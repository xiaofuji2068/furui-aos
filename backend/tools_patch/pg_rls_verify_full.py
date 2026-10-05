# -*- coding: utf-8 -*-
"""TASK-020 验证：测试库 RLS 全表收口 + furui_app 受限角色真实约束。"""
import os
import subprocess

PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
env = dict(os.environ)
env["PGPASSWORD"] = "postgres123"

# 1) 测试库 RLS 状态
p = subprocess.run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", "furui_aios_test",
                    "-c", """
SELECT c.relname AS t, c.relrowsecurity AS rls, c.relforcerowsecurity AS force_rls,
       (SELECT count(*) FROM pg_policies pp WHERE pp.tablename=c.relname) AS pol
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind='r' AND n.nspname='public' AND c.relname NOT IN ('alembic_version')
ORDER BY c.relname;
"""], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("=== 测试库 RLS 状态 ===")
print(p.stdout.strip())
lines = [l for l in p.stdout.splitlines() if l.strip() and "|" in l and "t" in l.split("|")[1]]
no_rls = [l.split("|")[0].strip() for l in p.stdout.splitlines()
          if l.strip() and "|" in l and l.split("|")[1].strip() == "f"]
print(f"\n已启用 RLS 表数: {len(lines)}")
print(f"未启用 RLS: {no_rls if no_rls else '(无)'}")

# 2) 受限角色验证（测试库现在全表 RLS）
print("\n=== furui_app 受限角色验证 ===")
import psycopg
with psycopg.connect("host=127.0.0.1 port=5432 dbname=furui_aios_test user=furui_app password=furui_app_local") as conn:
    cur = conn.execute("SELECT count(*) FROM users")
    n0 = cur.fetchone()[0]
    print(f"[无上下文] users 可见 = {n0} (期望 0)")

    conn.execute("SET LOCAL app.company_id = 3")
    cur = conn.execute("SELECT count(*) FROM users")
    n3 = cur.fetchone()[0]
    cur2 = conn.execute("SELECT count(DISTINCT company_id) FROM users")
    d = cur2.fetchone()[0]
    print(f"[租户3] users 可见 = {n3}, 唯一 company_id 数 = {d} (期望 1)")

    cur = conn.execute("UPDATE users SET name=name WHERE company_id != 3")
    print(f"[越权写] UPDATE 影响 = {cur.rowcount} (期望 0)")

    # 子表：agent_steps 复合租户键
    try:
        cur = conn.execute("SELECT count(*) FROM agent_steps")
        print(f"[无上下文] agent_steps 可见 = {cur.fetchone()[0]} (期望 0)")
    except Exception as e:
        print("agent_steps 查询异常:", str(e)[:120])
