# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend\app\pages\page.tsx")
t = p.read_text(encoding="utf-8")
old = '''  deletePage,
  draftPage,
  fetchPages,
  fetchWidgetTypes,'''
new = '''  deletePage,
  draftPage,
  fetchPageByCode,
  fetchPages,
  fetchWidgetTypes,'''
assert old in t, "import block not found"
t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
print("fetchPageByCode imported")