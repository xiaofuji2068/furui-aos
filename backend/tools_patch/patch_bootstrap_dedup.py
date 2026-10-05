# -*- coding: utf-8 -*-
"""修复 _seed_agents：删除残留的无条件全量创建循环（560-590 行），避免重复建 Agent。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\bootstrap.py"
with open(P, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 定位：_seed_agents 函数内的第一段增量循环的 commit 结束（行索引），到 def _seed_tools_and_approvals 前
# 特征：从 "    for a in AGENT_SEED:\n        agent = Agent(\n"（第二次出现）到 "    db.commit()\n\n\n"
i_start = None
count = 0
for i, ln in enumerate(lines):
    if ln == "    for a in AGENT_SEED:\n":
        count += 1
        if count == 2:
            i_start = i
            break
assert i_start is not None, "second loop not found"

# 找到该循环后的 "    db.commit()\n\n\n"（函数结尾）
i_end = None
for j in range(i_start, len(lines)):
    if lines[j] == "    db.commit()\n" and lines[j+1] == "\n" and lines[j+2] == "\n":
        i_end = j
        break
assert i_end is not None, "commit end not found"

del lines[i_start:i_end+3]
with open(P, "w", encoding="utf-8") as f:
    f.writelines(lines)
print(f"DELETED lines {i_start+1}..{i_end+3}")
