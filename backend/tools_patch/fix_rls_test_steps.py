# -*- coding: utf-8 -*-
"""修 test_rls_isolation：agent_steps INSERT 补全 NOT NULL 列。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_rls_isolation.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

old = '''        con.execute(text(
            "INSERT INTO agent_steps(task_id, seq, title, status) "
            "VALUES (:at, 0, 'RLS步-A1', 'Pending'), "
            "       (:at, 1, 'RLS步-A2', 'Pending'), "
            "       (:bt, 0, 'RLS步-B1', 'Pending')"),
            {"at": a_task, "bt": b_task})'''
new = '''        con.execute(text(
            "INSERT INTO agent_steps(task_id, seq, title, kind, depends_on, status, retry_count, "
            "                        input_data, output_data, error) "
            "VALUES (:at, 0, 'RLS步-A1', 'think', '[]', 'Pending', 0, '{}', '{}', ''), "
            "       (:at, 1, 'RLS步-A2', 'think', '[]', 'Pending', 0, '{}', '{}', ''), "
            "       (:bt, 0, 'RLS步-B1', 'think', '[]', 'Pending', 0, '{}', '{}', '')"),
            {"at": a_task, "bt": b_task})'''
assert old in src, "anchor1"
src = src.replace(old, new, 1)

old = '''            con.execute(text(
                "INSERT INTO agent_steps(task_id, seq, title, status) "
                "VALUES (:bt, 9, 'RLS越权-B步', 'Pending')"), {"bt": b_task})'''
new = '''            con.execute(text(
                "INSERT INTO agent_steps(task_id, seq, title, kind, depends_on, status, retry_count, "
                "                        input_data, output_data, error) "
                "VALUES (:bt, 9, 'RLS越权-B步', 'think', '[]', 'Pending', 0, '{}', '{}', '')"),
                {"bt": b_task})'''
assert old in src, "anchor2"
src = src.replace(old, new, 1)

with io.open(p, "w", encoding="utf-8") as f:
    f.write(src)
print("OK: agent_steps full columns")
