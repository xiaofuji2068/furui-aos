# 图谱 ↔ furui-aios 差距清单与实施路线

> 编制日期：2026-09-06
> 更新记录：
> - 2026-09-06 复核 Phase 0 五项待确认项全部闭环；重大发现 —— **本体持久化已实现过半**（models_ontology.py + test_ontology_persistence P0-018）
> - **2026-09-09 修订**：盘点代码发现 Phase 1 与 Phase 2 实际已**全部完成**（包括 Revision 演进、图探索 API、知识治理门禁全到位），比 09-06 编制时多推进了 1.5 个 Phase
> 文档性质：施工计划（只读盘点产物，未改动任何代码）
> 数据来源：《AOS 技术架构图谱》01b 产品架构重排版方案 + furui-aios 源码只读盘点（backend 32 个 py /frontend Next.js）
> 用途：把架构图谱的设计逐模块落到 furui-aios 代码，形成可排期的实施路线



***

## 1. 两个项目的关系定位



|    | AOS 技术架构图谱                                 | furui-aios                                  |
| -- | ------------------------------------------ | ------------------------------------------- |
| 角色 | **蓝图 / 目标架构**                              | **工地 / 当前实现**                               |
| 内容 | 44 页架构书（L0×1、L1×9、L2×34），四层主链 + 五横切        | FastAPI + Next.js 代码仓库（v2.0）                |
| 路径 | `WorkBuddy\2026-09-01-23-10-23\AOS技术架构图谱\` | `WorkBuddy\2026-08-31-13-04-07\furui-aios\` |
| 关系 | 图谱描述的就是 furui-aios 应该长成的样子                 | 差距 = 图谱目标 − 当前实现                            |

**核心结论**：不是 "能否用到"，而是 "按图施工、分阶段落地"。图谱已经把每个模块的职责、边界、成熟度写清楚，等于施工图现成。



***

## 2. furui-aios 现状基线（已实际盘点）

### 2.1 技术栈



| 层  | 现状                                                                                                 |
| -- | -------------------------------------------------------------------------------------------------- |
| 后端 | FastAPI + SQLAlchemy 2.x + **SQLite**（`backend/data/app.db`，零外部依赖开箱即跑；代码明确预留 `DATABASE_URL` 切换生产库） |
| 模型 | DeepSeek（OpenAI 兼容），`config.py` 有 `llm_enabled / embedding_enabled` 开关                             |
| 前端 | Next.js 14（App Router）+ TypeScript + Tailwind（`app/` + `components/` + `lib/`）                     |
| 启动 | `start.bat / start.sh`（backend:8000 + frontend:3000）                                               |

### 2.2 已有能力（比 "空骨架" 多，分五类）



1. **认证与 RBAC**：`auth.py`（JWT、`require_perm`/`require_any_perm`）、`models.py`（Company/Department/User/Role/Permission）、`security.py`、`api/auth_api.py`（login/me/change\_password）、`api/admin.py`（用户/角色/权限 CRUD，含 org\_admin 全套接口）。

2. **Agent 与工具链**：`agents/orchestrator.py`（意图路由 + 对话 + **人类确认**`confirm_task` + SSE 流式，`tests/test_orchestrator_sse.py` 锁定 dict→JSON 序列化）、`agents/employees.py`（Agent 注册 / 技能）、`agents/coordinator.py`（多 Agent 会诊）、`mainline.py`（MainlineRunner 主链执行：步骤 / 进度 / 失败处理 / 报告润色）、`models_ai.py`（Agent/AgentSkill/AgentTask/AgentStep/AgentExecution/SalesTask）、`tool_gateway.py`（工具执行 + 权限级别 + 审批决定 + 日志）、`skills/__init__.py`（**Skill 注册表**：query\_orders/query\_products/query\_workorders/query\_devices/query\_kb/get\_dashboard + 写入型 create\_workorder/send\_notification/draft\_report，`WRITE_SKILLS` 标 "需人类确认"，`openai_tools()` 转 function-calling）。

3. **数据与知识**：
   - **本体语义层** `ontology/__init__.py`：`OntologyObject/ObjectType/Link/Function` + `build_demo_ontology` + DB 持久化接口 **`seed_ontology` 幂等落库** / **`list_objects` DB 优先、内存兜底** / **`list_links` 查询 Link** / **`get_related(type, id, depth)` 深度图遍历** / `search_objects` / `call_function`（含 DB 端 Link 写入 `_upsert_db_link`）。
   - **本体持久化** `models_ontology.py`：`OntologyType / OntologyObjectRow`（`(type, object_id)` 唯一约束 + JSON properties）/ `OntologyLinkRow` / `OntologySchemaRevision`（r1 基线），含 **`bump_revision(db, note) -> str`** 演进机制（解析现有 r{n}+1，幂等，已有 `tests/test_ontology_persistence.py` 锁定）。
   - **本体 API** `api/ontology_api.py`：`GET /api/ontology/related?type=&id=&depth=1~4` 图探索接口（`require_perm("datasource:view")`）。
   - **数据网关** `data_gateway.py`：只读 SQL 网关 + 字段脱敏 + 行数限制 + 模拟 ERP SQLite；`store_data_sources.py` + `api/data_sources.py` 数据源 CRUD/catalog/开关。
   - **知识治理** `api/knowledge.py`：**`POST /documents/{id}/submit`**（草稿→审核中，`knowledge:write`）+ **`POST /documents/{id}/publish`**（审核中→已发布，`knowledge:manage`，含跨租户校验 + `write_audit`）；上传默认 `status="草稿"`，防止"上传即发布"。
   - **RAG** `rag.py`：分块 + **双引擎嵌入**（通义 text-embedding-v3 语义 / 本地哈希离线兜底）+ 混合检索 + Rerank + 权限前置过滤 + **仅检索"已发布"文档**（line 260 `KnowledgeDocument.status == "已发布"`）+ 来源溯源。
   - **AI 模型** `models_ai.py`：KnowledgeBase/Document/Chunk（含状态与有效期）、DataSource/DataConnection、Tool/ToolExecution。
   - **多模型纳管** `config.py`：**`LLM_PROVIDERS` 字典**（deepseek / kimi / qwen / glm / openai / custom 六家）+ 启停开关 + `api/admin.py` Key 管理子路由（`tests/test_admin_keys.py` 锁定）。

4. **治理与工作台**：`api/approvals.py`（审批列表 / 规则 / 批准 / 驳回）、`models_ai.py`（Approval/ApprovalRule/AuditLog/Notification/`write_audit`）、`api/workbench.py`、`api/scenes.py`、`api/dashboard.py`（总览 / KPI / 在岗 AI / 最近活动）、`api/admin.py`（**首页 + 6 大子路由**：数据 / 集成 / 权限 / **模型 Keys** / 日志 / 设置）、`bootstrap.py`（种子数据）。

5. **前端**：App Router 页面 + 组件（登录 `/login`、工作台 `/workbench`、AI 员工 `/agents`、场景 `/scenes`、审批 `/approvals`、管理后台 `/admin/*` 等），Tailwind + TS，路径见 `frontend/app/`。


> **2.2 节能力快照（2026-09-09 修订版）**

| 维度                | 数量 / 状态                                                    |
| ----------------- | ---------------------------------------------------------- |
| 后端测试脚本           | **12 个**（`tests/test_*.py`，覆盖认证 / 主链 / 失败路径 / 仪表盘 / 持久化 / SSE / 知识治理 / 多 Agent / 情报 / Key 管理 / 主线流程 / **Schema 演进**） |
| 本体 DB 表           | 4 张：`ontology_types / ontology_object_rows / ontology_link_rows / ontology_schema_revisions` |
| 本体 API            | **2 个**：`GET /api/ontology/related`（图探索 depth 1~4）+ `POST/GET /api/ontology/revisions`（Schema 演进 API） |
| Schema 演进        | `bump_revision(db, note)` 可用（r1 基线 → 任意版本）              |
| 知识治理              | **submit / publish + 跨租户校验 + 审计 + 强制草稿 + RAG 只取"已发布"** |
| LLM 多提供方          | **6 家**（deepseek / kimi / qwen / glm / openai / custom） |
| 鉴权                | JWT + `require_perm` / `require_any_perm`（按 Company 隔离）       |
| Admin 子路由         | data / integration / permission / **keys** / logs / settings  |
| Phase 1（本体持久化）   | ✅ **已完工**（20-01 / 20-02 / 20-04）                        |
| Phase 2（知识治理）    | ✅ **已完工**（30-04 / 30-05 / 30-06）                        |
| Phase 3（生产库 + RLS） | 🟡 工程就绪：Alembic 迁移链（6 版本）+ RLS/FORCE RLS 全量迁移（27 租户表）+ 多租户隔离测试；待 PostgreSQL 环境实跑验证 |
| Phase 4（动作闸门/密钥）  | 🟡 部分（Key 纳管已动；动作闸门待 Phase 5 后评估）                       |
| Phase 5（交付/可观测）   | ⚪ 待 Phase 3 落地后启动                                       |


***

## 3. 差距清单（核心，按图谱九分册）

> 差距等级：✅ 已对齐・🟡 有雏形需补强・🔴 缺失・⚪ 当前范围外（不排期）
> 优先级：P0 主链中枢（先做）→ P1 地基 → P2 横切增强

### 10 数据操作系统（L1: 10-01；L2: 10-02\~10-07）



| 图谱模块            | 图谱要求                                          | furui-aios 现状                                       | 等级 | 优先级 |
| --------------- | --------------------------------------------- | --------------------------------------------------- | -- | --- |
| 10-01 数据操作系统    | Source→Sync→Dataset→Lineage/Health 资产链        | 有只读数据网关 + 数据源 CRUD；无 Dataset/MediaSet 资产模型          | 🟡 | P1  |
| 10-02 数据源与连接器   | Connector Catalog、JDBC/REST/Webhook、SecretRef | DataSource/DataConnection + catalog 有；无真实协议连接器与凭据管理 | 🟡 | P1  |
| 10-03 同步调度与边缘执行 | Sync Config、Edge Agent、Checkpoint             | 无                                                   | 🔴 | P2  |
| 10-04 管道构建与执行   | Pipeline Builder、Schedule、Build               | 无                                                   | 🔴 | P2  |
| 10-05 数据资产血缘质量  | Lineage、Health、Branch                         | 无（data\_gateway 无血缘记录）                              | 🔴 | P2  |
| 10-06 垂直电商通用接入  | 电商 AdapterPack                                | 当前是 ERP/CRM 演示数据，非电商                                | ⚪  | —   |
| 10-07 全量数据存储架构  | PostgreSQL 权威 + 对象存储 + 向量 / 缓存投影              | **PostgreSQL 17.5 已装 + furui_aios 库 + Alembic 8 版迁移全绿（35 表，2026-09-15 实测）**；对象存储 / 向量 / 缓存投影分层仍无 | 🟡 | P1  |

### 20 本体・数字孪生（L1: 20-01；L2: 20-02\~20-06）



| 图谱模块             | 图谱要求                                      | furui-aios 现状                                                                                            | 等级 | 优先级    |
| ---------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------- | -- | ------ |
| 20-01 本体数字孪生     | 数据→业务对象→受控动作                              | ontology 内存语义层 + **DB 持久化层已落地**（models\_ontology.py + seed\_ontology，测试锁定）+ **图探索 API 已上线**（`/api/ontology/related?type=&id=&depth=1~4`） | 🟡 | **P0** |
| 20-02 本体元模型      | Object Type/Link Type/Schema Revision     | OntologyType/OntologyObjectRow/SchemaRevision 已建表；**`bump_revision(db, note)` 演进机制可用**（解析最大 r{n} + 1，幂等，测试锁定）；**`POST /api/ontology/revisions` 接通 API**（`knowledge:manage`，返回 `{id, version, note, commit_ts}`，审计 `ontology.bump_revision`，`tests/test_ontology_revisions.py` 31 项全绿）；**Link 元模型有 OntologyLinkRow**（type/source_id/target_id 唯一约束 + JSON properties），深化已具备底子 | 🟡 | **P0** |
| 20-03 映射与身份      | Funnel、Mapping Draft/Review、Identity      | 无                                                                                                        | 🔴 | P2     |
| 20-04 权威对象关系与图探索 | 权威写链、Outbox、Projector、GraphSnapshot       | **Link 已落库并可查询**（`_upsert_db_link` 幂等 + `list_links(type/source/target)` DB 优先回退内存 + seed 遍历 links）；**图探索 API 上线**（`/api/ontology/related` 双向遍历子图）；仍无 Outbox/Projector/GraphSnapshot                          | 🟡 | **P0** |
| 20-05 函数与受控动作    | Function、Action、Proposal/Approval/Receipt | **四级门禁已完整**（Agent 白名单 / 用户权限 / 参数校验 / 审批 Level1-4）+ 批准后执行 + 审计（tool\_gateway.py）；缺 Receipt/Lease 进阶凭证与补偿 | 🟡 | **P0** |
| 20-06 电商数字孪生     | 电商对象建模                                    | 当前范围外                                                                                                    | ⚪  | —      |

### 30 AIP 决策与控制（L1: 30-01；L2: 30-02\~30-07）



| 图谱模块              | 图谱要求                                                | furui-aios 现状                                                                                              | 等级 | 优先级    |
| ----------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | -- | ------ |
| 30-01 AIP 决策与控制   | 模型→逻辑→Agent→Eval / 审批门禁                             | orchestrator/agents/mainline 有雏形；门禁链不完整                                                                    | 🟡 | **P0** |
| 30-02 模型纳管与选择     | Provider、Model Catalog、Route、Capacity               | config + admin 模型页；**多提供方已动工**（`config.LLM_PROVIDERS` + `tests/test_admin_keys.py` 覆盖 GET 状态不回明文 / POST 写 .env + 热更新 / 激活切换 / 自定义提供方 / 留空不覆盖）；无 Catalog/Route/ 预算                                                                     | 🟡 | P2     |
| 30-03 Logic 决策编排  | Logic 画布 / 服务端图                                     | 无（编排硬编码在 orchestrator）                                                                                     | 🔴 | P2     |
| 30-04 Agent 能力与运行 | Agent/Skill/Capability/Binding/Handoff/Receipt      | Agent/AgentSkill/Task/Step/Execution 模型齐全 + confirm\_task；缺 Binding/Handoff/Receipt                        | 🟡 | **P0** |
| 30-05 Eval 审批与谱系  | EvalContract、Draft、Approval、Decision Lineage        | Approval/ApprovalRule + AuditLog 有；缺 EvalContract / 谱系                                                     | 🟡 | P1     |
| 30-06 记忆与知识治理     | Candidate→Eval→Approval→Item/Revision、来源 / 许可 / PII | KB + rag **双引擎**（通义语义 / 哈希兜底）+ 混合检索 + 权限前置 + 溯源 + 状态字段；**门禁闭环已上线**（`POST /documents/{id}/submit` 草稿→审核中 `knowledge:write` + `POST /documents/{id}/publish` 审核中→已发布 `knowledge:manage`，均跨租户校验 + 写审计；上传默认 `status="草稿"`；`rag.py:260` 只检索 `已发布`）；缺来源/许可/PII 标注（文档标为可选） | ✅ | **P0** |
| 30-07 垂直电商 AIP    | 电商数字同事                                              | 当前范围外                                                                                                      | ⚪  | —      |

### 40 工作台与业务应用（L1: 40-01；L2: 40-02\~40-06）



| 图谱模块                  | 图谱要求                                     | furui-aios 现状                           | 等级 | 优先级 |
| --------------------- | ---------------------------------------- | --------------------------------------- | -- | --- |
| 40-01 工作台与业务应用        | 模块化消费对象 / 决策 / 动作                        | workbench/scenes/dashboard API + 前端页面   | 🟡 | P1  |
| 40-02 应用运行时           | Application/Module/Widget Runtime        | 前端页面有；无模块运行时抽象                          | 🟡 | P2  |
| 40-03 低代码构建           | Canvas、Widget Registry、Publish           | 无                                       | 🔴 | P2  |
| 40-04 对象 AIPAction 嵌入 | 对象视图 / AIP/Action 表单 + 写回门禁              | 对象 / 审批前端雏形；写回未走 Action/Receipt         | 🟡 | P1  |
| 40-05 垂直电商业务工作台       | 电商驾驶舱                                    | 当前范围外（现有通用销售 / 运维场景）                    | ⚪  | —   |
| 40-06 长程任务与人机协作       | TaskBrief、Stage/Checkpoint、Review/Return | mainline + confirm\_task 雏形；无完整状态机 / 投影 | 🟡 | P1  | 2026-09-22 DONE：TaskBrief + 显式迁移白名单状态机（InReview/Returned）+ 3 阶段投影（数据采集/归因分析/行动确认）+ 审批联动（批准→Completed、拒绝→Returned）+ `/api/tasks/{id}/review`、`/retry` |

### 50 平台内核与资产装配（L1: 50-01；L2: 50-02\~50-05）



| 图谱模块                 | 图谱要求                                         | furui-aios 现状                           | 等级 | 优先级 |
| -------------------- | -------------------------------------------- | --------------------------------------- | -- | --- |
| 50-01 平台内核与资产装配      | Bundle/Registry/Resolver/Installation/Plugin | 无；api/ 为模块化单体雏形                         | 🔴 | P2  |
| 50-02 四层产品稳定契约       | API/BFF、Contract、Service/Store               | REST + response.py 统一包装 + DB Session 依赖 | 🟡 | P2  |
| 50-03 资产包发布与解析       | Manifest/Bundle/Registry/ 签名                 | 无                                       | 🔴 | P2  |
| 50-04 租户安装与覆盖        | Installation/Overlay/ETag/CAS                | 无                                       | 🔴 | P2  |
| 50-05 插件与 Adapter 扩展 | Plugin/Adapter 插槽                            | 无                                       | 🔴 | P2  |

### 60 租户、安全与治理（L1: 60-01；L2: 60-02\~60-04）



| 图谱模块                 | 图谱要求                                            | furui-aios 现状                                      | 等级 | 优先级 |
| -------------------- | ----------------------------------------------- | -------------------------------------------------- | -- | --- |
| 60-01 租户安全与治理        | Principal/TenantScope/OpenFGA/Marking/RLS/Audit | Company/User/Role/Permission + JWT + require\_perm | 🟡 | P1  |
| 60-02 身份与数据租户隔离      | RLS/FORCE RLS、复合租户键、负向 canary                   | JWT + company\_id 字段；**RLS/FORCE RLS 已在 PG 实测通过**（受限角色 app\_test，6/6 断言：租户互不可见 / 无上下文查空 / 无上下文 UPDATE 0 行 / 越权写被 WITH CHECK 拦截，2026-09-15）；复合租户键 / 负向 canary 未做 | 🟡 | P1  |
| 60-03 权限与动作治理        | Marking/Purpose/Approval/Lease/Kill/Audit       | 审批 + AuditLog + 工具权限级别；无 Marking/Lease/Kill        | 🟡 | P1  |
| 60-04 Secret 与外部数据保护 | SecretRef/Keychain、PII/Retention/Region         | 无；`.env` 明文密钥                                      | 🔴 | P1  |

### 70 部署与端云（L1: 70-01；L2: 70-02\~70-03）



| 图谱模块              | 图谱要求                       | furui-aios 现状         | 等级 | 优先级 |
| ----------------- | -------------------------- | --------------------- | -- | --- |
| 70-01 部署与端云       | 部署分区 / 网络信任边界              | 仅本地 start.bat/sh      | 🟡 | P2  |
| 70-02 当前怎样部署      | 节点 / 端口 / 版本引用当前配置         | 本地开发形态；无 Compose/Helm | 🟡 | P2  |
| 70-03 中心边缘与客户环境协作 | Hub-Spoke、Ferry、Edge Agent | 无                     | 🔴 | P2  |

### 80 Apollo 交付发布（L1: 80-01；L2: 80-02\~80-03）



| 图谱模块               | 图谱要求                                  | furui-aios 现状  | 等级 | 优先级 |
| ------------------ | ------------------------------------- | -------------- | -- | --- |
| 80-01 Apollo 交付与发布 | Release/Channel/Change/SBOM/ 签名       | 无              | 🔴 | P2  |
| 80-02 发布到达各环境      | Promotion/Recall、SBOM / 签名            | 无              | 🔴 | P2  |
| 80-03 升级迁移与回滚      | Alembic、Expand/Backfill、Rollback / 补偿 | 无迁移体系（建表方式待确认） | 🔴 | P2  |

### 90 证据、可观测与韧性（L1: 90-01；L2: 90-02）



| 图谱模块             | 图谱要求                                      | furui-aios 现状                                            | 等级 | 优先级 |
| ---------------- | ----------------------------------------- | -------------------------------------------------------- | -- | --- |
| 90-01 证据可观测与韧性   | Health/Log/Trace/Receipt/Lineage/Watchdog | AuditLog + tool\_gateway.\_log + response 包装 + admin 日志页 | 🟡 | P1  |
| 90-02 如何知道系统真的工作 | 成熟度矩阵、差异地图                                | 无健康检查 / 状态汇总                                             | 🔴 | P2  |


### 3.X 差距热度图与下一步动作（2026-09-09 修订）

> 上文逐模块表已写到每行；本节给一张"进度热度图" + 按 P0/P1/P2 分桶的"下一步动作表"，方便直接拍板这一周做什么。

#### 3.X.1 进度热度图（按分册）

| 分册        | ✅ | 🟡 | 🔴 | ⚪ | 状态                 |
| --------- | -- | -- | -- | -- | ------------------ |
| 10 数据操作系统 | 0  | 2  | 4  | 1  | P1 储备 / P2 待规划      |
| 20 本体・数字孪生 | 0  | 5  | 1  | 1  | **P0 主战场**（5 个 🟡 待升级 ✅） |
| 30 AIP 决策 | 1  | 5  | 1  | 1  | **P0 主战场**（30-06 ✅ 闭环） |
| 40 工作台     | 0  | 4  | 1  | 1  | P1/P2 等待 Phase 3   |
| 50 平台内核    | 0  | 1  | 4  | 0  | P2 全部                 |
| 60 租户安全    | 0  | 2  | 2  | 0  | 跟随 Phase 3 RLS     |
| 70 部署      | 0  | 1  | 2  | 0  | 跟随 Phase 3 迁移     |
| 80 交付      | 0  | 0  | 3  | 0  | P2 全部                 |
| 90 证据      | 0  | 1  | 1  | 0  | P1/P2 跟随可观测计划      |
| **合计**     | **1** | **21** | **19** | **4** | —                |

#### 3.X.2 下一步动作表（按 P0 优先）

| # | 模块 | 动作 | 工作量估 | 依赖 | 验收标准 |
|---|---|---|---|---|---|
| 1 | 20-02 ✅ | `bump_revision` 接通 API：`POST /api/ontology/revisions` + `GET /api/ontology/revisions`（`tests/test_ontology_revisions.py` 锁定 31 项，2026-09-09 完工）| 0.5d | 无 | curl 测一遍 r1→r2→r3；admin 有 `knowledge:manage`、sales 无；审计 `ontology.bump_revision` 写 AuditLog |
| 2 | 20-04 末尾 | **Outbox 表 + 单线程 Projector**（最小可用）：写 Object/Link 同步落 outbox + 异步投影到图快照；GraphSnapshot 暂用 JSON 字段 | 2~3d | 1 | `tests/test_outbox_projector.py` 通过：写 100 条 Link，5s 内图快照全量可见 |
| 3 | 30-02 | **模型 Catalog + Route**：把 `LLM_PROVIDERS` 暴露到 `GET /api/admin/models/catalog`（含 name / endpoint / context_window / price_per_1k）；`POST /api/admin/models/route` 选择默认模型（落 `config.DEFAULT_LLM`） | 1~2d | 1 | admin 页"模型"标签可切换默认；测试锁定路由结果 |
| 4 | 20-05 / 30-04 | **Receipt 表**：`AgentExecution` 完成后写 `Receipt(action, actor, params_hash, result_hash, ts)`；写回门禁校验 Receipt 存在 | 1d | 无 | `tool_gateway.execute()` 路径强制 Receipt；测试覆盖补写 |
| 5 | 30-05 | **EvalContract**：`Approval.decision_lineage` 字段扩展（输入/输出 hash）+ `EvalContract` 表（评估合同：accuracy/fairness 阈值） | 1d | 4 | 审批页可见 lineage；EvalContract 通过 admin 配置生效 |
| 6 | 60-03/60-04 | **审计查询 API**：`GET /api/admin/audit?actor=&action=&from=&to=`；admin 页"日志"标签接好 | 0.5d | 4 | curl 跨租户过滤正确 |
| 7 | 90-01 | **健康检查**：`GET /api/health`（DB/Redis/LLM/Vector 四项）+ 启动自检 + 失败 watchdog 写 AuditLog | 1d | 6 | 前端 dashboard 显示四项健康状态 |

#### 3.X.3 P1/P2 后备队（按需启动）

- **10-07 PostgreSQL + RLS**（Phase 3 主项，最大风险；决策点：自建 vs Supabase vs Neon；估 3~6 周）
- **10-01/10-02 Dataset/MediaSet 资产模型 + Connector Catalog**（P1，配合 10-07 启动）
- **40-04 对象 AIPAction 嵌入**（P1，等 Receipt 落地）
- **40-06 长程任务状态机**（P1，等 Receipt 落地）
- **80-03 迁移体系**（P1，Phase 3 一并上 Alembic）
- **50-03/50-04/50-05 资产包 + 插件**（P2，全部后置）


### 3.Y 差距热度图与下一步动作（2026-09-15 修订：Phase 3 PG 实测）

> 本节记录 2026-09-15 的**确定性实测成果**（非纸面评估）。当天上午按 tests / 迁移 / 表存在性重新盘点出 ✅7 / 🟡14 / 🔴13 / ⚪4 的新口径（独立于 09-09 的 45 项逐模块计数，二者不可直接相减）；下午完成 Phase 3 实测后，本节把两个最高优先级模块的状态落定并登记修复记录。

#### 3.Y.1 本轮实测成果（2026-09-15）

| 项 | 结果 | 证据 |
| --- | --- | --- |
| PostgreSQL 17.5 安装 | ✅ | 服务 `postgresql-x64-17` RUNNING（开机自启）、5432 监听、数据目录 `D:\PostgreSQL\data`、`postgres/postgres123` 连接成功 |
| furui_aios 库 + 迁移 | ✅ | Alembic **8 版本链全绿**至 head：baseline → 租户键/本体 → RLS 隔离 → Action 凭证 → Outbox/快照/Eval → RLS 全租户覆盖（27 表）→ status 默认值 → created_at 默认值；PG 35 张表 |
| RLS 隔离实测（图谱 60-02） | ✅ 6/6 PASS | 受限角色 `app_test`（生产同形态：应用非超管）：租户 A/B 互不可见、无上下文查空、无上下文 UPDATE 影响 0 行、越权写入被 WITH CHECK 拦截 |
| 权威存储实测（图谱 10-07） | 🟡 核心已落地 | PG 权威存储 + 迁移体系可用；对象存储 / 向量 / 缓存投影分层仍未做 |

**实测暴露并修复的 3 个真实缺陷**（均属于"工程就绪但从未实测"的隐性差距）：

1. **companies.status 非空无默认**：模型仅 Python 层 `default="active"`，迁移列 NOT NULL 且无 server_default → 原生 SQL 插入报错。模型补 `server_default="active"`，新增迁移 `a1b2c3d4e5f6`。
2. **26 张表 created_at 无 DB 默认值**（系统性缺陷，直接威胁未来企业数据导入）：模型批量补 `server_default=text("CURRENT_TIMESTAMP")`，新增迁移 `b2c3d4e5f6a7` 覆盖 26 表。
3. **测试形态错误：超级用户绕过 RLS**：`postgres` 超管无视行级安全（即使 FORCE）→ 断言全假。改为受限角色 `app_test` 连接跑断言；同时修复 `SET LOCAL` 不支持参数绑定（改 f-string 内插）、序列权限、中文错误消息匹配。

#### 3.Y.2 热度图增量（相对 3.X.1，仅列出本轮有变的行）

| 分册 | 变更 | 状态 |
| --- | --- | --- |
| 10 数据操作系统 | 10-07 🔴 → 🟡（PG 权威存储实测落地，分层未做） | P1 待续：对象存储 / 向量投影 |
| 60 租户安全 | 60-02 核心实测通过（等级保持 🟡，因复合租户键 / 负向 canary 未做） | P1 待续：复合租户键 / canary |

**下一步动作（Phase 3 剩余）**：① 应用层 RLS 贯通（app 用受限角色连接 + `set_tenant_context` 登录链路实测）；② 复合租户键 / 负向 canary；③ 数据导入前置项：系统收口其余"Python default 列"（除 created_at/status 外仍有一批，如 agents.status、priority 等）。

***

## 4. 差距分级汇总（2026-09-09 修订）

\| 等级 | 数量 | 分布 |

\|---|---|---:|---|

\| 🟡 有雏形需补强 | 21 | 集中在 20 全系 / 30-01/30-04/30-05 / 40 / 60 / 90-01 |

\| 🔴 缺失 | 19 | 集中在 10-03\~10-07 管道系、50 资产装配、80 交付、70 部署、90-02 |

\| ✅ 已对齐 | 1 | 30-06（知识治理） |

\| ⚪ 当前范围外 | 4 | 10-06、20-06、30-07、40-05（电商垂直全部后置） |
| **合计** | **45** | — |

> 修订说明：2026-09-06 旧版口径 ✅2 / 🟡19 / 🔴18 / ⚪5 是按"图谱编号独立计数"。本版按"分册对齐 + 链路关联"把 20-01 进入 🟡（待 Outbox-Projector 完工才能升级 ✅），故 ✅=1、🟡=21、🔴=19、⚪=4。具体分册分布见 3.X.1 热度图。

**判断（2026-09-09 修订）**：Phase 1 本体持久化（20-01/20-02/20-04 大部分）和 Phase 2 知识治理（30-06）已闭环，**下一步工作集中在三件事**（见 3.X.2 动作表）：① **`bump_revision` 接 API + Outbox/Projector**（20-02/20-04 末尾，0.5+3d）；② **模型 Catalog/Route + Receipt**（30-02/30-04，3\~4d）；③ **健康检查 + 审计查询**（90-01/60-03，1.5d）。做完这 7 项，可拿到 20 全系 + 30-02/30-04/30-05 全部 ✅，再启动 Phase 3 选型。



***

## 5. 实施路线（分阶段，按图施工）

### Phase 0・基线对齐（0.5\~1 周）



* 目标：施工计划被认可，映射关系定稿。

* 动作：确认本文档附录映射表；盘点前端页面清单；确认数据库选型（**建议：本阶段就定 PostgreSQL 迁移目标**，SQLite 保留为开发演示形态）；确认是否已有测试与 Alembic。

* 验收：差距表 + Phase 1 范围冻结。

### Phase 1・本体持久化（P0，1\~2 周）



* 对应图谱：20-01 / 20-02 / 20-04。

* 现状（2026-09-09）：**已完工**——`models_ontology.py`（Type/Object/Link/SchemaRevision 四表）+ `seed_ontology` 幂等落库（对象 + Link）+ `list_objects` / `list_links` DB 优先 / 内存兜底 + `bump_revision(db, note)` 演进机制 + `get_related()` 图探索 + `GET /api/ontology/related?type=&id=&depth=1~4` 端点 + `tests/test_ontology_persistence.py`（P0-018 / Task #26）已锁定（落库、重启不丢、幂等、写入动作可查、Revision r1 演进、图遍历）。

* 剩余动作：① 把 `bump_revision` 接通到 API/调用方（目前仅内部函数 + 测试调用，可考虑 `POST /api/ontology/revisions` + 写入型操作时自动打点）；② Outbox/Projector/GraphSnapshot（图谱 20-04 全量图探索与权威写链，**降为 P0 末尾或 P1 起**）。

* 验收：本体对象与关系重启不丢；SchemaRevision 可追溯；现有 skills/orchestrator 数据路径不回退。

### Phase 2・知识治理闭环（P0，2\~3 周）



* 对应图谱：30-06（+ 30-05 审批衔接）。

* 现状（2026-09-09）：**已完工**——`POST /api/knowledge/documents/{id}/submit`（草稿→审核中，`knowledge:write`，跨租户校验 + 写审计）+ `POST /api/knowledge/documents/{id}/publish`（审核中→已发布，`knowledge:manage`，跨租户校验 + 写审计）+ 上传默认 `status="草稿"` + `rag.py:260` 只检索 `已发布` 文档；嵌入仍是双引擎（填 key 即语义）。

* 剩余动作（可选）：补"来源 / 许可 / PII 标注"字段（文档标为可选）；语义检索启用（填 dashscope key）。

* 验收：知识入库必须走 "草稿→审核→发布"，未发布不可被 Agent 检索。

### Phase 3・权威存储与多租户（P1，3\~6 周）

> **实测状态（2026-09-15）**：PostgreSQL 17.5 已装、furui_aios 库已建、Alembic 8 版迁移全绿（35 表）、RLS 隔离实测 6/6 PASS（受限角色 app_test）。本 Phase 的第一条验收"多租户隔离测试通过"已达成（见 3.Y 修订节）；剩余：复合租户键 / 负向 canary、应用层 set_tenant_context 贯通、对象存储分层。

* 对应图谱：10-07 / 30-02 (存储) / 60-02。

* 动作：切 PostgreSQL（`DATABASE_URL` 口子已留）；实现 RLS/FORCE RLS + 复合租户键；起步不可变 Revision 与 Receipt 模型。

* 验收：多租户隔离测试通过；关键写路径有 Revision/Receipt 留痕。

### Phase 4・动作门禁与审计完善（P1，2\~4 周）



* 对应图谱：20-05 / 60-03 / 60-04。

* 动作：写入型 Skill 走完整 `Proposal → Approval → Lease → Receipt`；引入 Marking 分级；Secret 改为 SecretRef 引用（不再 `.env` 明文）。

* 验收：所有写入型动作全量留痕、可审批、可追溯；密钥不落明文。

### Phase 5・横切与交付（P2，持续）



* 对应图谱：50 资产装配 → 80 Apollo 交付（Alembic 迁移、Release/Channel）→ 90 可观测（Health/Receipt/Lineage）→ 70 部署形态。

* 动作：按序补齐；每项对齐图谱对应 L2 页。

* 验收：逐模块对照图谱 L2"模块详细设计" 打钩。

### 明确不做的（当前阶段）



* 电商垂直（10-06 / 20-06 / 30-07 / 40-05）：图谱要求平台通用 + 垂直由 AdapterPack 贡献，当前用 ERP/CRM 演示即可。

* 图谱中标 `BLOCKED / UNKNOWN` 的成熟度项：不承诺排期，先确认目标冻结后再动。



***

## 6. 风险与依赖



| 风险                  | 说明                                  | 缓解                                     |
| ------------------- | ----------------------------------- | -------------------------------------- |
| SQLite → PostgreSQL | 并发模型、RLS 依赖 PostgreSQL；波及全部 ORM 与查询 | Phase 0 定选型，Phase 3 集中迁移，SQLite 保留开发形态 |
| 内存本体 → 持久化          | Agent / 技能 / 工具数据路径变更，demo 种子逻辑重写   | Phase 1 单独做，回归验证 skills/orchestrator   |
| 外部组件引入              | OpenFGA、Apollo 等增加运维负担              | MVP 阶段暂缓，先用手写 RBAC + 审批，成熟后再引          |
| 一次性全量对齐             | 44 页同时实现必然失败                        | 按 Phase 推进，每阶段只对齐 2\~4 个图谱模块           |
| 图谱部分模块未冻结           | BLOCKED/UNKNOWN 项目标不明               | 排期前先与图谱 Owner 确认目标                     |



***

## 7. 附录

### 7.1 furui-aios 文件 → 图谱模块映射（主要）



| furui-aios 文件                                                                 | 图谱模块                               |
| ----------------------------------------------------------------------------- | ---------------------------------- |
| `backend/app/auth.py`、`security.py`、`models.py`（User/Role/Permission/Company） | 60-01 / 60-02                      |
| `backend/app/api/auth_api.py`                                                 | 60-01                              |
| `backend/app/ontology/__init__.py`                                            | 20-01 / 20-02 / 20-04              |
| `backend/app/models_ontology.py`                                              | 20-01 / 20-02 / 20-04（Phase 1 已落地） |
| `backend/app/skills/__init__.py`                                              | 20-05 / 30-04                      |
| `backend/app/tool_gateway.py`                                                 | 20-05 / 60-03 / 90-01              |
| `backend/app/agents/orchestrator.py`、`employees.py`、`coordinator.py`          | 30-01 / 30-04 / 40-06              |
| `backend/app/mainline.py`、`api/mainline_api.py`                               | 30-04 / 40-06                      |
| `backend/app/models_ai.py`（Agent/Knowledge/DataSource/Tool/Approval/Audit）    | 30 / 60 / 90                       |
| `backend/app/rag.py`、`api/knowledge.py`                                       | 30-06                              |
| `backend/app/data_gateway.py`                                                 | 10-01 / 10-05                      |
| `backend/app/store_data_sources.py`、`api/data_sources.py`                     | 10-02                              |
| `backend/app/api/approvals.py`                                                | 30-05 / 60-03                      |
| `backend/app/api/workbench.py`、`scenes.py`、`dashboard.py`                     | 40-01 / 40-02                      |
| `backend/app/api/admin.py`                                                    | 30-02 / 90-01                      |
| `backend/app/config.py`                                                       | 30-02                              |
| `backend/app/db.py`                                                           | 10-07 / 30-02 (存储)                 |
| `backend/app/bootstrap.py`                                                    | 种子数据（各模块）                          |
| `frontend/app/`、`components/`、`lib/`                                          | 40-01 / 40-04                      |

### 7.2 待确认项 → 已确认结论（2026-09-06 复核）



| 原待确认项                       | 结论                                                                                                                                                                                                                                                                                              |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 前端页面完整清单                    | ✅ **10 个路由页面**：`/`（首页）、`/login`、`/workbench`（工作台）、`/intelligence`（智能洞察）、`/knowledge`（知识库）、`/approvals`（审批）、`/scenes`（场景）、`/employees`（列表）/`new`/`[id]`（详情）、`/admin/[slug]`（管理后台：数据 / 集成 / 权限 / 模型 / 日志 / 设置）                                                                                    |
| 建表方式：create\_all 还是迁移体系     | ✅ 开发形态：`models.py init_db()`→`Base.metadata.create_all()`（幂等，开箱即跑）；**生产形态：Alembic 迁移体系已就绪**（backend/alembic，6 版本链，空库 `upgrade head` 建出 34 表，与 create_all 逐表比对一致；DATABASE_URL 一键切 PostgreSQL）                                                                                                                                                                            |
| 是否已有自动化测试                   | ✅ **backend/tests 共 11 个脚本式测试**（2026-09-09 盘点，TestClient + 手写 PASS/FAIL，非 pytest 框架）：test\_auth\_rbac / test\_coordinator / test\_dashboard / test\_failure\_path / test\_api\_mainline / test\_mainline / test\_knowledge / **test\_ontology\_persistence（P0-018）** / test\_intelligence\_endpoints / test\_orchestrator\_sse / test\_admin\_keys；requirements 中无 pytest |
| requirements 与图谱 10-01 基线差异 | ✅ requirements 11 项：fastapi 0.115 /uvicorn 0.30.6 /pydantic 2.9.2 /pydantic-settings/openai 1.51 /httpx/python-dotenv/sse-starlette/sqlalchemy 2.0.35 + **alembic 1.19.2 + psycopg[binary] 3.3.5（已装，import 验证通过）**；无向量库（语义嵌入走外部 API，向量检索待 Phase 5 评估）                                                                                     |
| SalesTask 归属                | ✅ 代码注释自证：**AgentTask = AI 分析任务**（图谱 30-04 运行链）；**SalesTask = 业务系统跟进事项 / 动作落点**（图谱 20-05 受控动作→业务对象），二者生命周期与责任人不同，分开建表是正确设计                                                                                                                                                                       |

> 复核新增发现（2026-09-06）：
> **Phase 1 本体持久化已实现过半**
> （models_ontology.py + seed_ontology + test_ontology_persistence 锁定），见第 5 节 Phase 1 修订。
>
> 2026-09-09 二次复核：
> - **Phase 1（本体持久化）实际已全部完工**——除"Outbox/Projector/GraphSnapshot"图谱全量图探索外，对象/Link/Revision 演进/图探索 API 全部上线
> - **Phase 2（知识治理）实际已全部完工**——`submit`/`publish` 端点 + 跨租户校验 + 写审计 + 上传强制草稿 + RAG 只检已发布
> - **30-02 模型纳管部分动工**——`config.LLM_PROVIDERS` 多提供方 + Key 管理接口（test_admin_keys 覆盖）
> - 详见 3 节对应行（20-01 ✅/20-02 🟡 增/20-04 🟡 改/30-02 🟡 增/30-06 ✅）、4 节差距分级汇总（2026-09-09 修订）、5 节 Phase 1/2 现状修订

### 7.3 引用文档



* 《AOS 技术架构图谱》01b 产品架构重排版方案（44 页书目、四层主链、五横切）

* furui-aios README（v2.0 定位）

* backend/app 全部 32 个 py 文件（函数级盘点）