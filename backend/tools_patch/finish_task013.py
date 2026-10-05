# -*- coding: utf-8 -*-
"""TASK-013 收尾：CURRENT.md 标记 DONE 并写入 TASK-020；BACKLOG.md 同步状态。"""
import io

# ---------- 1) CURRENT.md ----------
p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks\CURRENT.md"
with io.open(p, "r", encoding="utf-8") as f:
    cur = f.read()

new_cur = """# CURRENT TASK
# Task ID
TASK-020
---
# Status
READY（执行顺序第 2 位；TASK-013 已完成）
---
# Title
Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口
---
# Goal
把 Phase 3 生产库/RLS 的剩余三件事收口：
1. 应用层 RLS 贯通：app 用受限角色连接 PG，登录链路 set_tenant_context 全流程实测（Agent/API 经受限连接写库均受 RLS 约束）。
2. 复合租户键 / 负向 canary：存在非 company_id 归属的表（如 company_id 缺失或业务键复合）补租户键，并加入「负向 canary」测试（租户 B 无论如何构造都读不到租户 A 数据）。
3. default 列收口：系统其余 Python 侧 default（非 server_default）排查，落库语义与 PG 对齐。
---
# Scope
1. RLS 贯通：数据库连接改为受限角色（非 superuser），set_tenant_context 覆盖登录/API/Agent 全链路；app 查询与写入受 RLS 约束。
2. 复合租户键：排查无 company_id 或需复合归属的表，补齐租户键与 RLS policy。
3. 负向 canary：test_rls_isolation 扩展负向用例（复杂 WHERE/JOIN/子查询/跨表读均不可见）。
4. default 收口：Python default 与 server_default 对齐审计，列表输出差异。
---
# Acceptance Criteria
1. PG 形态：受限角色连接下，登录用户/API/Agent 写库均受 RLS 约束；无上下文访问安全拒绝。
2. 复合租户键表补齐并可被 RLS 隔离；负向 canary 全部通过（B 租户读不到 A 的任何形态）。
3. default 列审计表输出，SQLite/PG 行为一致（或差异已记录）。
4. 全量回归：SQLite 21 脚本 0 失败 / 1 SKIP（RLS 待 PG）；PG 模式 test_rls_isolation + 新增用例 0 失败。
---
# Dependencies
TASK-003（已 DONE）— 生产库 PG 已迁移到 head（c3d4e5f6a7b8，36 表 + 28 表 RLS）。
TASK-013（已 DONE）— Keychain 已落库并接入 RLS（secret_entries 含 tenant_isolation policy）。
---
# Risks
- 受限角色需要重建连接配置，本地开发/演示（SQLite）不受影响，但 PG 形态需重新验证全链路。
- 复合租户键表若有历史数据，补键需幂等迁移；canary 测试需避免依赖特定执行顺序。
- default 列收口可能涉及多模块，逐表审计，避免过度改动。
---
# Development Rule
开始开发之前：
必须读取：
.ai/README.md
.ai/PROJECT.md
.ai/PRINCIPLES.md
.ai/ARCHITECTURE.md
.ai/DOMAIN.md
.ai/AI.md
.ai/API.md
.ai/SECURITY.md
.ai/workflows/feature.md
.ai/rules/coding.md
.ai/rules/backend.md
---
# Completion
完成以后：
更新 CURRENT.md
将本任务状态改为 DONE
然后将下一任务（TASK-021，执行顺序第 3 位）写入 CURRENT.md
"""
with io.open(p, "w", encoding="utf-8") as f:
    f.write(new_cur)
print("OK: CURRENT.md -> TASK-020 READY")

# ---------- 2) BACKLOG.md ----------
p2 = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks\BACKLOG.md"
with io.open(p2, "r", encoding="utf-8") as f:
    back = f.read()

# 2a) 执行顺序表：第 1 位标记完成
old_line = "| 1 | TASK-013 | SecretRef 密钥引用（60-04） | P1 | TASK-003 ✅ | 已 READY，下一个开工 |"
new_line = "| 1 | TASK-013 | SecretRef 密钥引用（60-04） | P1 | TASK-003 ✅ | ✅ 2026-09-23 完成（见 Backlog 行备注），下一个开工 TASK-020 |"
if old_line in back:
    back = back.replace(old_line, new_line, 1)
else:
    print("WARN: order row1 not found")

old_line2 = "| 2 | TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | TASK-003 ✅ | 差距清单 3.Y.2 剩余三件事 |"
new_line2 = "| 2 | TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | TASK-003 ✅ | 已 READY，下一个开工 |"
if old_line2 in back:
    back = back.replace(old_line2, new_line2, 1)

# 2b) TASK-013 Backlog 行：IN_PROGRESS -> DONE + 完成备注
old_t13 = "| TASK-013 | SecretRef 密钥引用（60-04） | P1 | IN_PROGRESS | TASK-003（已 DONE） | 2026-09-23 领取（执行顺序第 1 位）；告别 `.env` 明文；SecretRef/Keychain + PII/Retention/Region 标注 |"
new_t13 = "| TASK-013 | SecretRef 密钥引用（60-04） | P1 | DONE | TASK-003（已 DONE） | 2026-09-23 完成：SecretEntry 模型（secret_entries 表 + PII/Retention/Region 标注）+ store_secrets Keychain（set/get/list 脱敏/delete/migrate .env→Keychain 幂等 + resolve_llm_key Keychain 优先 .env 兜底）+ admin secrets 4 路由（require_perm tool:config，列表绝回明文）+ save_model_keys 同步写 Keychain + Alembic c3d4e5f6a7b8（secret_entries + RLS/FORCE）；附带修复 admin._BACKEND_DIR 路径 bug（原指向 backend/app/.env，模型 Key 保存写错位置）与 ensure_column 跨方言；SQLite 全量 21 脚本 0 失败/1 SKIP（test_secret_ref 29 PASS），PG 模式 test_secret_ref 29 PASS + test_rls_isolation 6 PASS，生产库 furui_aios 迁移 head（36 表，secret_entries RLS 启用） |"
if old_t13 in back:
    back = back.replace(old_t13, new_t13, 1)
else:
    print("WARN: TASK-013 backlog row not found")

# 2c) TASK-020 Backlog 行：BACKLOG -> READY
old_t20 = "| TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | BACKLOG | TASK-003（已 DONE） | 2026-09-23 登记（差距清单 3.Y.2 剩余）：① app 用受限角色连接 + set_tenant_context 登录链路实测 ② 复合租户键/负向 canary ③ 系统收口其余 Python default 列 |"
new_t20 = "| TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | READY | TASK-003（已 DONE） | 2026-09-23 登记（差距清单 3.Y.2 剩余），TASK-013 完成后领取：① app 用受限角色连接 + set_tenant_context 登录链路实测 ② 复合租户键/负向 canary ③ 系统收口其余 Python default 列 |"
if old_t20 in back:
    back = back.replace(old_t20, new_t20, 1)
else:
    print("WARN: TASK-020 backlog row not found")

# 2d) 顶部日志追加一行
log_old = "> 2026-09-23：TASK-003 完成（见行内备注）"
log_new = "> 2026-09-23：TASK-013 完成（见行内备注）：SecretRef/Keychain 落库（secret_entries + RLS）并接线 admin 密钥管理；SQLite 全量 21 脚本 0 失败/1 SKIP；PG 模式 test_secret_ref 29 PASS + test_rls_isolation 6 PASS；生产库 furui_aios 迁移到 head（36 表，secret_entries RLS 启用）。TASK-020 依赖解锁 READY。\n> 2026-09-23：TASK-003 完成（见行内备注）"
if log_old in back:
    back = back.replace(log_old, log_new, 1)

with io.open(p2, "w", encoding="utf-8") as f:
    f.write(back)
print("OK: BACKLOG.md updated")
