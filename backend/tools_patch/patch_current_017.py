# -*- coding: utf-8 -*-
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks\CURRENT.md"
s = io.open(p, encoding="utf-8").read()

# 将文件尾部 TASK-016 READY 块替换为 TASK-017 READY 块（当前任务切换）
old_tail = """---
# Title
平台内核与资产装配（50 全系）
# Title
平台内核与资产装配（50 全系）
---
# Goal
把「可复用的 AI 能力/页面/流程」提升为可打包、可安装、可解析的资产装配体系：
1. Bundle / Registry / Resolver：AI 能力、页面、流程以 Bundle 打包注册，运行时按需解析装配。
2. Installation / Plugin：租户级安装与覆盖（多企业各自装配，不互相污染）。
3. Manifest / 签名：Bundle 元信息（名称/版本/依赖/权限声明）+ 完整性校验。
---
# Scope
1. 资产模型：Bundle 定义（Manifest）、Registry 注册表、Resolver 解析器。
2. 安装链路：租户安装/卸载/覆盖/升级（幂等）。
3. 签名与校验：Manifest 元信息 + 防篡改校验。
4. 前端：资产中心页（浏览/安装/版本/依赖关系展示）。
---
# Acceptance Criteria
1. 可定义一份 Bundle（Manifest + 内容）并注册进 Registry。
2. 租户可安装 Bundle 并解析出可用能力（页面/流程/工具）。
3. 安装幂等、覆盖安全、卸载干净（不破坏其他租户）。
4. 全量回归 0 失败；前端 tsc 0 错误。
---
# Dependencies
TASK-015（已 DONE）— 低代码页面可被 Bundle 引用为资产。
TASK-014（已 DONE）— Logic 图可被 Bundle 引用为流程资产。
---
# Risks
- 资产装配与现有模块（pages/logic/tools）的边界需明确：Bundle 是「元层」而非「业务层」。
- 租户覆盖语义（覆盖 vs 派生）需要一次拍板，开工前与用户确认。
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
然后将下一任务（TASK-017，执行顺序第 7 位）写入 CURRENT.md
"""

new_tail = """---
# Task ID
TASK-017
---
# Status
IN_PROGRESS（执行顺序第 7 位；2026-09-29 开工，前序 TASK-016 已 DONE）
---
# Title
交付发布与部署形态（70/80 全系）
---
# Goal
把「如何交付与发布」从本地开发形态升级为可审计的私有化交付体系：
1. 部署分区与信任边界（70-01）、节点/端口/版本编排（70-02）。
2. 中心边缘协作 Hub-Spoke（70-03）。
3. Apollo 交付：Release/Channel/Change/SBOM/签名（80-01）、Promotion/Recall（80-02）。
4. 升级迁移与回滚（80-03，基于已有 Alembic 8 版本链）。
---
# Scope
1. docs/DEPLOYMENT.md：部署分区 / 网络信任边界 / 端口与环境变量引用清单。
2. Dockerfile.backend / Dockerfile.frontend + docker-compose.yml（backend+frontend+postgres）+ .env.production 模板
   + 静态校验（本机无 Docker，产出标准文件 + YAML 结构断言，不实测容器）。
3. docs/HUB-SPOKE.md + EdgeSite 最小闭环（edge_sites 表 + 注册/心跳/同步策略 API，RLS 租户隔离）。
4. Release 模型（releases 表：code 唯一、version、channel、manifest、sbom、signature、status）
   + 5 API（list/get/create/promote/recall，tool:config）+ sha256 签名校验。
5. SBOM 生成脚本 tools/sbom.py：requirements.txt + package-lock.json → SPDX-lite sbom.json。
6. docs/UPGRADE.md：Expand/Backfill/Contract + alembic upgrade/downgrade 双库流程 + 补偿清单。
---
# Acceptance Criteria
1. 部署文档覆盖分区/边界/端口/变量，可据此在客户内网完成部署。
2. Compose/Dockerfile 文件结构有效（YAML 可解析、服务/依赖/健康检查齐全）。
3. Release 可创建/发布/召回，签名随 Release 落库并可通过 API 校验。
4. SBOM 可一键生成（后端+前端依赖可溯源）。
5. EdgeSite 注册/心跳闭环可用（RLS 隔离）。
6. 全量回归 0 失败；前端 tsc 0 错误。
---
# Dependencies
TASK-016（已 DONE）— Bundle/Registry 签名模式复用为 Release 底座。
TASK-003（已 DONE）— Alembic 迁移链与双库（生产 furui_aios / 测试 furui_aios_test，head=8c9d0e1f2a3b）。
---
# Risks
- 本机无 Docker/Helm：Compose/Helm 只能静态校验，真实容器启动需在部署机验证。
- 核电客户私有化多为内网离线：Hub-Spoke 的 Ferry 同步复用现有 outbox，不引入外部队列依赖。
- Release 状态迁移（promote/recall）需显式白名单，防止非法跳态。
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
然后将下一任务（TASK-018，执行顺序第 8 位）写入 CURRENT.md
"""

if old_tail not in s:
    raise SystemExit("tail anchor missing")
s = s.replace(old_tail, new_tail, 1)
io.open(p, "w", encoding="utf-8").write(s)
print("CURRENT TASK-017 OK")
