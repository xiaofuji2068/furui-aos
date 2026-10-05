# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios"
from app.bootstrap import init_all
from app.db import SessionLocal
from app.assets import list_bundles

out = []
try:
    init_all()
    out.append("INIT_ALL OK")
except Exception as e:
    out.append("INIT_ALL ERR %r" % e)
db = SessionLocal()
try:
    bundles = list_bundles(db, company_id=16)
    out.append("BUNDLES: %d" % len(bundles))
    for b in bundles:
        out.append("- %s %s v%s status=%s" % (b["code"], b["name"], b["version"], b["status"]))
except Exception as e:
    out.append("LIST ERR %r" % e)
finally:
    db.close()
open(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tools_patch\bootstrap_verify.txt", "w", encoding="utf-8").write("\n".join(out))
