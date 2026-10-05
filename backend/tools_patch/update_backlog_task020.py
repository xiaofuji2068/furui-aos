# -*- coding: utf-8 -*-
"""TASK-020 完成：更新 BACKLOG.md（顺序表第 2 位 ✅ + 行状态 DONE + 顶部日志）。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks\BACKLOG.md"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

# 1) 顶部日志追加
old = "> 2026-09-23：TASK-013 完成"
new = "> 2026-09-23：TASK-020 完成（见行内备注）：受限角色 furui_app 双库 + 全库 34 表 RLS/FORCE 收口（对齐迁移 d4e5f6a7b8c9：补 4 张缺失表幂等 + 31 直列 + 3 子表复合租户键 EXISTS policy + 5 系统表豁免）；租户硬编码显式化（ontology/admin eval-contract）；test_rls_isolation 扩展 13 断言 PG 全 PASS（负向 canary OR/LIKE/JOIN + 子表复合键 + 子表越权写拦截）；default 审计 docs/TASK-020-default审计.md（A 192/B 215 分批）；SQLite 全量 21 脚本 0 失败；生产/测试库 head=d4e5f6a7b8c9。\n> 2026-09-23：TASK-013 完成"
assert old in src, "1"
src = src.replace(old, new, 1)

# 2) 执行顺序表第 2 位
old = "| 2 | TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | TASK-003 ✅ | 已 READY，下一个开工 |"
new = "| 2 | TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | TASK-003 ✅ | ✅ 2026-09-23 完成（见 Backlog 行备注），下一个开工 TASK-021 |"
assert old in src, "2"
src = src.replace(old, new, 1)

# 3) Backlog Items 行状态
old = "| TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | READY | TASK-003（已 DONE） | 2026-09-23 登记（差距清单 3.Y.2 剩余），TASK-013 完成后领取：① app 用受限角色连接 + set_tenant_context 登录链路实测 ② 复合租户键/负向 canary ③ 系统收口其余 Python default 列 |"
new = "| TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | DONE | TASK-003（已 DONE） | 2026-09-23 完成：受限角色 furui_app（双库+全表 GRANT）；对齐迁移 d4e5f6a7b8c9（幂等补 4 缺失表 agent_stages/data_datasets/inspection_work_orders/task_reviews + 31 直列 RLS/FORCE + 3 子表 agent_skills/agent_steps/agent_stages 复合租户键 EXISTS policy + 5 系统表豁免 companies/ontology_types/permissions/role_permissions/user_roles）；生产/测试库 40 表 34 RLS head 一致；租户硬编码显式化（ontology _upsert_*/outbox/snapshot/seed + admin eval_contract user.company_id）；test_rls_isolation 扩展至 13 断言 PG 13/13 PASS（全表收口×2、负向 canary OR 1=1/LIKE 绕过×2、JOIN 只见 A、子表复合键只见 A、子表越权写 WITH CHECK 拦截）；default 审计落档（A 192 处 Python default 无 server_default / B 215 处 NOT NULL 无 server_default，分批处理）；SQLite 全量 21 脚本 0 失败/1 SKIP |"
assert old in src, "3"
src = src.replace(old, new, 1)

with io.open(p, "w", encoding="utf-8") as f:
    f.write(src)
print("OK: BACKLOG.md updated")
