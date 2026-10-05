# -*- coding: utf-8 -*-
import sys, traceback
sys.path.insert(0, r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
from alembic.config import Config
from alembic import command
import os
os.chdir(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")
for name, url in [("prod", "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios"),
                  ("test", "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test")]:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    try:
        command.upgrade(cfg, "head")
        print(f"[{name}] upgrade head OK")
    except Exception:
        print(f"[{name}] FAIL:")
        traceback.print_exc()