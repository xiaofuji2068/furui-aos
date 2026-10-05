# -*- coding: utf-8 -*-
"""调试：在测试环境下实测 migrate_env_to_keychain 全流程。"""
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")

from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.store_secrets import migrate_env_to_keychain

with TestClient(app) as c:
    env_path = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\.env")
    backup = env_path.read_text(encoding="utf-8")
    try:
        env_path.write_text("DEEPSEEK_API_KEY=sk-migrate-ds\nKIMI_API_KEY=sk-migrate-kimi\n",
                            encoding="utf-8", newline="\n")
        print("=== 写入后文件内容 ===")
        print(env_path.read_text(encoding="utf-8"))
        db = SessionLocal()
        try:
            res = migrate_env_to_keychain(db, 1, actor_name="tester")
        finally:
            db.close()
        print("=== migrate 结果 ===")
        print(res)
    finally:
        env_path.write_text(backup, encoding="utf-8", newline="\n")
        print("=== .env 已还原 ===")
