# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_outbox_projector.py")
t = p.read_text(encoding="utf-8")
old = '''            src = f"N{i % 20:03d}"
            dst = f"N{(i + 1) % 20:03d}"'''
new = '''            src = f"N{i:03d}"
            dst = f"N{i + 1:03d}"'''
if old in t:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8")
    print("outbox loop: PATCHED")
else:
    print("outbox loop: MISS")
ast.parse(p.read_text(encoding="utf-8"))
print("SYNTAX OK")