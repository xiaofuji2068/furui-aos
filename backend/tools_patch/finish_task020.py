# -*- coding: utf-8 -*-
"""TASK-020 完成：更新 CURRENT.md → TASK-020 DONE + 写入 TASK-021 READY。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks\CURRENT.md"

content = '''# CURRENT TASK
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
# 上一任务完成记录（TASK-020 → DONE）
## Completed
Phase 3 收尾三件事全部完成：
1. 应用层 RLS 贯通：受限角色 furui_app（双库已建+全表 GRANT）；对齐迁移 d4e5f6a7b8c9
   （补 4 张缺失表 + 31 张直列 RLS/FORCE + 3 张子表 EXISTS 复合租户键 policy + 5 张系统表豁免）
   生产库/测试库均 upgrade 成功（head=d4e5f6a7b8c9，40 表，34 表 RLS）。
2. 复合租户键 + 负向 canary：agent_skills/agent_steps/agent_stages 经父表 EXISTS 隔离；
   test_rls_isolation 扩展至 13 断言（全表收口×2、OR/LIKE 绕过×2、JOIN、子表复合键、子表越权写）PG 模式 13/13 PASS。
3. default 列收口：ontology/admin 租户硬编码显式化（company_id 参数化 + user.company_id 注入）；
   4 张补表 server_default 与 ORM 语义对齐；审计报告 docs/TASK-020-default审计.md（A 类 192 / B 类 215，分批处理）。
## Files
- backend/alembic/versions/d4e5f6a7b8c9_rls_phase3_consolidation.py（新建/重写：幂等守卫 + 全库 RLS）
- backend/app/ontology/__init__.py（租户显式化：_upsert_db_object/_upsert_db_link/_write_outbox/project_outbox/get_graph_snapshot/seed_ontology）
- backend/app/api/ontology_api.py（snapshot/project 路由 user.company_id）
- backend/app/api/admin.py（eval_contract upsert company_id 显式化）
- backend/tests/test_rls_isolation.py（扩展 13 断言）
- docs/TASK-020-default审计.md（default 差异清单）
## Tests
SQLite 全量回归：21 脚本 PASS 21 / FAIL 0（RLS 无 PG 时 SKIP 1）
PG 模式：test_secret_ref 29/29 PASS；test_rls_isolation 13/13 PASS
结果：PASS
## Risks
- 5 张系统表豁免（companies/ontology_types/permissions/role_permissions/user_roles）未启用 RLS：
  RBAC/元数据表系统级共享，如需按租户隔离需另行评估。
- B 类 215 处 NOT NULL 无 server_default 列（裸 SQL 写入会违反约束）留待分批对齐。
## Next
TASK-021 前端对象语境真实化（本文件当前任务）。
'''
with io.open(p, "w", encoding="utf-8") as f:
    f.write(content)
print("OK: CURRENT.md updated")
