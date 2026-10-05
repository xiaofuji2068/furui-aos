# -*- coding: utf-8 -*-
"""重置隔离测试库 furui_aios_test（drop → create → alembic upgrade head → init_all）。

为什么需要：
    测试脚本在隔离库上跑完后会残留数据（如 AssetBundle code='test-bundle'），
    下一轮再跑就撞唯一键崩溃（ValueError: Bundle code 'test-bundle' 已存在），
    且因为跑不到汇总行，会被 run_tests.py 之外的方式误读成「通过」。

建库方式（重要，2026-10-05 修正）：
    以前这里用 Base.metadata.create_all()。那是个「看起来能用」的偷懒路径，
    但它绕开了 alembic：
      1) create_all 只建表，不建 alembic_version、不跑数据迁移、不建 RLS 策略；
      2) 于是「迁移链本身能不能在新环境跑通」这个最关键的问题从来没被验证过；
      3) 更糟的是残留 schema 再跑 alembic 会撞 DuplicateTable。
    现在改成 drop/create → `alembic upgrade head`，与真实新环境完全同路径。
    已验证：干净库上 16 个迁移一次跑通，public 表 46 张，head = 8c9d0e1f2a3b，
    模型表 45 张全部覆盖（多出的 1 张是 alembic_version 元数据表）。

用法：
    cd backend && venv/Scripts/python.exe tools_patch/reset_test_db.py
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# 本脚本位于 backend/tools_patch/，sys.path[0] 是 tools_patch，
# 直接 import app.db 会 ModuleNotFoundError，需把 backend 根加进路径。
sys.path.insert(0, str(ROOT))
# psycopg 原生 connect() 只认 postgresql://（后端的 +psycopg 是 SQLAlchemy 语法，
# 传给 psycopg 会被当 conninfo 字符串报 "missing =" ）
PG_DSN = "postgresql://postgres:postgres123@127.0.0.1:5432"
# 必须是 postgresql+psycopg://（psycopg3）。写成 postgresql:// 时 SQLAlchemy
# 默认 driver 会落到 psycopg2，而环境里没装 psycopg2 → ModuleNotFoundError。
BASE = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432"
TEST = f"{BASE}/furui_aios_test"
TEST_NAME = "furui_aios_test"

# TASK-020：受限角色 RLS 只对非超级用户生效，应用连接必须用它。
# furui_app 是集群级 role，但每个库都要单独 GRANT，否则应用连接=超管，
# test_rls_isolation 会直接 InsufficientPrivilege / RLS 不生效。
GRANT_SQL = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'furui_app') THEN
    CREATE ROLE furui_app LOGIN PASSWORD 'furui_app_local';
  END IF;
END
$$;
GRANT CONNECT ON DATABASE {db} TO furui_app;
GRANT USAGE ON SCHEMA public TO furui_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO furui_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO furui_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO furui_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO furui_app;
"""


def main():
    import psycopg

    # 1) 断连旧会话 → 删库 → 建库
    # psycopg3 默认在隐式事务里，而 DROP DATABASE / CREATE DATABASE 不允许在事务块中运行
    admin = psycopg.connect(f"{PG_DSN}/postgres", dbname="postgres", autocommit=True)
    admin.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{TEST_NAME}' AND pid <> pg_backend_pid()"
    )
    admin.execute(f"DROP DATABASE IF EXISTS {TEST_NAME}")
    admin.execute(f"CREATE DATABASE {TEST_NAME}")
    admin.close()
    print(f"[1/5] 已 drop/create {TEST_NAME}")

    # 2) 迁移链建库（与真实新环境同路径，顺带验证 alembic 可用）
    env = dict(os.environ)
    env["DATABASE_URL"] = TEST
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       cwd=str(ROOT), env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("[2/5] ❌ alembic upgrade head 失败：")
        for line in ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-20:]:
            print("      |", line)
        return 1
    # 别从日志末尾猜 head（末尾行未必带 "->"），直接读版本表
    import psycopg as _pg

    _c = _pg.connect(f"{PG_DSN}/{TEST_NAME}", dbname=TEST_NAME)
    _row = _c.execute("SELECT version_num FROM alembic_version").fetchone()
    _c.close()
    ver = _row[0] if _row else "unknown"
    print(f"[2/5] ✅ 迁移链跑通，head = {ver}")

    # 3) 跑 bootstrap.init_all 补齐业务基础数据：租户、admin 及其他角色账号、
    #    角色/权限点/关联、ontology seed、AI 技能与数据源等。
    #    这是与生产库一致的初始状态——曾经那批「600/35 全绿」的回归
    #    就是跑在已 init 的库上；只 create_all 不 init 会导致大面积
    #    403 缺权限 / 401 无账号 / uq_onto_obj 唯一键冲突。
    #
    #    代价（已确认，非 bug）：init_all 会 seed 2 个 AssetBundle，因此
    #    test_asset_bundle 的「seed 首次创建 2 Bundle」断言在任何已 init 的库上
    #    必然失败。这是 TASK-016 遗留的测试设计缺陷，单独排期。
    os.environ["DATABASE_URL"] = TEST
    from app.bootstrap import init_all

    init_all(force_erp=False)
    print("[3/5] ✅ bootstrap.init_all 补齐基础数据（角色/权限/账号/ontology）")

    # 4) 授权受限角色 furui_app（解锁 test_rls_isolation）
    conn = psycopg.connect(f"{PG_DSN}/{TEST_NAME}", dbname=TEST_NAME, autocommit=True)
    conn.execute(GRANT_SQL.format(db=TEST_NAME))
    conn.close()
    print("[4/5] ✅ furui_app 受限角色已授权（RLS 前提）")

    # 5) 校验表数
    import psycopg as pg

    c = pg.connect(f"{PG_DSN}/{TEST_NAME}", dbname=TEST_NAME)
    n = c.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
    ).fetchone()[0]
    c.close()
    print(f"[5/5] ✅ {TEST_NAME} 就绪，public 表 {n} 张")
    return 0 if n > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
