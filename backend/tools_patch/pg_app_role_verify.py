# -*- coding: utf-8 -*-
"""TASK-020 验证：furui_app 受限角色连接下 RLS 生效（无上下文拒绝 / 租户隔离 / 越权写 0 行）。"""
import psycopg

DSN = "host=127.0.0.1 port=5432 dbname=furui_aios_test user=furui_app password=furui_app_local"

with psycopg.connect(DSN) as conn:
    conn.execute("SET ROLE NONE")  # 确保以 furui_app 身份

    # 1) 无租户上下文：安全拒绝（应 0 行）
    cur = conn.execute("SELECT count(*) FROM users")
    n = cur.fetchone()[0]
    print(f"[无上下文] users 可见行数 = {n}  (期望 0，安全拒绝)")

    # 2) 注入租户 3 后可见自己租户
    conn.execute("SET LOCAL app.company_id = 3")
    cur = conn.execute("SELECT id, company_id, username FROM users ORDER BY id LIMIT 5")
    rows = cur.fetchall()
    print(f"[租户3] users 可见 {len(rows)} 行: {rows}")
    cur = conn.execute("SELECT count(*) FROM users")
    print(f"[租户3] users 计数 = {cur.fetchone()[0]} (期望 = 租户3 的用户数)")

    # 3) 越权写：UPDATE company_id != 3 的行 → 0 行受影响
    cur = conn.execute("UPDATE users SET name = name WHERE company_id != 3")
    print(f"[越权写] UPDATE 影响行数 = {cur.rowcount} (期望 0)")

    # 4) 同事务内跨表：secret_entries 也隔离
    try:
        conn.execute("SET LOCAL app.company_id = 3")
    except Exception:
        pass
    cur = conn.execute("SELECT count(*) FROM secret_entries")
    print(f"[租户3] secret_entries 计数 = {cur.fetchone()[0]}")

print("\nOK: furui_app RLS 验证完成")
