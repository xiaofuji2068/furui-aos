# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test"
import alembic.config
from alembic import command

out = []
cfg = alembic.config.Config("alembic.ini")
try:
    command.stamp(cfg, "8c9d0e1f2a3b")
    out.append("STAMP OK")
except Exception as e:
    out.append("STAMP ERR %r" % e)
try:
    command.current(cfg)
    out.append("CURRENT OK")
except Exception as e:
    out.append("CURRENT ERR %r" % e)

open(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tools_patch\stamp_test.txt", "w", encoding="utf-8").write("\n".join(out))
