# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\pages.py")
t = p.read_text(encoding="utf-8")
old = 'from .models_ai import AppPage'
new = 'from .models_ai import AppPage\nfrom .models import Company'
if old in t and "from .models import Company" not in t:
    t = t.replace(old, new, 1)
old2 = '''def seed_pages(db: Session, company_id: int = 1) -> List[AppPage]:
    created: List[AppPage] = []'''
new2 = '''def seed_pages(db: Session, company_id: int = 1) -> List[AppPage]:
    created: List[AppPage] = []
    if db.get(Company, company_id) is None:
        return created  # 无效租户：不 seed（外键/RLS 防御）'''
if old2 in t:
    t = t.replace(old2, new2, 1)
    p.write_text(t, encoding="utf-8")
    print("patched OK")
else:
    print("PATTERN NOT FOUND")