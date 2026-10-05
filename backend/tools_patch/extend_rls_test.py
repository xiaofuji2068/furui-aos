# -*- coding: utf-8 -*-
"""TASK-020：扩展 test_rls_isolation.py —— 负向 canary + 子表复合租户键 + 全表无上下文拒绝。

在现有 PG 模式 6 断言基础上追加（用 furui_app 受限角色，双库已建+全表 GRANT）：
7.  无上下文 SELECT users = 0（全库 RLS 已收口）
8.  无上下文 UPDATE users = 0 行
9.  负向 canary：A 上下文 OR 1=1 / LIKE 绕过 → 仍只见 A
10. 负向 JOIN：A 上下文 JOIN companies 只见 A
11. 子表复合租户键：agent_tasks + agent_steps 按父表隔离（A 只见 A 的 steps）
12. 越权写子表：A 上下文 INSERT step 关联 B 的 task → WITH CHECK 拦截
"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_rls_isolation.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

# ---- 1) 受限角色改 furui_app（双库已建，全表 GRANT）；URL 替换 ----
old = '''    # ---- 前置：受限角色 app_test（RLS 只对非超级用户生效；生产同形态：应用用非超管连接） ----
    with engine.begin() as con:
        con.execute(text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='app_test') "
            "THEN CREATE ROLE app_test LOGIN PASSWORD 'app_test'; END IF; END $$;"))
        con.execute(text("GRANT USAGE ON SCHEMA public TO app_test"))
        con.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON sales_tasks TO app_test"))
        con.execute(text("GRANT SELECT ON companies TO app_test"))
        con.execute(text("GRANT USAGE ON SEQUENCE sales_tasks_id_seq TO app_test"))

    # 构造受限角色连接 URL
    import re as _re
    app_url = _re.sub(r"//[^@]+@", "//app_test:app_test@", url)
    app_engine = create_engine(app_url)'''
new = '''    # ---- 前置：受限角色 furui_app（TASK-020 双库已建 + 全表 GRANT；
    #     RLS 只对非超级用户生效；生产同形态：应用用非超管连接） ----
    import re as _re
    app_url = _re.sub(r"//[^@]+@", "//furui_app:furui_app_local@", url)
    app_engine = create_engine(app_url)'''
assert old in src, "1 anchor"
src = src.replace(old, new, 1)

# ---- 2) 清理残留：追加 agent_tasks/steps 清理 ----
old = '''    with engine.begin() as con:
        con.execute(text("DELETE FROM sales_tasks WHERE title LIKE 'RLS%'"))
        con.execute(text("DELETE FROM companies WHERE code IN ('RLS-A','RLS-B')"))'''
new = '''    with engine.begin() as con:
        con.execute(text("DELETE FROM sales_tasks WHERE title LIKE 'RLS%'"))
        con.execute(text("DELETE FROM agent_steps WHERE title LIKE 'RLS%' OR title LIKE 'RLS步%'"))
        con.execute(text("DELETE FROM agent_tasks WHERE input_text LIKE 'RLS%'"))
        con.execute(text("DELETE FROM companies WHERE code IN ('RLS-A','RLS-B')"))'''
assert old in src, "2 anchor"
src = src.replace(old, new, 1)

# ---- 3) 在"写入隔离"用例后追加负向 canary 与子表用例 ----
old = '''    # ---- 清理 ----
    with engine.begin() as con:
        con.execute(text("DELETE FROM sales_tasks WHERE title LIKE 'RLS%'"))
        con.execute(text("DELETE FROM companies WHERE code IN ('RLS-A','RLS-B')"))
    engine.dispose()'''
new = '''    # ---- 8. 全表 RLS 已收口：无上下文 SELECT/UPDATE 均安全拒绝 ----
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
            "INSERT INTO agent_tasks(company_id, mode, input_text, status) "
            "VALUES (:a, '智能问答', 'RLS任务-A的plan', 'Pending'), "
            "       (:b, '智能问答', 'RLS任务-B的plan', 'Pending')"),
            {"a": a_id, "b": b_id})
    a_task = _scalar(engine, "SELECT id FROM agent_tasks WHERE input_text='RLS任务-A的plan'")
    b_task = _scalar(engine, "SELECT id FROM agent_tasks WHERE input_text='RLS任务-B的plan'")
    with engine.begin() as con:
        con.execute(text(
            "INSERT INTO agent_steps(task_id, seq, title, status) "
            "VALUES (:at, 0, 'RLS步-A1', 'Pending'), "
            "       (:at, 1, 'RLS步-A2', 'Pending'), "
            "       (:bt, 0, 'RLS步-B1', 'Pending')"),
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
                "INSERT INTO agent_steps(task_id, seq, title, status) "
                "VALUES (:bt, 9, 'RLS越权-B步', 'Pending')"), {"bt": b_task})
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
    engine.dispose()'''
assert old in src, "3 anchor"
src = src.replace(old, new, 1)

with io.open(p, "w", encoding="utf-8") as f:
    f.write(src)
print("OK: test_rls_isolation extended")
