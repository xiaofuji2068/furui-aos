# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios"
import alembic.config
from alembic import command

out = []
cfg = alembic.config.Config("alembic.ini")
try:
    command.upgrade(cfg, "head")
    out.append("UPGRADE OK")
except Exception as e:
    out.append("UPGRADE ERR %r" % e)
try:
    command.current(cfg)
    out.append("CURRENT OK")
except Exception as e:
    out.append("CURRENT ERR %r" % e)

open(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tools_patch\upgrade_prod.txt", "w", encoding="utf-8").write("\n".join(out))
