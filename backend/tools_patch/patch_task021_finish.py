# -*- coding: utf-8 -*-
"""TASK-021 收尾：更新 CURRENT.md（DONE + 下一任务 TASK-014）与 BACKLOG.md（✅ + 日志）。"""
from pathlib import Path

D = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks")

# ---------- CURRENT.md ----------
p = D / "CURRENT.md"
s = p.read_text(encoding="utf-8")

old = """# CURRENT TASK
# Task ID
TASK-021
---
# Status
READY（执行顺序第 3 位；TASK-020 已完成）
---
# Title
前端对象语境真实化（P2 收尾：TASK-002 场景 → 全站语境统一）
---
# Goal
把前端各业务页面从"演示/单页"状态提升为"对象语境完整"：
1. 核电巡检主链路页面的对象语境统一（对象中心/数据资产/审批/知识/任务状态机贯穿一致）。
2. 保留销售链路（用户已明确：核电为主链路 + 保留销售链路）。
---
# Scope
1. 走查 TASK-019 已修复的 17 个路由，确认对象语境（对象名/状态/关联/操作按钮）全部真实化。
2. 补齐 P2 遗留页面（按差距清单 3.Y 与 docs/P2-对象语境真实化-运行截图 对齐）。
3. 数据库相关管理页（数据源/数据资产/数据集）与 TASK-020 RLS 租户语义一致（登录用户可见自己租户数据）。
---
# Acceptance Criteria
1. 主链路页面无"演示占位"内容（fake/模拟/占位文案清点归零或明确标注）。
2. 所有功能入口点击不报错（对照 TASK-019 走查清单复检）。
3. 对象详情/列表/操作按钮与后端真实 API 联动，数据来自当前登录租户。
4. SQLite 全量回归 21 脚本 0 失败；PG 模式（如涉及）不回归破坏。
---
# Dependencies
TASK-019（已 DONE）— 全站 17 路由走查 + admin 六页空白修复。
TASK-020（已 DONE）— 生产库 RLS 收口，前端按租户可见数据。
TASK-002（已 DONE）— 核电巡检模拟数据/工具/Agent 真实化，前端语境对齐基础。
---
# Risks
- 前端改动面大，需以 TASK-019 走查清单为准逐页确认，避免回归。
- 与 RLS 联动后，演示租户（company_id=1）与测试租户（admin company_id=3）数据可见性不同，需统一种子口径。
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
.ai/rules/frontend.md
.ai/workflows/feature.md
---
# Completion
完成以后：
更新 CURRENT.md
将本任务状态改为 DONE
然后将下一任务（TASK-014，执行顺序第 4 位）写入 CURRENT.md
---
# 上一任务完成记录（TASK-020 → DONE）"""

new = """# CURRENT TASK
# Task ID
TASK-014
---
# Status
READY（执行顺序第 4 位；TASK-021 已完成）
---
# Title
Logic 决策编排画布（30-03）
---
# Goal
把当前硬编码在 orchestrator 的编排逻辑提升为服务端图 + Logic 画布：
1. 将"编排"从代码态升级为数据态（图定义可查/可改/可版本化）。
2. 前端提供 Logic 画布入口，与对象中心/工作台语境一致。
---
# Scope
1. 服务端图模型（节点/边/触发/条件/动作，参照 .ai/DOMAIN.md Workflow 定义）。
2. 编排执行从固定代码迁移为读图执行（保持现有六步链路行为不变）。
3. 前端 Logic 画布页（只读展示 + 基础编辑，与现有设计系统一致）。
---
# Acceptance Criteria
1. 现有巡检/销售主链路行为回归不变（SQLite 全量 21 脚本 0 失败）。
2. 图定义 API 可查可改，改动后编排按新图执行。
3. 前端画布入口点击不报错，展示与服务端图一致。
---
# Dependencies
TASK-021（已 DONE）— 前端语境统一基线。
TASK-002（已 DONE）— 巡检六步链路现状（迁移目标）。
---
# Risks
- 迁移编排行为有回归风险，需以现有六步链路测试为准逐项核对。
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
.ai/rules/frontend.md
.ai/rules/backend.md
.ai/workflows/feature.md
---
# Completion
完成以后：
更新 CURRENT.md
将本任务状态改为 DONE
然后将下一任务（TASK-015，执行顺序第 5 位）写入 CURRENT.md
---
# 上一任务完成记录（TASK-021 → DONE）
## Completed
前端对象语境真实化（TASK-021）完成，走查结论 + 三处修复：
1. 走查结论：17 路由数据全部来自后端 API（lib/api），无前端硬编码假数据；
   对象中心/工作台/审批/数据资产闭环已具备（对象详情+关联图+AIP/Action+知识关联、
   工作台六步链路+阶段投影+审批 pending、对象 URL 跳转恢复）。
2. 修复①（真实缺陷）：admin/settings 原为进程内存暂存（_SETTINGS），"保存后重启即丢失"。
   新增 SystemSetting 模型（system_settings 表，company_id+key 唯一）+ admin settings 读写落库
   （_load_settings_db 按租户读、save_settings 按租户幂等 upsert）+ 迁移 e5f6a7b8c9d0
   （建表 + PG RLS/FORCE tenant_isolation，双库 upgrade 成功，system_settings RLS=t）。
   前端文案"已保存（演示，重启即丢失）"→"已保存至数据库"。
3. 修复②（语境缺口）：对象中心 TYPE_META 补核电对象类型
   （Area 区域/MonitoringStation 监测站/MetricRecord 监测指标/InspectionRecord 巡检记录），
   类型筛选与对象列表显示中文语境而非英文类型名。
4. 修复③（语境缺口）：工作台结果对象跳转 objectLinkOf 补核电前缀
   （MS→MonitoringStation / INSP→InspectionRecord / MET→MetricRecord / AREA→Area），
   巡检链路结果里的监测站/巡检记录可一键跳对象中心。
## Files
- backend/app/models.py（SystemSetting 模型 + UniqueConstraint 导入）
- backend/app/api/admin.py（_load_settings_db/_settings_payload(company_id)/save_settings 落库/admin_page settings 传租户）
- backend/alembic/versions/e5f6a7b8c9d0_system_settings.py（新建：建表 + PG RLS）
- frontend/app/admin/[slug]/page.tsx（保存文案真实化）
- frontend/app/objects/page.tsx（TYPE_META 核电对象类型）
- frontend/app/workbench/page.tsx（objectLinkOf 核电前缀）
## Tests
SQLite 全量回归：21 脚本 PASS 21 / FAIL 0（test_rls_isolation 无 PG SKIP 1）
PG 模式：test_secret_ref 29/29 + test_rls_isolation 13/13 PASS（含负向 canary/复合租户键）
前端 tsc --noEmit：0 错误
settings 落库闭环实测：SQLite upsert+读回 + payload 覆盖默认 全部通过
结果：PASS
## Risks
- system_settings 仅 company 级隔离（company_id），未做行级细粒度，符合当前租户模型。
- 迁移 e5f6a7b8c9d0 已在生产/测试双库执行；如回滚需 downgrade 配合 DROP TABLE。
## Next
TASK-014 Logic 决策编排画布（本文件当前任务）。
"""

assert old in s, "CURRENT anchor"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK: CURRENT.md -> TASK-014 READY")

# ---------- BACKLOG.md ----------
p = D / "BACKLOG.md"
s = p.read_text(encoding="utf-8")

# 执行顺序表第 3 位
old = "| 3 | TASK-021 | 前端对象语境真实化体验深化 | P1 | TASK-002 ✅ | 用户长期痛点：把巡检工单/监测站/审批做进对象中心与仪表盘 |"
new = "| 3 | TASK-021 | 前端对象语境真实化体验深化 | P1 | TASK-002 ✅ | ✅ 2026-09-23 完成（见 Backlog 行备注），下一个开工 TASK-014 |"
assert old in s, "order row 3"
s = s.replace(old, new, 1)

# Backlog Items 行
old = "| TASK-021 | 前端对象语境真实化体验深化 | P1 | BACKLOG | TASK-002（已 DONE） | 2026-09-23 登记（用户长期痛点）：把巡检工单/监测站/审批做进对象中心与仪表盘，让页面不再\"像演示\" |"
new = "| TASK-021 | 前端对象语境真实化体验深化 | P1 | DONE | TASK-002（已 DONE） | 2026-09-23 完成：走查结论=17 路由数据全走后端 API 无前端假数据、闭环已具备；修复① admin/settings 落库（SystemSetting 表 + admin 读写改 DB + 迁移 e5f6a7b8c9d0 双库成功 + 文案去\"重启即丢失\"）；修复② 对象中心 TYPE_META 补核电对象（Area/MonitoringStation/MetricRecord/InspectionRecord 中文语境）；修复③ 工作台 objectLinkOf 补核电前缀（MS/INSP/MET/AREA 可跳对象中心）；SQLite 21/21 + PG 13/13 + tsc 0 错误 |"
assert old in s, "backlog row 21"
s = s.replace(old, new, 1)

# 顶部日志
old = "> 2026-09-23：TASK-003 完成（见行内备注）"
new = "> 2026-09-23：TASK-021 完成（见行内备注）：admin/settings 落库（SystemSetting 表+迁移 e5f6a7b8c9d0 双库）+ 对象中心核电对象中文语境（TYPE_META）+ 工作台核电对象跳转（objectLinkOf MS/INSP/MET/AREA）；SQLite 全量 21 脚本 0 失败 + PG 13/13 + tsc 0 错误。\n> 2026-09-23：TASK-003 完成（见行内备注）"
assert old in s, "log anchor"
s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("OK: BACKLOG.md updated")
