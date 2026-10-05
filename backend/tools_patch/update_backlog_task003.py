# -*- coding: utf-8 -*-
"""TASK-003 完成后更新 BACKLOG.md：时间线 + TASK-003 DONE + TASK-013 READY。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks\BACKLOG.md"
with io.open(p, "r", encoding="utf-8") as f:
    b = f.read()

# 1) 时间线加行
anchor = "> 2026-09-22：TASK-002 完成（见行内备注）：核电巡检主线落地（data_gateway 3 表 / tool_gateway 4 工具 / 「巡检分析 Agent」+IoT 数据源 +2 巡检场景 / mainline 巡检六步链路 / 本体图 4 类实体+32 Link / 工作台前端对齐），新增 test_nuclear_scenario 23 断言 0 失败，全量 20 脚本 0 失败 / 1 SKIP（RLS 待 PG）。"
add = "> 2026-09-23：TASK-003 完成（见行内备注）：本机 PostgreSQL 17 真实验证——Alembic 8 版本链迁移到 head（35 表）+ 27 表 RLS rowsecurity=t 全部启用 + test_rls_isolation PG 模式 6 PASS / 0 FAIL / 0 SKIP（租户互不可见/无上下文安全拒绝/WITH CHECK 拦截）；SQLite 形态全量 20 脚本 19 真跑 0 失败 / 1 SKIP。TASK-013 依赖解锁 READY。"
if anchor in b:
    b = b.replace(anchor, anchor + "\n" + add, 1)
else:
    print("WARN timeline anchor not found")

# 2) TASK-003 行
old3 = "| TASK-003 | Phase 3 生产库 / RLS 真实 PostgreSQL 验证 | P1 | BLOCKED | 需 PostgreSQL 环境（自建/Supabase/Neon 三选一） | Alembic 6 版本链 + 27 表 RLS/FORCE 迁移已就绪，仅差实跑；本机无 PG/psql/Docker |"
new3 = "| TASK-003 | Phase 3 生产库 / RLS 真实 PostgreSQL 验证 | P1 | DONE | — | 2026-09-23 完成：本机 PG 17（postgres/postgres123）Alembic 8 版本链迁移到 head（35 表）+ 27 表 RLS rowsecurity=t 全部启用 + test_rls_isolation PG 模式 6 PASS/0 FAIL/0 SKIP；SQLite 全量 20 脚本 19 真跑 0 失败/1 SKIP |"
if old3 in b:
    b = b.replace(old3, new3, 1)
else:
    print("WARN TASK-003 row not found")

# 3) TASK-013 行解锁
old13 = "| TASK-013 | SecretRef 密钥引用（60-04） | P1 | BLOCKED | TASK-003 | 告别 `.env` 明文；SecretRef/Keychain + PII/Retention/Region 标注 |"
new13 = "| TASK-013 | SecretRef 密钥引用（60-04） | P1 | READY | TASK-003（已 DONE） | 告别 `.env` 明文；SecretRef/Keychain + PII/Retention/Region 标注 |"
if old13 in b:
    b = b.replace(old13, new13, 1)
else:
    print("WARN TASK-013 row not found")

with io.open(p, "w", encoding="utf-8") as f:
    f.write(b)
print("BACKLOG.md updated")
