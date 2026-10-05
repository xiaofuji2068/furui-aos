# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios"
import alembic.config
from alembic import command

cfg = alembic.config.Config("alembic.ini")
try:
    command.current(cfg)
    out = "CURRENT OK"
except Exception as e:
    out = "CURRENT ERR %r" % e
open(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tools_patch\alembic_cur.txt", "w", encoding="utf-8").write(out)
