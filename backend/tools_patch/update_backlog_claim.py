# -*- coding: utf-8 -*-
"""TASK-013 已领取：BACKLOG.md 状态 READY -> IN_PROGRESS。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks\BACKLOG.md"
with io.open(p, "r", encoding="utf-8") as f:
    b = f.read()

old13 = "| TASK-013 | SecretRef 密钥引用（60-04） | P1 | READY | TASK-003（已 DONE） | 告别 `.env` 明文；SecretRef/Keychain + PII/Retention/Region 标注 |"
new13 = "| TASK-013 | SecretRef 密钥引用（60-04） | P1 | IN_PROGRESS | TASK-003（已 DONE） | 2026-09-23 领取（执行顺序第 1 位）；告别 `.env` 明文；SecretRef/Keychain + PII/Retention/Region 标注 |"

if old13 in b:
    b = b.replace(old13, new13, 1)
else:
    print("WARN: TASK-013 row not found")

with io.open(p, "w", encoding="utf-8") as f:
    f.write(b)
print("BACKLOG.md updated: TASK-013 -> IN_PROGRESS")
