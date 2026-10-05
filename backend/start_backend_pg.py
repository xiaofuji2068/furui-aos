# -*- coding: utf-8 -*-
"""启动后端（强制 PG 生产库，绕开 shell env 传递坑）。"""
import os
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios"
import uvicorn
uvicorn.run("app.main:app", host="127.0.0.1", port=8000)