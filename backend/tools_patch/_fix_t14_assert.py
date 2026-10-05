# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_logic_graph.py")
s = p.read_text(encoding="utf-8")
old = '''        check("同租户仅 1 张 active", len([i for i in items2 if i["status"] == "active"]) == 1)'''
new = '''        check("激活后目标图 active", g["status"] == "active")
        t2 = list_graphs(db, cid)
        tg = [i for i in t2 if i["id"] == target][0]
        check("目标图状态持久", tg["status"] == "active")
        check("另一链路图仍 active（互不影响）",
              len([i for i in t2 if i["code"] == "sales-drop" and i["status"] == "active"]) == 1)'''
assert old in s
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK")