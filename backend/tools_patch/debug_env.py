# -*- coding: utf-8 -*-
import io
from pathlib import Path

p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\.env")
b = p.read_text(encoding="utf-8") if p.exists() else ""
print("=== 当前 .env 内容 ===")
print(b[:2000] if b else "(empty)")
print("=== 手工解析 ===")
env = {}
for ln in b.splitlines():
    s = ln.strip()
    if s and not s.startswith("#") and "=" in s:
        k, _, v = s.partition("=")
        env[k.strip()] = v.strip()
for k in ["DEEPSEEK_API_KEY", "KIMI_API_KEY", "OPENAI_API_KEY", "DASHSCOPE_API_KEY"]:
    print(k, "=>", repr(env.get(k)))
