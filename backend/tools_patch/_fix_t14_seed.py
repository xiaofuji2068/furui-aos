# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_logic_graph.py")
s = p.read_text(encoding="utf-8")
old = 'check("seed 创建 2 张图", len(created) == 2)'
new = 'check("seed 创建 2 张图（或已幂等存在）", len(created) in (0, 2))'
assert old in s
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK")