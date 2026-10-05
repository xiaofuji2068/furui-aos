# -*- coding: utf-8 -*-
"""验证「全新环境」能否只用 alembic 迁移链建库（任务 C）。

为什么需要：
    之前 reset_test_db.py 里写过注释「alembic/env.py 依赖 psycopg2，新库统一走
    create_all」。后来诊断证明这个结论是错的——driver 其实是对的
    （engine dialect = PGDialect_psycopg | driver = psycopg）。
    真正导致 alembic 失败的是：测试库里已经有 create_all 建的 audit_logs 等表，
    migration DDL 撞 DuplicateTable。也就是「迁移链本身没问题，是被脏库污染的」。

本脚本用一个一次性新库 furui_aios_migtest 做纯净验证：
    1) drop/create 干净库
    2) alembic upgrade head（纯迁移链，不跑 create_all）
    3) 拉出 migration 实际建的表数 / alembic_version / head revision
    4) 与 Base.metadata 的模型表数做对比，报告缺口

用法：
    cd backend && venv/Scripts/python.exe tools_patch/verify_migration_fresh.py
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PG_DSN = "postgresql://postgres:postgres123@127.0.0.1:5432"
BASE = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432"
DB = "furui_aios_migtest"
TEST_URL = f"{BASE}/{DB}"


def run(cmd, env_extra=None):
    import os
    env = dict(os.environ)
    env["DATABASE_URL"] = TEST_URL
    if env_extra:
        env.update(env_extra)
    return subprocess.run(cmd, cwd=str(ROOT), env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def main():
    import psycopg

    # 1) 干净库
    admin = psycopg.connect(f"{PG_DSN}/postgres", dbname="postgres", autocommit=True)
    admin.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{DB}' AND pid <> pg_backend_pid()"
    )
    admin.execute(f"DROP DATABASE IF EXISTS {DB}")
    admin.execute(f"CREATE DATABASE {DB}")
    admin.close()
    print(f"[1/4] 已创建干净库 {DB}")

    # 2) 纯迁移链升级
    r = run([sys.executable, "-m", "alembic", "upgrade", "head"])
    tail = (r.stdout or "") + (r.stderr or "")
    print(f"[2/4] alembic upgrade head -> returncode={r.returncode}")
    for line in tail.strip().splitlines()[-15:]:
        print("      |", line)
    if r.returncode != 0:
        print("❌ 迁移链在干净库上失败")
        return 1

    # 3) 现状盘点
    c = psycopg.connect(f"{PG_DSN}/{DB}", dbname=DB)
    n = c.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
    ).fetchone()[0]
    ver = c.execute("SELECT version_num FROM alembic_version").fetchone()
    c.close()
    print(f"[3/4] 迁移后 public 表 {n} 张，alembic_version = {ver[0] if ver else None}")

    # 4) 与模型对比
    import app.models  # noqa: F401
    import app.models_ontology  # noqa: F401
    import app.models_ai  # noqa: F401
    from app.db import Base

    model_tables = set(Base.metadata.tables)
    c = psycopg.connect(f"{PG_DSN}/{DB}", dbname=DB)
    real = {r_[0] for r_ in c.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    ).fetchall()}
    c.close()
    missing = sorted(t for t in model_tables if t not in real)
    extra = sorted(t for t in real if t not in model_tables)
    print(f"[4/4] 模型表 {len(model_tables)} / 迁移表 {len(real)}")
    print(f"      迁移未建的模型表({len(missing)}): {missing}")
    print(f"      迁移多建的表({len(extra)}): {extra}")
    print("✅ 迁移链在干净库上可用" if r.returncode == 0 and not missing else "⚠️ 有缺口")
    return 0


if __name__ == "__main__":
    sys.exit(main())
