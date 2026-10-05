# -*- coding: utf-8 -*-
"""TASK-013：把 admin secrets 路由块移动到 /admin/{slug} 动态路由之前（避免被抢占）。"""
import io
import re

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\api\admin.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

# 定位文件末尾追加的 secrets 块
marker = "# ---------------- SecretRef / Keychain 密钥引用（60-04） ----------------"
if marker not in src:
    print("WARN: secrets marker not found")
    raise SystemExit(1)

# 从 marker 到文件尾
idx = src.index(marker)
block = src[idx:].rstrip() + "\n"
head = src[:idx].rstrip() + "\n"

# 动态路由 /admin/{slug} 的锚点：在其 def 前插入 secrets 块
anchor = "# ---------------- 路由 ----------------\n\n@router.get(\"/admin/{slug}\")"
if anchor not in head:
    print("WARN: dynamic route anchor not found")
    raise SystemExit(1)

# 已存在的块从尾部移除，插入到 anchor 之前
head = head.replace(anchor, block + "\n" + anchor, 1)
with io.open(p, "w", encoding="utf-8") as f:
    f.write(head)
print("OK: secrets routes moved before /admin/{slug}")
