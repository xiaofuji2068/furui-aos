# -*- coding: utf-8 -*-
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\bootstrap.py"
s = io.open(p, encoding="utf-8").read()

old1 = "from .rag import index_document\nfrom .ontology import seed_ontology\n"
new1 = "from .rag import index_document\nfrom .ontology import seed_ontology\nfrom .assets import seed_bundles\n"
assert old1 in s, "anchor1 missing"
s = s.replace(old1, new1, 1)

old2 = "        seed_ai(db)\n"
new2 = "        seed_ai(db)\n        seed_bundles(db)  # TASK-016 平台资产目录（幂等，全局 RLS 豁免）\n"
assert old2 in s, "anchor2 missing"
s = s.replace(old2, new2, 1)

io.open(p, "w", encoding="utf-8").write(s)
import ast
ast.parse(s)
print("PATCH OK")
