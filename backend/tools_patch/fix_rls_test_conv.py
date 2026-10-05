# -*- coding: utf-8 -*-
"""修 test_rls_isolation：agent_tasks INSERT 补 conversation_id（NOT NULL）。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_rls_isolation.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

old = '''        con.execute(text(
            "INSERT INTO agent_tasks(company_id, mode, input_text, status) "
            "VALUES (:a, '智能问答', 'RLS任务-A的plan', 'Pending'), "
            "       (:b, '智能问答', 'RLS任务-B的plan', 'Pending')"),
            {"a": a_id, "b": b_id})'''
new = '''        con.execute(text(
            "INSERT INTO agent_tasks(company_id, mode, input_text, conversation_id, status) "
            "VALUES (:a, '智能问答', 'RLS任务-A的plan', 'RLS-CONV-A', 'Pending'), "
            "       (:b, '智能问答', 'RLS任务-B的plan', 'RLS-CONV-B', 'Pending')"),
            {"a": a_id, "b": b_id})'''
assert old in src, "anchor"
src = src.replace(old, new, 1)

with io.open(p, "w", encoding="utf-8") as f:
    f.write(src)
print("OK: agent_tasks conversation_id fixed")
