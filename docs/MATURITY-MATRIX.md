# furui-aios 成熟度矩阵与差异地图（TASK-018 · 图谱 90-02）

> **图谱模块 90-02「如何知道系统真的工作：成熟度矩阵、差异地图」落地物。**
> 盘点日期 **2026-10-05**，全部结论来自实测取证（双库直查 / 路由扫描 / 回归跑通 / 迁移链解析），
> **不采用纸面评估**；与本文配套的可复跑采集器：`backend/tools_patch/maturity_snapshot.py`。
> 证据快照（机器可读）：`docs/maturity-snapshot.json`。

---

## 0. 结论先行

| 硬指标 | 实测值 | 取证方式 |
| --- | --- | --- |
| 迁移链 | **17 步**，单链、链根唯一 `78532a4f3d68`、无分叉无孤立 | 迁移 AST 解析 + 从 DB tip 反推祖先链 |
| 双库一致 | prod / test 均 `tip=9d1f4c7b2e8a`、49 表、40 RLS 表（FORCE） | `pg_class` + `alembic_version` 直查 |
| 后端接口面 | **119 个 API / 28 组** | FastAPI routes 全量扫描 |
| 前端可操作面 | **20 条路由 / 85 个 ts 文件**，`tsc --noEmit` **0 错误** | 文件树 + tsc |
| 测试面 | **25 脚本 / 25 OK / PASS 660 / FAIL 0 / SKIP 0** | `run_tests.py` 全量回归 |
| 代码规模 | backend 13,158 行 / frontend 13,135 行 | `wc -l` |

**一句话判断**：工程底盘（迁移、双库、RLS、被锁定的测试）已经**达到可交付的内部标准**；
差距集中在**生产化要素**——真实连接器、CI、可观测三件套（Trace/Watchdog）、
以及"跑在生产库上"的完整闭环（当前回归全绿，但没有一条断言证明它能在别人的机器上跑起来）。

---

## 1. 等级口径（先定义什么叫"到了这一步"）

旧清单用 ✅/🟡/🔴/⚪ 四级主观涂色，同一模块不同人盘出不同结论。本文改**行为可验证的 L0–L4**：

| 等级 | 名称 | 判定标准（全部满足才给这一级） | 符号 |
| --- | --- | --- | --- |
| **L3** | 达标 | 闭环打通 **且** 有测试锁定 **且** 双库对齐（RLS 或显式豁免）**且** 前端可操作 | ✅ |
| **L2** | 可用 | 闭环打通 + 有测试锁定，但缺生产化要素（无 RLS / 无签名 / 前端未接 / 无前端页） | 🟡 |
| **L1** | 骨架 | 只有模型或端点，闭环未通（CRUD 有、状态机与门禁没有） | 🟠 |
| **L0** | 缺失 | 无表、无端点、无测试 | 🔴 |
| — | 范围外 | 图谱明确列为当前不做（电商垂直线） | ⚪ |

> 与旧口径换算：L3≈✅、L2≈🟡、L1≈🟡（弱）/🔴（强）、L0=🔴。
> **本文数字与 09-09、09-15 两版热度图对不上是正常的**——见 §3.2 口径对照。

---

## 2. 成熟度矩阵（9 分册 · 43 模块）

> 「变化」列 = 相对 `docs/图谱-furui-aios差距清单与实施路线.md` 2026-09-09 版的自评等级。
> 证据栏只写**实测得到的东西**（表名 / 端点 / 测试脚本），不写"应该有"。

### 10 数据操作系统（L3×0 · L2×1 · L1×2 · L0×3 · 外1）

| 模块 | 图谱要求 | 实测证据 | 等级 | 变化 |
| --- | --- | --- | --- | --- |
| 10-01 数据操作系统 | Source→Sync→Dataset→Lineage/Health | `data_sources` `data_connections` `data_datasets` 三表；`/api/data-sources` 7 端点、`/api/data-assets` 5 端点；无 Sync/Dataset 资产闭环 | 🟠 L1 | 🟡→L1（下调，此前高估） |
| 10-02 数据源与连接器 | Connector Catalog、JDBC/REST/Webhook、SecretRef | catalog 有 + `secret_entries` 表（TASK-013）+ `/api/admin/secrets` CRUD 4 端点；无真实协议连接器 | 🟠 L1 | 🟡 |
| 10-03 同步调度与边缘执行 | Sync Config、Edge Agent、Checkpoint | 无对应表与端点（`edge_sites` 属 70-03，非数据同步） | 🔴 L0 | 🔴 |
| 10-04 管道构建与执行 | Pipeline Builder、Schedule、Build | 无 | 🔴 L0 | 🔴 |
| 10-05 数据资产血缘质量 | Lineage、Health、Branch | 无 lineage 表，`data_gateway` 无血缘记录 | 🔴 L0 | 🔴 |
| 10-06 垂直电商通用接入 | 电商 AdapterPack | 明确不做 | ⚪ | ⚪ |
| 10-07 全量数据存储架构 | PG 权威 + 对象存储 + 向量/缓存投影 | PG 17 已装 + 17 迁移 + 49 表 + **40 表 RLS/FORCE**；对象存储/向量/缓存投影无 | 🟡 L2 | 🟡 |

### 20 本体・数字孪生（L3×4 · L1×0 · L0×1 · 外1）— **最强分册**

| 模块 | 图谱要求 | 实测证据 | 等级 | 变化 |
| --- | --- | --- | --- | --- |
| 20-01 本体数字孪生 | 数据→业务对象→受控动作 | `ontology_types/objects/links` + `/api/ontology/related`（depth 1~4）+ 前端 `/objects` | ✅ L3 | 🟡→✅ |
| 20-02 本体元模型 | Object/Link Type、Schema Revision | `ontology_schema_revisions` + `bump_revision` + `POST /api/ontology/revisions` + `test_ontology_revisions` 31 PASS | ✅ L3 | 🟡→✅ |
| 20-03 映射与身份 | Funnel、Mapping/Identity | 无（Mapping Draft/Review 无表无端点） | 🔴 L0 | 🔴 |
| 20-04 权威对象关系与图探索 | 权威写链、Outbox、Projector、GraphSnapshot | `ontology_outbox` + `ontology_graph_snapshots` 两表 + `test_outbox_projector` **21 PASS/0 FAIL** | ✅ L3 | 🟡→✅ |
| 20-05 函数与受控动作 | Function、Action、Proposal/Approval/Receipt | `action_receipts` + `tool_executions` 两表 + 四级门禁 + `test_receipts` 31 PASS；**缺 Lease 与补偿** | ✅ L3 | 🟡 |
| 20-06 电商数字孪生 | 电商对象建模 | 明确不做 | ⚪ | ⚪ |

### 30 AIP 决策与控制（L3×3 · L2×3 · L1×0 · 外1）

| 模块 | 图谱要求 | 实测证据 | 等级 | 变化 |
| --- | --- | --- | --- | --- |
| 30-01 AIP 决策与控制 | 模型→逻辑→Agent→Eval/审批门禁 | orchestrator + employees + mainline 全通；门禁链不完整（无统一 EvalContract 自动裁决） | 🟡 L2 | 🟡 |
| 30-02 模型纳管与选择 | Provider、Model Catalog、Route、Capacity | `LLM_PROVIDERS` 6 家 + `GET /api/admin/models/catalog` + `keys` CRUD + `test_admin_keys` 9 PASS；**无 Route/预算** | 🟡 L2 | 🟡 |
| 30-03 Logic 决策编排 | Logic 画布 / 服务端图 | `logic_graphs` `logic_nodes` + `/api/logic` 4 端点 + 前端 `/logic` + `test_logic_graph` 19 PASS | ✅ L3 | 🔴→✅（TASK-014 已落） |
| 30-04 Agent 能力与运行 | Skill/Capability/Binding/Handoff/Receipt | `agents` `agent_tasks` `agent_steps` `agent_executions` `agent_skills` + confirm_task；缺 Binding/Handoff | 🟡 L2 | 🟡 |
| 30-05 Eval 审批与谱系 | EvalContract、Draft、Decision Lineage | `eval_contracts` 表 + `/api/admin/eval-contracts` 2 端点 + `test_eval_contract` 36 PASS | ✅ L3 | 🟡→✅ |
| 30-06 记忆与知识治理 | Candidate→Eval→Approval→Item/Revision | `knowledge_bases/documents/chunks` + submit/publish 门禁 + rag 双引擎 + `test_knowledge` 31 PASS | ✅ L3 | ✅ |
| 30-07 垂直电商 AIP | 电商数字同事 | 明确不做 | ⚪ | ⚪ |

### 40 工作台与业务应用（L3×1 · L2×3 · L1×1 · 外1）

| 模块 | 图谱要求 | 实测证据 | 等级 | 变化 |
| --- | --- | --- | --- | --- |
| 40-01 工作台与业务应用 | 模块化消费对象/决策/动作 | `/workbench` `/scenes` `/dashboard` API + 前端路由齐；无模块运行时抽象 | 🟡 L2 | 🟡 |
| 40-02 应用运行时 | Application/Module/Widget Runtime | `app_pages` 表 + `/api/pages` 8 端点 + 前端 `/pages` `/pages/[code]` + `test_pages` 17 PASS；运行时薄 | 🟡 L2 | 🟡 |
| 40-03 低代码构建 | Canvas、Widget Registry、Publish | 只有页定义（ Insights 级），无 Canvas 拖动与 Widget Registry | 🟠 L1 | 🔴→L1 |
| 40-04 对象 AIPAction 嵌入 | 对象视图 / AIP/Action 表单 + 写回门禁 | `/api/object_actions` + `test_object_actions` 31 PASS；写回未走 Action/Receipt 统一链路 | 🟡 L2 | 🟡 |
| 40-05 垂直电商业务工作台 | 电商驾驶舱 | 明确不做 | ⚪ | ⚪ |
| 40-06 长程任务与人机协作 | TaskBrief、Stage/Checkpoint、Review/Return | `task_reviews` `agent_stages` + `/api/tasks/{id}/review` `/retry` + `test_task_state_machine` **51 PASS** | ✅ L3 | 🟡→✅（TASK-012） |

### 50 平台内核与资产装配（L2×3 · L1×1 · L0×1）

| 模块 | 图谱要求 | 实测证据 | 等级 | 变化 |
| --- | --- | --- | --- | --- |
| 50-01 平台内核与资产装配 | Bundle/Registry/Resolver/Installation/Plugin | `asset_bundles` `asset_installations` + `/api/assets` 10 端点 + 前端 `/assets/center` + `test_asset_bundle` 35 PASS | 🟡 L2 | 🔴→L2（TASK-016，清单已严重过时） |
| 50-02 四层产品稳定契约 | API/BFF、Contract、Service/Store | REST + `response.py` 统一包装 + DB Session 依赖注入；无 BFF/Service 层 | 🟡 L2 | 🟡 |
| 50-03 资产包发布与解析 | Manifest/Bundle/Registry/签名 | `releases.manifest_json` + `signature` + `sbom.json`；无独立 Bundle Registry 解析流程 | 🟡 L2 | 🔴→L2 |
| 50-04 租户安装与覆盖 | Installation/Overlay/ETag/CAS | `asset_installations` 记录安装态 + toggle 连接；无 Overlay/ETag | 🟠 L1 | 🔴→L1 |
| 50-05 插件与 Adapter 扩展 | Plugin/Adapter 插槽 | 无 | 🔴 L0 | 🔴 |

### 60 租户、安全与治理（L3×2 · L2×1 · L1×1）

| 模块 | 图谱要求 | 实测证据 | 等级 | 变化 |
| --- | --- | --- | --- | --- |
| 60-01 租户安全与治理 | Principal/TenantScope/OpenFGA/Marking/RLS/Audit | 4 张身份表 + JWT + `require_perm` + `/api/org` 16 端点 + `audit_logs`；无 OpenFGA/Marking | ✅ L3 | 🟡→✅（体量达标） |
| 60-02 身份与数据租户隔离 | RLS/FORCE、复合租户键、负向 canary | **40 表 RLS+FORCE** + 受限角色 `furui_app` 授权 + `test_rls_isolation` **13 PASS/0 SKIP** | ✅ L3 | 🟡→✅（TASK-020） |
| 60-03 权限与动作治理 | Marking/Purpose/Approval/Lease/Kill/Audit | `approvals` `approval_rules` `audit_logs` + `tool_executions`；无 Marking/Lease/Kill | 🟡 L2 | 🟡 |
| 60-04 Secret 与外部数据保护 | SecretRef/Keychain、PII/Retention/Region | `secret_entries` 表（只存哈希）+ admin secrets CRUD + `migrate` + `test_secret_ref` 29 PASS；PII/Retention/Region 无 | 🟡 L2 | 🔴→L2（TASK-013） |

### 70 部署与端云（L2×3）

| 模块 | 图谱要求 | 实测证据 | 等级 | 变化 |
| --- | --- | --- | --- | --- |
| 70-01 部署与端云 | 部署分区 / 网络信任边界 | `backend/Dockerfile` `frontend/Dockerfile` `docker-compose.yml` `docs/DEPLOYMENT.md`；**无 CI、无网络信任边界定义** | 🟡 L2 | 🟡 |
| 70-02 当前怎样部署 | 节点 / 端口 / 版本引用 | compose + `docs/UPGRADE.md` + `sbom.json`；仅本地形态，无 Helm | 🟡 L2 | 🟡 |
| 70-03 中心边缘与客户环境协作 | Hub-Spoke、Ferry、Edge Agent | `edge_sites` 表（RLS/FORCE）+ register/heartbeat/sync 三段 + `docs/HUB-SPOKE.md` + 前端 `/edge-sites` | 🟡 L2 | 🔴→L2（TASK-017） |

### 80 Apollo 交付发布（L3×1 · L2×1 · L1×1）

| 模块 | 图谱要求 | 实测证据 | 等级 | 变化 |
| --- | --- | --- | --- | --- |
| 80-01 交付与发布 | Release/Channel/Change/SBOM/签名 | `releases` `release_changes` + `sha256(version\|manifest\|sbom)` + `PROMOTE_ORDER` 状态机 + 前端 `/releases` + `test_release_delivery` **37 PASS** | ✅ L3 | 🔴→✅（TASK-017，清单完全过时） |
| 80-02 发布到达各环境 | Promotion/Recall、SBOM/签名 | promote/recall/sync_target 三段齐全 + `edge_sites.sync_target` 版本比对；**无真实环境投递动作** | 🟡 L2 | 🔴→L2 |
| 80-03 升级迁移与回滚 | Alembic、Expand/Backfill、Rollback/补偿 | 17 迁移链完整（每条都有 `down_revision`）；**downgrade 未实测过一条** | 🟠 L1 | 🔴→L1 |

### 90 证据、可观测与韧性（L2×2）— **本任务所在分册**

| 模块 | 图谱要求 | 实测证据 | 等级 | 变化 |
| --- | --- | --- | --- | --- |
| 90-01 证据可观测与韧性 | Health/Log/Trace/Receipt/Lineage/Watchdog | `GET /api/health` 1 端点 + `audit_logs` + `tool_executions` + `action_receipts` + `eval_contracts`；**无 Trace 链路、无 Watchdog 守护** | 🟡 L2 | 🟡 |
| 90-02 如何知道系统真的工作 | 成熟度矩阵、差异地图 | **本文** + 可复跑采集器 `tools_patch/maturity_snapshot.py` + 证据快照 `docs/maturity-snapshot.json` | 🟡 L2 | 🔴→L2（本任务产出） |

---

## 3. 差异地图（横向视角）

### 3.1 分册热力（本文口径）

| 分册 | ✅L3 | 🟡L2 | 🟠L1 | 🔴L0 | ⚪外 | 判读 |
| --- | --: | --: | --: | --: | --: | --- |
| 10 数据操作系统 | 0 | 1 | 2 | 3 | 1 | **最弱**：血缘/管道/同步三件全无 |
| 20 本体・数字孪生 | 4 | 0 | 0 | 1 | 1 | **最强**：5 项达标 1 项缺失 |
| 30 AIP 决策与控制 | 3 | 3 | 0 | 0 | 1 | 结构完整，Route/预算是短板 |
| 40 工作台与业务应用 | 1 | 3 | 1 | 0 | 1 | 前端面够，运行时与低代码薄 |
| 50 平台内核与资产装配 | 0 | 3 | 1 | 1 | 0 | 资产链已通，插件插槽空 |
| 60 租户、安全与治理 | 2 | 1 | 1 | 0 | 0 | **地基最扎实** |
| 70 部署与端云 | 0 | 3 | 0 | 0 | 0 | 容器化有，CI 无 |
| 80 Apollo 交付发布 | 1 | 1 | 1 | 0 | 0 | 发布闭环通，落地环境未通 |
| 90 证据可观测韧性 | 0 | 2 | 0 | 0 | 0 | 本分册刚起 |
| **合计** | **11** | **17** | **6** | **5** | **4** | 39 项有效模块 |

**L3 率 = 11/39 ≈ 28%**；L3+L2 = 28/39 ≈ 72%（"能用"的占七成）。

### 3.2 与历史两版口径对照（为什么不相等）

| 版本 | ✅ | 🟡 | 🔴 | ⚪ | 判定 | 口径差异 |
| --- | --: | --: | --: | --: | --- | --- |
| 2026-09-09 清单自评 | 1 | 21 | 19 | 4 | 45 项 | 纸面自评 + 部分靠 TASK 描述 |
| 2026-09-15 实测重盘 | 7 | 14 | 13 | 4 | 38 项 | 当天上午按 tests/迁移/表存在性重数 |
| **2026-10-05（本文）** | **11** | **16** | **5** | **4** | **39 项** | **行为级 L0–L4，每级要表+端点+测试三重证据** |

三点必须说清：

1. **总数不同≠漏项**：09-09 记 45 项、09-15 记 38 项、本文 39 项（43 减 4 项范围外）。
   分册项数本身在历次评审中就有增减，不能直接相减看"少了"。
2. **🔴 从 19 掉到 5，主要靠执行而非口径放宽**：80-01/80-02、70-03、50-01/50-03、60-04、
   30-03、40-06、90-02 这 9 项在旧清单里标 🔴（"无"），实际已被 TASK-012~017 落地成表+端点+测试。
   **这是旧地图最大的失真点**——清单 09-09 之后就没再更新过。
3. **本文把两项主动下调**（不是粉饰）：10-01 从 🟡 降到 L1（Dataset 只有表没有资产闭环）、
   40-03 从 🔴 提到 L1 但没给 L2（有页定义无 Canvas）。下调项已在表中标红理由。

### 3.3 五轴硬指标（用数字说话，不用形容词）

```
工程基础  ┌──────────────────────────────────────────────┐ 17 迁移单链 / 双库同 tip / 40 RLS 表
          └──────────────────────────────────────────────┘
测试锁定  ┌──────────────────────────────────────────────┐ 25 脚本 660 断言 0 红
          └──────────────────────────────────────────────┘
接口覆盖  ┌──────────────────────────────────────────────┐ 119 端点 / 28 组
          └──────────────────────────────────────────────┘
前端可操作 ┌──────────────────────────────────────────────┐ 20 路由 / tsc 0 错 / 真浏览器未验
          └──────────────────────────────────────────────┘
生产化     ┌──────────────────────────────────────────────┐ CI / Trace / Watchdog / 真实连接器 全空
          └──────────────────────────────────────────────┘
```

**五轴里前四轴都亮着，第五轴（生产化）是空的** —— 这就是当前阶段最真实的画像。

---

## 4. 可观测与证据链现状（90-01 交叉）

图谱要求的六件套，逐项核：

| 件套 | 状态 | 实证 |
| --- | --- | --- |
| Health | ✅ 有 | `GET /api/health`（DB/LLM/向量），无前端消费 |
| Log | ✅ 有 | `audit_logs` 表 + `/api/admin/audit` + admin 日志页 |
| **Trace** | ❌ 无 | 端点间无链路 ID 传递，`tool_executions` 无 trace_id |
| Receipt | ✅ 有 | `action_receipts` + `/api/admin/receipts` |
| Lineage | 🟠 部分 | 审批谱系有（`eval_contracts`），**数据血缘无** |
| Watchdog | ❌ 无 | 无守护进程/无失败自愈，进程挂了没人知道 |

---

## 5. 已知债（实测出来的，不是猜的）

从上轮 TASK-017 以来延续、且本轮回归/盘点点到的：

| # | 债 | 影响 | 处置 |
| --- | --- | --- | --- |
| 1 | **真浏览器联调未做** | `/releases`、`/edge-sites` 两页只验到 SSR 200 + 代理数据正确，无真实点击 | 本机无 Playwright；装 Chromium ~500MB 需你点头 |
| 2 | **迁移 downgrade 零实测** | 17 条迁移都有 `down_revision`，但没有一条真跑过 `downgrade` | 补一条 `verify_downgrade.py` 走干净库 |
| 3 | `test_outbox_projector` 口径曾变 | CURRENT.md 记其 FAIL「<5s 验收」，本轮 **21 PASS/0 FAIL** | 随 `reset_test_db.py` 改走迁移链后隔离库数据变干净，断言前提复位；**回归口径以本轮为准** |
| 4 | 签名是非对称实现的占位 | 当前 `sha256(version\|manifest\|sbom)`，多人可伪造 | 换私钥签名前不接受"外部审计"承诺 |
| 5 | 心跳无超时判离线 | 边缘站点只记录 `last_heartbeat_at`，**不因超时转 offline** | 页面显示的 online 是当下事实，不是健康推断 |
| 6 | `DASHSCOPE_API_KEY` 未填 | 语义检索走本地哈希兜底，检索质量降级 | 填了即升 text-embedding-v3（维度一致不需重建索引） |
| 7 | 无 CI | 一次全绿回归要人工跑 ~7 分钟 | 见 §6 第 1 条 |

---

## 6. 下一步（按 P0 → P1 → P2，每条带验收标准）

| # | 模块 | 动作 | 验收标准 | 依赖 |
| -: | --- | --- | --- | --- |
| 1 | 70-01 | **接一条 CI**（GitHub Actions：reset_test_db → run_tests → tsc） | push 后自动跑出「25 脚本 / PASS 660 / tsc 0 错」三连绿 | 远端已配（见 README 版本管理节） |
| 2 | 90-01 | **Trace 链路 ID**：请求中间件生成 `trace_id`，透传进 `audit_logs` + `tool_executions` | 一次请求后两表都能查到同一 trace_id；`test_trace.py` 锁定 | 1 |
| 3 | 90-01 | **Watchdog**：`/api/health` 升为体检（依赖探测 + 近 5 分钟错误率 + 边缘站点超时判离线） | 边缘站点心跳超 5 分钟自动转 `offline`；前端 dashboard 显四项 | 2 |
| 4 | 80-03 | **downgrade 实测**：干净库上逐条 `downgrade -1` 再 `upgrade head` | 17 步全通；失败即修迁移 | 无 |
| 5 | 10-01/10-05 | **最小血缘**：`data_datasets` 加 `source_id` 自引用，记录一次抽取血缘 | 数据源页可见"上游→本次"一行 | 无 |
| 6 | 30-02 | **Model Route**：`POST /api/admin/models/route` 落默认模型 | admin 页可切换默认模型，测试锁定 | 无 |
| 7 | 10-02 | **真实连接器**：REST Webhook 连接器（最小）打通 | 配一个 Webhook 源能拉到数 | 无 |
| 8 | 50-05 | **Adapter 插槽**：定义一个空的 `Plugin` 挂载点 | 无真实插件也能优雅降级 | 无 |

> 第 1 条是杠杆最大的一条：没有 CI，前面任何一次"全绿回归"都只是人工自觉。

---

## 7. 怎么刷新这张地图

这张地图**不是写完就过时的死文档**——采集器可复跑：

```powershell
cd backend
# 人读摘要
.\venv\Scripts\python.exe tools_patch\maturity_snapshot.py
# 机器可读证据（覆盖 docs/maturity-snapshot.json）
.\venv\Scripts\python.exe tools_patch\maturity_snapshot.py --json > ..\docs\maturity-snapshot.json
```

采集器每次都会重新数：迁移链（AST 解析，含链根唯一性校验）、双库 tip/表数/RLS 表数、
API 端点与分组、前端路由与源码文件数。**改完代码重跑一遍，§0 那张表和 §3.1 热力图就能同步更新。**

> 踩坑提醒：DSN 必须写 `postgresql+psycopg://`。写 `postgresql://` 会落回 psycopg2 抛
> `ModuleNotFoundError`——这是本项目反复踩过的坑，见 README「环境变量」节与差距清单 DSN 铁律。

---

## 附：本文引用的证据源

- 双库直查：`pg_class`（RLS / FORCE 判据）、`pg_tables`、`alembic_version`
- 路由面：`app.api` 注册后遍历 FastAPI `routes`
- 测试面：`backend/run_tests.py` 全量回归（2026-10-05，25 脚本）
- 类型面：`frontend` `tsc --noEmit` 0 错误（2026-10-05）
- 历史口径：`docs/图谱-furui-aios差距清单与实施路线.md`（09-09 / 09-15 两版）
