"""Phase 3 验收：多租户隔离（RLS/FORCE RLS，图谱 60-02）。

验收口径（差距清单 Phase 3）：
    「多租户隔离测试通过；关键写路径有 Revision/Receipt 留痕」

本测试分两种形态：
1. PostgreSQL 可用（DATABASE_URL 或 TEST_PG_URL 为 postgresql://）：
   真实 RLS 断言 —— 两个租户互不可见、FORCE RLS 对 owner 生效、无租户上下文查空。
2. 无 PostgreSQL（本机开发默认 SQLite）：
   如实 SKIP，不伪装通过；打印接入指引。
   （SQLite 不支持 RLS，租户隔离由应用层 company_id 过滤承担，已有 test_auth_rbac
    等覆盖；迁移体系 `alembic upgrade head` 在 PG 上自动启用 RLS。）

运行：
    backend/venv/Scripts/python.exe tests/test_rls_isolation.py
    # PG 环境：$env:TEST_PG_URL="postgresql://user:pass@host:5432/furui_aios_test" 后运行
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import create_engine  # noqa: E402

PASS, FAIL, SKIP = [], [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def _pg_url() -> str | None:
    for var in ("TEST_PG_URL", "DATABASE_URL"):
        url = os.getenv(var) or ""
        if url.startswith("postgresql"):
            return url
    return None


def _rl_sql(table: str) -> str:
    return f"""
    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation ON {table};
    CREATE POLICY tenant_isolation ON {table}
      USING (company_id = NULLIF(current_setting('app.company_id', true), '')::int)
      WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::int);
    """


def _scalar(engine, sql: str, params: dict | None = None):
    with engine.connect() as con:
        return con.execute(text(sql), params or {}).scalar()


def main() -> int:
    url = _pg_url()
    if not url:
        print("SKIP  本机无 PostgreSQL（当前 DATABASE_URL 非 postgresql://）。")
        print("      说明：RLS 为 PostgreSQL 特性，SQLite 开发形态不支持；")
        print("      生产切 PG 后执行 `alembic upgrade head` 自动启用 RLS（SQLite 上该迁移自动跳过）。")
        print("      接入后运行：$env:TEST_PG_URL='postgresql://user:pass@host:5432/furui_aios_test'")
        print("                 ; .\\venv\\Scripts\\python.exe tests\\test_rls_isolation.py")
        SKIP.append("rls-isolation（PG 缺失）")
        print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} / SKIP {len(SKIP)} ===")
        return 0

    print(f"=== PostgreSQL 模式：{url.split('@')[-1] if '@' in url else url} ===")
    engine = create_engine(url)

    # ---- 前置：确保关键表存在（在全新测试库上先跑一次建表，模拟已迁移） ----
    from app.db import Base  # noqa: E402
    import app.models  # noqa: E402, F401
    import app.models_ai  # noqa: E402, F401
    import app.models_ontology  # noqa: E402, F401

    Base.metadata.create_all(engine)

    # ---- 前置：受限角色 furui_app（TASK-020 双库已建 + 全表 GRANT；
    #     RLS 只对非超级用户生效；生产同形态：应用用非超管连接） ----
    import re as _re
    app_url = _re.sub(r"//[^@]+@", "//furui_app:furui_app_local@", url)
    app_engine = create_engine(app_url)

    # ---- 清理残留 ----
    with engine.begin() as con:
        con.execute(text("DELETE FROM sales_tasks WHERE title LIKE 'RLS%'"))
        con.execute(text("DELETE FROM agent_steps WHERE title LIKE 'RLS%' OR title LIKE 'RLS步%'"))
        con.execute(text("DELETE FROM agent_tasks WHERE input_text LIKE 'RLS%'"))
        con.execute(text("DELETE FROM companies WHERE code IN ('RLS-A','RLS-B')"))

    # ---- 1. 两个租户 + 各自数据 ----
    with engine.begin() as con:
        con.execute(text("INSERT INTO companies(code, name, status) VALUES ('RLS-A','租户A','active')"))
        con.execute(text("INSERT INTO companies(code, name, status) VALUES ('RLS-B','租户B','active')"))
    a_id = _scalar(engine, "SELECT id FROM companies WHERE code='RLS-A'")
    b_id = _scalar(engine, "SELECT id FROM companies WHERE code='RLS-B'")
    check("创建租户 A/B", bool(a_id) and bool(b_id), f"A={a_id} B={b_id}")

    # ---- 2. 启用 RLS（等效 alembic e29b7c11a4d0 的迁移 SQL） ----
    with engine.begin() as con:
        con.execute(text(_rl_sql("sales_tasks")))
    with engine.begin() as con:
        con.execute(text(
            "INSERT INTO sales_tasks(company_id, title, customer_name, detail, priority, owner, due_date, status, source, created_by) "
            "VALUES (:a, 'RLS任务-A', '客户A', '', 'high', '', '', '待跟进', 'agent', 'tester'), "
            "       (:b, 'RLS任务-B', '客户B', '', 'high', '', '', '待跟进', 'agent', 'tester')"),
            {"a": a_id, "b": b_id})

    # ---- 3. 租户 A 上下文：只见 A ----
    with app_engine.connect() as con:
        con.execute(text(f"SET LOCAL app.company_id = '{a_id}'"))
        rows = con.execute(text("SELECT title FROM sales_tasks ORDER BY title")).fetchall()
        titles = [r[0] for r in rows]
    check("租户A 只见自己的行", titles == ["RLS任务-A"], str(titles))

    # ---- 4. 租户 B 上下文：只见 B ----
    with app_engine.connect() as con:
        con.execute(text(f"SET LOCAL app.company_id = '{b_id}'"))
        rows = con.execute(text("SELECT title FROM sales_tasks ORDER BY title")).fetchall()
        titles = [r[0] for r in rows]
    check("租户B 只见自己的行", titles == ["RLS任务-B"], str(titles))

    # ---- 5. 无租户上下文：查空（FORCE RLS + current_setting 缺省安全兜底） ----
    with app_engine.connect() as con:
        rows = con.execute(text("SELECT title FROM sales_tasks")).fetchall()
    check("无上下文查空（安全拒绝）", len(rows) == 0, str([r[0] for r in rows]))

    # ---- 6. RLS 对受限角色生效（生产同形态：应用非超管连接） ----
    with app_engine.begin() as con:
        con.execute(text(f"SET LOCAL app.company_id = '{a_id}'"))
        # 上下文匹配：更新自己的行，WITH CHECK 允许
        con.execute(text("UPDATE sales_tasks SET status='已完成' WHERE title='RLS任务-A'"))
    with app_engine.begin() as con:
        # 无上下文更新任意行：被 RLS 拦截（0 行）
        res = con.execute(text("UPDATE sales_tasks SET status='已删除'"))
        check("RLS：无上下文 UPDATE 影响 0 行", res.rowcount == 0, f"rowcount={res.rowcount}")

    # ---- 7. 写入隔离：租户A 上下文插入 B 数据被 WITH CHECK 拦截（PG 抛 RLS 错误） ----
    with app_engine.begin() as con:
        con.execute(text(f"SET LOCAL app.company_id = '{a_id}'"))
        try:
            con.execute(text(
                "INSERT INTO sales_tasks(company_id, title, customer_name, detail, priority, owner, due_date, status, source, created_by) "
                "VALUES (:b, 'RLS越权-B', '客户B', '', 'high', '', '', '待跟进', 'agent', 'tester')"), {"b": b_id})
            check("租户A 写入 B 租户行被 WITH CHECK 拦截（抛错）", False, "未抛错，越权写入成功")
        except Exception as e:                                       # noqa: BLE001
            msg = str(e)
            check("租户A 写入 B 租户行被 WITH CHECK 拦截（抛错）",
                  "row-level security" in msg.lower() or "行级安全" in msg, msg[:100])

    # ---- 8. 全表 RLS 已收口：无上下文 SELECT/UPDATE 均安全拒绝 ----
    with app_engine.connect() as con:
        rows = con.execute(text("SELECT count(*) FROM users")).scalar()
        check("全表收口：无上下文 SELECT users = 0", rows == 0, f"count={rows}")
    with app_engine.begin() as con:
        res = con.execute(text("UPDATE users SET name=name"))
        check("全表收口：无上下文 UPDATE users 影响 0 行", res.rowcount == 0, f"rowcount={res.rowcount}")

    # ---- 9. 负向 canary：OR 绕过 / LIKE 绕过 / 复杂条件 均不可见 ----
    with app_engine.connect() as con:
        con.execute(text(f"SET LOCAL app.company_id = '{a_id}'"))
        rows = con.execute(text(
            "SELECT title FROM sales_tasks WHERE title LIKE 'RLS%' OR 1=1 ORDER BY title")).fetchall()
        titles = [r[0] for r in rows]
    check("负向 canary：A 上下文 OR 1=1 仍只见 A", titles == ["RLS任务-A"], str(titles))

    with app_engine.connect() as con:
        con.execute(text(f"SET LOCAL app.company_id = '{a_id}'"))
        rows = con.execute(text(
            "SELECT title FROM sales_tasks WHERE title LIKE '%任务-B%' OR company_id IS NOT NULL "
            "ORDER BY title")).fetchall()
        titles = [r[0] for r in rows]
    check("负向 canary：A 上下文复杂条件仍只见 A", titles == ["RLS任务-A"], str(titles))

    # ---- 10. 负向 JOIN：跨表读 B 租户不可达 ----
    with app_engine.connect() as con:
        con.execute(text(f"SET LOCAL app.company_id = '{a_id}'"))
        rows = con.execute(text(
            "SELECT s.title, c.code FROM sales_tasks s JOIN companies c ON c.id=s.company_id "
            "ORDER BY s.title")).fetchall()
        pairs = [(r[0], r[1]) for r in rows]
    check("负向 JOIN：A 上下文 JOIN companies 只见 A", pairs == [("RLS任务-A", "RLS-A")], str(pairs))

    # ---- 11. 子表复合租户键：agent_steps 经 agent_tasks 归属隔离 ----
    with engine.begin() as con:
        con.execute(text(
            "INSERT INTO agent_tasks(company_id, title, mode, input_text, conversation_id, brief, "
            "                        status, priority, progress, result, error, retry_count) "
            "VALUES (:a, 'RLS任务A', '智能问答', 'RLS任务-A的plan', 'RLS-CONV-A', '{}', "
            "        'Pending', 3, 0, '', '', 0), "
            "       (:b, 'RLS任务B', '智能问答', 'RLS任务-B的plan', 'RLS-CONV-B', '{}', "
            "        'Pending', 3, 0, '', '', 0)"),
            {"a": a_id, "b": b_id})
    a_task = _scalar(engine, "SELECT id FROM agent_tasks WHERE input_text='RLS任务-A的plan'")
    b_task = _scalar(engine, "SELECT id FROM agent_tasks WHERE input_text='RLS任务-B的plan'")
    with engine.begin() as con:
        con.execute(text(
            "INSERT INTO agent_steps(task_id, seq, title, kind, depends_on, status, retry_count, "
            "                        input_data, output_data, error) "
            "VALUES (:at, 0, 'RLS步-A1', 'think', '[]', 'Pending', 0, '{}', '{}', ''), "
            "       (:at, 1, 'RLS步-A2', 'think', '[]', 'Pending', 0, '{}', '{}', ''), "
            "       (:bt, 0, 'RLS步-B1', 'think', '[]', 'Pending', 0, '{}', '{}', '')"),
            {"at": a_task, "bt": b_task})
    with app_engine.connect() as con:
        con.execute(text(f"SET LOCAL app.company_id = '{a_id}'"))
        rows = con.execute(text("SELECT title FROM agent_steps ORDER BY title")).fetchall()
        titles = [r[0] for r in rows]
    check("子表复合租户键：A 只见自己任务的 steps", titles == ["RLS步-A1", "RLS步-A2"], str(titles))

    # ---- 12. 越权写子表：A 上下文 INSERT 关联 B 的 task → WITH CHECK 拦截 ----
    with app_engine.begin() as con:
        con.execute(text(f"SET LOCAL app.company_id = '{a_id}'"))
        try:
            con.execute(text(
                "INSERT INTO agent_steps(task_id, seq, title, kind, depends_on, status, retry_count, "
                "                        input_data, output_data, error) "
                "VALUES (:bt, 9, 'RLS越权-B步', 'think', '[]', 'Pending', 0, '{}', '{}', '')"),
                {"bt": b_task})
            check("子表越权写被 WITH CHECK 拦截（抛错）", False, "未抛错，越权写入成功")
        except Exception as e:                                   # noqa: BLE001
            msg = str(e)
            check("子表越权写被 WITH CHECK 拦截（抛错）",
                  "row-level security" in msg.lower() or "行级安全" in msg, msg[:100])

    # ---- 清理 ----
    with engine.begin() as con:
        con.execute(text("DELETE FROM sales_tasks WHERE title LIKE 'RLS%'"))
        con.execute(text("DELETE FROM agent_steps WHERE title LIKE 'RLS%' OR title LIKE 'RLS步%'"))
        con.execute(text("DELETE FROM agent_tasks WHERE input_text LIKE 'RLS%'"))
        con.execute(text("DELETE FROM companies WHERE code IN ('RLS-A','RLS-B')"))
    engine.dispose()

    print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} / SKIP {len(SKIP)} ===")
    if FAIL:
        print("失败：", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
