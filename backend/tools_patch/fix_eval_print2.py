# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_eval_contract.py")
t = p.read_text(encoding="utf-8")
old = '        r3 = execute(ctx, "create_sales_task", {'
new = '        print("DIAG r3 ctx:", ctx.company_id, getattr(ctx.agent, "code", None))\n        r3 = execute(ctx, "create_sales_task", {'
if old in t:
    t = t.replace(old, new, 1)
else:
    print("MISS r3")
p.write_text(t, encoding="utf-8")
ast.parse(p.read_text(encoding="utf-8"))
print("OK")