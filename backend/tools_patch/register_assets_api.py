# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\api\__init__.py")
t = p.read_text(encoding="utf-8")
old = '''from .pages_api import router as pages_router'''
new = '''from .pages_api import router as pages_router
from .assets_api import router as assets_router'''
assert old in t, "import anchor not found"
t = t.replace(old, new, 1)
old2 = '''# 低代码页面（40-03）
router.include_router(pages_router)'''
new2 = '''# 低代码页面（40-03）
router.include_router(pages_router)
# 资产装配（50 全系：Bundle/Registry/Resolver/Installation/Plugin）
router.include_router(assets_router)'''
assert old2 in t, "include anchor not found"
t = t.replace(old2, new2, 1)
p.write_text(t, encoding="utf-8")
ast.parse(t)
print("assets_api registered")