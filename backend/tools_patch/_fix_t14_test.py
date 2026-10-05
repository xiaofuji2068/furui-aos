# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_logic_graph.py")
s = p.read_text(encoding="utf-8")
old = "import pytest\n"
assert old in s
new = "from app.mainline import MainlineRunner  # noqa: F401  (引擎读图验证)\n"
s = s.replace(old, new, 1)
# 补丁脚本生成的版本遗留 pytest fixture/import 兼容：检查是否还引用 pytest
if "import pytest" in s:
    print("STILL HAS pytest, force rewrite")
else:
    p.write_text(s, encoding="utf-8")
    print("OK minimal fix")