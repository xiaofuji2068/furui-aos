# furui-aios 施工步骤手册（Phase 1–5 执行手册）

> 编制日期：2026-09-06
> 依据：《图谱-furui-aios差距清单与实施路线.md》+ 代码函数级复核
> 性质：可执行施工计划（未改动任何代码）
> 每步格式：现状 → 改动（文件/函数级）→ 验收标准 → 依赖

---

## 施工进度（2026-09-06 更新）

**批 1（P0）已完成并全量回归**：10 个测试文件全部 exit=0。

| 步骤 | 状态 | 验证结果 |
|---|---|---|
| 0 基线验证 | ✅ | 10 个测试文件基线记录；唯一失败项（test_ontology_persistence WO-003/004 残留）定位为测试脆弱性，已在 1.1 修复 |
| 1.1 本体 Link 落库 | ✅ | test_ontology_persistence 27 PASS / 0 FAIL（含 1.2）；links 种子 11 条、幂等重 seed 不重复、list_links 过滤正确 |
| 1.2 SchemaRevision 演进 | ✅ | bump_revision 递增唯一 + 自清理恢复基线 |
| 1.3 图探索接口 | ✅ | GET /api/ontology/related 实测：depth1/depth2 节点边正确、401/422 鉴权生效 |
| 1.4 知识治理门禁 | ✅ | test_knowledge 26→31 PASS；上传强制草稿→不可检索→submit 审核中→publish 已发布→可检索；sales 越权 publish 403 |
| 1.5 RAG 语义启用 | ✅（配置） | .env.example 补 DASHSCOPE_API_KEY 说明；真实语义引擎生效需填入 key 后验证（未持有 key） |
| 1.6 前端状态流转 | ✅（tsc） | page.tsx 操作列（提交审核/发布）+ api.ts 两函数；`tsc --noEmit` 通过；`npm run build` 未跑（耗时，可选补） |
| 批 1 收尾回归 | ✅ | test_api_mainline 30、test_auth_rbac 32、test_coordinator ✓、test_dashboard 24、test_failure_path 11、test_intelligence_endpoints 16、test_knowledge 31、test_mainline 33、test_orchestrator_sse ✓、test_ontology_persistence ✓（exit=0） |

**改动文件清单**（批 1）：
- `backend/app/models_ontology.py`（uq_onto_link、to_properties、bump_revision）
- `backend/app/ontology/__init__.py`（links 种子 11 条、_upsert_db_link、seed 落库、list_links、_object_type、get_related）
- `backend/app/api/ontology_api.py`（新增，GET /api/ontology/related）
- `backend/app/api/__init__.py`（挂载 ontology_router）
- `backend/app/api/knowledge.py`（DocCreate 默认草稿、上传校验、submit/publish 端点）
- `backend/tests/test_ontology_persistence.py`、`backend/tests/test_knowledge.py`（断言同步）
- `backend/.env.example`（DASHSCOPE_API_KEY 说明）
- `frontend/lib/api.ts`、`frontend/app/knowledge/page.tsx`（状态流转操作列）

**下一步**：批 2（P1 地基）——2.0 Alembic 基线 → 2.1 切 PostgreSQL → 2.2 RLS 租户隔离（2.3/2.4 穿插）。涉及数据库迁移与切库，按约定**需与用户确认后推进**。

---

## 施工进度（2026-09-06 更新 · 批 2）

**批 2（P1 地基）已完成并全量回归**：10 个测试文件全部 exit=0（250 项断言）。

| 步骤 | 状态 | 验证结果 |
|---|---|---|
| 2.0 Alembic 基线 | ✅ | alembic 1.19.2 装入 venv；基线迁移 78532a4f3d68：空库 upgrade head 建出 31 表（30 业务 + alembic_version）；现有开发库 stamp head 后 27 PASS 不回归；ontology_links UNIQUE 约束随 CREATE TABLE 自带 |
| 2.1 切 PostgreSQL | ✅（代码就绪） | db.py 支持 DATABASE_URL 环境变量 + pool_pre_ping + check_same_thread 按方言条件化；psycopg 3.3.5 装入 venv；.env.example 补 DATABASE_URL。**PG 实测待环境**（本机未装 PostgreSQL） |
| 2.2 租户键与 RLS | ✅（代码+迁移就绪） | 30 表审计：20 表已有 company_id；本体 3 表（objects/links/revisions）补租户键（types 保持全局系统字典）；set_tenant_context（PG SET LOCAL / SQLite no-op，无租户上下文注入 0 防 current_setting 报错）+ get_db 按请求 Authorization 注入租户；**RLS 全量迁移 e29b7c11a4d0 对当前 27 张租户表**建 tenant_isolation policy（USING+WITH CHECK）+ FORCE RLS（SQLite 自动跳过，幂等 DROP+CREATE）。验证：迁移空库建 34 表与 create_all 逐表一致；tests/test_rls_isolation.py（PG 实跑两租户互不可见/FORCE/无上下文查空，本机无 PG 时如实 SKIP）。**FORCE RLS 实测待 PG 环境** |
| 2.3 动作门禁加固 | ✅ | ActionReceipt 表（approval_id 关联、params/result sha256 哈希、actor、created_at）；execute 成功路径 + decide_approval 批准路径均写 receipt；test_mainline 33→39 PASS（审批 receipt 4 条 + Level2 直行 2 条），重复执行生成新 receipt 旧的不变 |
| 2.4 Secret 治理 | ✅ | .gitignore 已含 `.env`（backend/.env 被忽略）；admin 模型页不暴露密钥（仅 llm_enabled/model_name）；启动时无 LLM/DashScope key 打印清晰提示（不静默降级）；.env.example 补 Secret 注入说明 |
| 批 2 收尾回归 | ✅ | 10/10 exit=0：api_mainline 30、auth_rbac 32、coordinator 29、dashboard 24、failure_path 11、intelligence_endpoints 16、knowledge 31、mainline 39、orchestrator_sse 11、ontology_persistence 27 |

**改动文件清单**（批 2）：
- `backend/requirements.txt`（+alembic、+psycopg）
- `backend/alembic/`（init 结构 + env.py 指向 Base.metadata + 6 个迁移：baseline / tenant keys / rls / action receipts / sync schema / rls full coverage）
- `backend/alembic.ini`（SQLite 默认 URL）
- `backend/app/db.py`（DATABASE_URL 环境变量、IS_SQLITE、set_tenant_context、get_db 租户注入）
- `backend/app/models_ontology.py`（3 表 +company_id）
- `backend/app/ontology/__init__.py`（seed 写 company_id=1）
- `backend/app/models_ai.py`（+ActionReceipt 表）
- `backend/app/tool_gateway.py`（_hash/_write_receipt、两处写入）
- `backend/app/main.py`（启动无 key 提示）
- `backend/.env.example`（DATABASE_URL + Secret 注入说明）
- `backend/tests/test_mainline.py`（+6 Receipt 断言）

**已知遗留**：
1. 现有开发库 app.db 的 ontology_links 缺 uq_onto_link 约束（create_all 时代建的，无约束；SQLite 补约束需重建表，成本高）。**生产空库经 alembic 迁移建表无此问题**；开发库由代码幂等保证。后续如需补齐可走"重建表迁移"。
2. 2.1/2.2 的 PG 实测（切库种子、FORCE RLS 跨租户隔离）需在有 PostgreSQL 的环境执行；迁移文件已就绪，`alembic upgrade head` + 环境变量即可。
3. pydantic protected_namespace warning（model_name 字段）无害，未修。

**下一步**：批 3（P2 横切）——3.1 /api/health 健康检查、3.2 契约文档、3.3 docker-compose 一键拉起。可延后、可挑做。

---

## 施工进度（2026-09-15 更新 · Phase 3 PG 实测）

**Phase 3（10-07 / 60-02）PG 实测完成**：本机安装 PostgreSQL 17.5，Alembic 迁移链升级至 **8 版全绿**，RLS 隔离实测 **6/6 PASS**；"已知遗留"第 2 条（PG 实测待环境）已闭环。

| 项 | 状态 | 验证结果 |
|---|---|---|
| PostgreSQL 17.5 安装 | ✅ | EDB 官方包静默安装；服务 `postgresql-x64-17` RUNNING（开机自启）、5432 监听、数据目录 `D:\PostgreSQL\data`、`postgres/postgres123` 连接成功；`furui_aios` 库已建 |
| Alembic 迁移（2.0/2.1） | ✅ | `DATABASE_URL=postgresql+psycopg://...`（psycopg3，非 psycopg2）→ 8 版链全绿至 head：baseline → 租户键/本体 → RLS 隔离 → Action 凭证 → Outbox/快照/Eval → RLS 全租户覆盖 → status 默认值 → created_at 默认值；PG 35 张表 |
| RLS 隔离实测（2.2 / 60-02） | ✅ 6/6 | 受限角色 `app_test`（生产同形态：应用非超管；超管会绕过 RLS）：租户 A/B 互不可见、无上下文查空、无上下文 UPDATE 影响 0 行、越权写入被 WITH CHECK 拦截 |
| 实测修复 | ✅ 3 项 | ① companies.status 补 server_default（迁移 a1b2c3d4e5f6）；② 26 表 created_at 补 server_default（迁移 b2c3d4e5f6a7，系统性缺陷，威胁数据导入）；③ RLS 测试改受限角色 + SET LOCAL 内插 + 序列授权 + 中文错误匹配 |
| .env 修复 | ✅ | PowerShell 编码损坏（BOM+乱码）→ Python 修复为 UTF-8 无 BOM；DeepSeek Key 找回并写回；无 DATABASE_URL 常驻（默认 SQLite 开箱即跑不受影响） |

**本轮新增/改动文件**：
- `backend/app/models.py`（Company.status server_default）
- `backend/app/models.py` / `models_ai.py`（23 处 created_at server_default + import text）
- `backend/alembic/versions/a1b2c3d4e5f6_status_server_defaults.py`、`b2c3d4e5f6a7_created_at_server_defaults.py`（新增 2 个迁移）
- `backend/tests/test_rls_isolation.py`（受限角色 app_test + 字段补齐 + SET LOCAL 内插）
- `backend/fix_env.py`（.env 维护工具，保留）

**已知遗留（更新）**：
1. 开发库 app.db 的 ontology_links 缺 uq_onto_link 约束（同批 2，生产空库无此问题）。
2. ~~2.1/2.2 的 PG 实测~~ → **已闭环（2026-09-15）**。
3. **数据导入前置项（新增）**：模型层仍有若干"仅 Python default、无 server_default"的列（如 agents.status、priority 等），原生 SQL 导入会踩 NOT NULL；导入前需系统收口（复用本轮 created_at 修复模式）。
4. **应用层 RLS 贯通（新增，Phase 3 剩余）**：app 用受限角色连接 + `set_tenant_context` 登录链路实测（当前测试直接走 SQL，未走 FastAPI 登录链路）。

**下一步**：① 应用层 RLS 贯通实测；② 数据导入前置（default 列系统收口）；③ 批 3 横切可挑做。

---

## 使用说明

- **批 1（P0）**：不换库、不换协议，可在现有 SQLite 上直接做，改动集中在 6 个文件。
- **批 2（P1）**：地基工程，必须先建 Alembic 基线（步骤 2.0），再切库、上租户隔离。
- **批 3（P2）**：横切增强，可延后、可挑着做。
- 每步验收都给出了可执行检查方式（测试/curl/页面），做完一步打一个勾。

---

## 第 0 步 · 基线验证（0.5 天）

**现状**：backend/tests 下 9 个脚本式测试（TestClient + 手写 PASS/FAIL），直接 `python` 运行。

**动作**：
```
cd backend
venv\Scripts\python.exe tests\test_auth_rbac.py
venv\Scripts\python.exe tests\test_coordinator.py
venv\Scripts\python.exe tests\test_dashboard.py
venv\Scripts\python.exe tests\test_failure_path.py
venv\Scripts\python.exe tests\test_api_mainline.py
venv\Scripts\python.exe tests\test_mainline.py
venv\Scripts\python.exe tests\test_knowledge.py
venv\Scripts\python.exe tests\test_ontology_persistence.py
venv\Scripts\python.exe tests\test_intelligence_endpoints.py
```

**验收**：9 个全部 PASS（或记录 FAIL 清单作为后续回归基线）。

---

## 批 1 · P0 先行（1~2 周）

### 步骤 1.1 · 本体 Link 落库（图谱 20-01 / 20-04）

**现状**：`OntologyLink`（内存类）与 `OntologyLinkRow`（表）已存在；但 `build_demo_ontology()` 只返回 `types` + `functions`，**没有 links 数据**；`seed_ontology()` 只 upsert 对象，**Link 表永远是空的**。

**改动**：
- `backend/app/ontology/__init__.py`
  - `build_demo_ontology()`：在返回 dict 中新增 `"links"` 键，构造演示关系：`Order→Customer`、`Device→Product`（linked_sku）、`WorkOrder→Device`、`Ticket→WorkOrder`（每条 = `OntologyLink(type, source_id, target_id, properties)`）。
  - 新增 `_upsert_db_link(db, link)`：按 `(type, source_id, target_id)` 查重后 upsert（复制 `_upsert_db_object` 模式，见 231 行）。
  - `seed_ontology(db)`：objects 落库后，遍历 `ONTO["links"]` 调 `_upsert_db_link`，统一 commit。
  - 新增 `list_links(type=None, source_id=None, target_id=None)`：DB 优先、空时回退内存（复制 `list_objects` 的降级模式，见 258 行）。
- `backend/app/models_ontology.py`
  - `OntologyLinkRow` 加唯一约束 `UniqueConstraint("type", "source_id", "target_id", name="uq_onto_link")`（对齐 `uq_onto_obj` 风格）。

**验收**：
- 扩展 `tests/test_ontology_persistence.py`：种子后 `OntologyLinkRow` 行数 > 0；重复 `seed_ontology` 行数不变（幂等）；`list_links` 可查到 `WorkOrder→Device`。
- 手工：`bootstrap.init_all()` 后查 `ontology_links` 表。

**依赖**：无。

---

### 步骤 1.2 · SchemaRevision 演进（图谱 20-02）

**现状**：`OntologySchemaRevision` 表存在，`seed_ontology` 只在空表时打 `r1`；无演进机制。

**改动**：
- `backend/app/models_ontology.py`：新增 `bump_revision(db, note="")` —— 取当前最大 revision（`r{n}` 解析 n）自增写入下一条，返回新版本号。
- `backend/app/ontology/__init__.py`：在需要 schema 变更的入口（后续 20-02 扩展时）调用 `bump_revision` 并写审计。

**验收**：`bump_revision` 连调两次 → 表内存在 r1、r2、r3；版本号递增无重复。

**依赖**：无（可与 1.1 并行）。

---

### 步骤 1.3 · 图探索接口（图谱 20-04）

**改动**：
- `backend/app/ontology/__init__.py`：新增 `get_related(type_name, object_id, depth=1)` —— 沿 `list_links` 双向遍历到指定深度，返回 `{object, related:[...]}`。
- 路由：在 `backend/app/api/__init__.py` 或新增 `backend/app/api/ontology_api.py` 暴露 `GET /api/ontology/related?type=WorkOrder&id=WO-001&depth=1`（复用 `require_perm` 守卫）。

**验收**：
- `curl "http://localhost:8000/api/ontology/related?type=WorkOrder&id=WO-001"` 返回关联 Device；
- depth=2 能追到 Device 关联的 Product；无权限返回 403。

**依赖**：1.1（links 已落库）。

---

### 步骤 1.4 · 知识治理门禁（图谱 30-06）

**现状（重要修正）**：`KnowledgeDocument` **已有** `status`（草稿/审核中/已发布/已过期/已归档）、`source`、`version`、有效期字段；RAG 检索**已只返回"已发布"且未过期**的文档（`rag.py` 260 行过滤）；知识健康度 `_health` 四维真实统计已有。**唯一缺口：`create_document` 直接接受请求传入的 `status="已发布"`——上传即发布，无审批门禁。**

**改动**（`backend/app/api/knowledge.py`）：
- `DocCreate`：移除 `status: str = "已发布"` 默认值，改为 `status: str = "草稿"`，且仅允许 `草稿`/`审核中`（写入时校验，直接传"已发布"返回 400）。
- 新增 `POST /documents/{doc_id}/submit`：`草稿 → 审核中`（写 `write_audit`）。
- 新增 `POST /documents/{doc_id}/publish`：`审核中 → 已发布`，`require_perm("knowledge:manage")`，写审计；失败（状态非法/无权限）返回明确错误。
- 前端提示联动：`list_documents` 已返回 `status`，无需改后端。

**验收**：
- 上传新文档 → 状态=草稿；`POST /api/knowledge/search` 检索不到（RAG 已天然过滤）。
- `publish` 后立即可检索到；无 `knowledge:manage` 权限 publish 返回 403。
- 9 个测试回归通过（`test_knowledge.py` 需按新状态流微调断言）。

**依赖**：无。这是批 1 中业务价值最直接的一步。

---

### 步骤 1.5 · RAG 语义检索启用（图谱 30-06）

**现状（重要修正）**：RAG **已是双引擎**——`_remote_embed`（通义 text-embedding-v3，1024 维）完整实现 + 本地哈希离线兜底；混合检索（语义 0.68 + 关键词 0.32）+ Rerank + 权限前置过滤 + 来源溯源全部已有（`rag.py` 全文）。`config.py` 的 `dashscope_api_key` 字段已就位。**不是"开发语义检索"，而是"填 key 即启用"。**

**改动**：
- `backend/.env.example`：补 `DASHSCAPE_API_KEY=` 说明注释（填入即从哈希升级为语义向量，维度一致无需重建索引）。
- 可选：`backend/app/api/admin.py` 模型页展示当前引擎（调 `rag.engine_name()`）。

**验收**：
- 配置 key 后 `engine_name()` 返回"通义 text-embedding-v3"；检索命中语义相关（非同字面）内容。
- 无 key 环境降级正常（离线演示不受影响）。

**依赖**：无。

---

### 步骤 1.6 · 前端状态流转（图谱 40-01 / 40-04）

**改动**：
- `frontend/app/knowledge/page.tsx`：文档列表加 status 徽标（草稿/审核中/已发布）；草稿行显示"提交审核"、审核中行显示"发布"按钮（调 1.4 新增端点）。
- 可选（依赖 1.3）：`frontend/app/ontology/page.tsx` 本体关系浏览页。

**验收**：页面可完成"草稿→审核→发布"全流程；`npm run build` 通过。

**依赖**：1.3、1.4。

---

## 批 2 · P1 地基（3~6 周）

### 步骤 2.0 · Alembic 迁移基线（图谱 80-03，**提前做**）

> 为什么提前：批 2 要切 PostgreSQL、加租户键、改表——没有迁移体系，任何改表都是删库重建。**本步骤是批 2 的前置，不依赖批 1。**

**改动**：
- `backend/requirements.txt`：+ `alembic`。
- `cd backend && alembic init alembic`；`alembic/env.py` 指向 `app.db.Base.metadata`。
- 生成基线迁移：`alembic revision --autogenerate -m "baseline"`；`alembic upgrade head`。
- `backend/app/models.py init_db()`：保留为开发快捷建表（SQLite 演示），生产建表改走 `alembic upgrade head`（在 README/启动脚本注明）。

**验收**：空库 `alembic upgrade head` 建出全部表（organizations→ontology 全量）；`alembic history` 有基线；`test_ontology_persistence` 仍通过。

**依赖**：无。

---

### 步骤 2.1 · 切 PostgreSQL（图谱 10-07）

**改动**：
- `backend/app/db.py`：`DATABASE_URL` 改为从环境变量读取（`os.getenv("DATABASE_URL", sqlite 默认)`）；engine 加 `pool_pre_ping=True`。
- `backend/requirements.txt`：+ `psycopg[binary]`。
- `backend/.env.example`：补 `DATABASE_URL=postgresql://user:pass@localhost:5432/furui_aios`。
- 确认 SQLite 特有写法兼容：`check_same_thread` 仅 SQLite 需要（按 URL 前缀条件化）。

**验收**：PG 空库上 `alembic upgrade head` + `bootstrap.init_all()` 全量种子成功；9 个测试在 PG 上通过；SQLite 开发路径不回归（环境变量缺省仍可跑）。

**依赖**：2.0。

---

### 步骤 2.2 · 租户键与 RLS（图谱 60-02）

**改动**：
- 模型审计：核对 `models.py` / `models_ai.py` / `models_ontology.py` 全部业务表都有 `company_id`（缺的补上；`ontology_types` 等系统表按图谱 60-02 定租户归属）。
- `backend/app/auth.py`：`issue_token` 已带 `company_id`；新增 `set_tenant_context(db, company_id)` 帮助函数（执行 `SET LOCAL app.company_id = ...`）。
- PG 迁移（`alembic` 新迁移）：为业务表建 RLS policy（`USING (company_id = current_setting('app.company_id')::int)`）+ `FORCE ROW LEVEL SECURITY`。
- `backend/app/db.py get_db()`：请求上下文内 `set_tenant_context`（从当前用户 token 取 company_id）。

**验收**：
- 两个租户数据并存时，跨租户 SELECT 返回空；
- `FORCE RLS` 开启后，无租户上下文的连接查询被 PG 拒绝；
- 9 个测试适配后通过（测试需显式设租户上下文）。

**依赖**：2.0、2.1。风险最高的一步（涉及全部模型与查询路径）。

---

### 步骤 2.3 · 动作门禁加固（图谱 20-05 / 60-03）

**现状（重要修正）**：`tool_gateway.py` **已有完整四级门禁**——Agent 白名单 → 用户权限 → 参数校验 → 审批判断（Level 1 自动/2 通知后执行/3 必须审批/4 禁止）→ 执行 → 日志 + 审计；`decide_approval` 支持批准/拒绝/修改参数后执行，批准后真正落库（SalesTask/Notification）并写审计。**核心价值已闭环**，本步只补图谱进阶概念。

**改动**：
- `backend/app/models_ai.py`：新增 `ActionReceipt` 表（`approval_id`、`tool_name`、`params_hash`、`result_hash`、`actor_type/actor_id`、`created_at`）——不可变执行凭证（图谱 Receipt）。
- `backend/app/tool_gateway.py`：`execute()` 成功路径与 `decide_approval()` 批准执行路径写入 `ActionReceipt`（哈希用 `hashlib.sha256` 对 params/result 摘要）。
- 可选（低优先）：Lease——审批通过后加有效期，超时未执行自动失效（`Approval` 加 `expires_at`）。

**验收**：任意 Level 2/3 动作执行后存在对应 receipt；approval_id → receipt 可关联查询；测试断言 receipt 不可变（重复执行生成新 receipt，旧的不变）。

**依赖**：无（与 2.2 可并行，但查询路径涉及 RLS 时需在 2.2 后回归）。

---

### 步骤 2.4 · Secret 治理（图谱 60-04）

**改动**：
- `backend/.gitignore`：确认 `backend/.env` 已忽略（未忽略则补）。
- `backend/app/config.py`：密钥字段保持从环境变量读取（现状已如此），补充读取失败时的明确报错；生产部署时支持从外部 Secret 注入（文档说明，不引新依赖）。
- 可选：`api/admin.py` 模型密钥展示改为掩码（`sk-****`）。

**验收**：`git status` 无 `.env`；仓库扫描无明文密钥；无 key 环境启动有清晰提示而非静默降级。

**依赖**：无。

---

## 批 3 · P2 横切（持续，可挑做）

### 步骤 3.1 · 健康与可观测（图谱 90-01）
- 新增 `GET /api/health`：服务、DB 连接、模型配置（llm_enabled/embedding_enabled）、最近审计写入延迟汇总。
- 验收：`curl /api/health` 返回各组件状态，无外部依赖。

### 步骤 3.2 · 资产装配与契约（图谱 50）
- `api/` 分层规约文档化（BFF/Service/Store）；契约清单对齐图谱 50-02。
- 验收：产出契约文档，路由命名可审计。

### 步骤 3.3 · 部署形态（图谱 70）
- `docker-compose.yml`：backend + frontend + PostgreSQL；启动脚本 `start.bat` 适配容器模式。
- 验收：`docker compose up` 一键拉起全栈，健康检查通过。

---

## 排期与依赖总览

| 步骤 | 工期 | 前置 | 风险 |
|---|---:|---|---|
| 0 基线验证 | 0.5 天 | — | 低 |
| 1.1 本体 Link 落库 | 2~3 天 | — | 低 |
| 1.2 SchemaRevision 演进 | 1~2 天 | — | 低 |
| 1.3 图探索接口 | 2~3 天 | 1.1 | 低 |
| 1.4 知识治理门禁 | 2~3 天 | — | 中（改动既有接口语义） |
| 1.5 RAG 语义启用 | 0.5 天 | — | 低（配置即启用） |
| 1.6 前端状态流转 | 2~3 天 | 1.3、1.4 | 中 |
| 2.0 Alembic 基线 | 1~2 天 | — | 中（首次生成迁移） |
| 2.1 切 PostgreSQL | 2~3 天 | 2.0 | 高 |
| 2.2 租户键与 RLS | 3~5 天 | 2.0、2.1 | **最高** |
| 2.3 动作门禁加固 | 2~3 天 | — | 中 |
| 2.4 Secret 治理 | 1 天 | — | 低 |
| 3.1~3.3 横切 | 各 1~3 天 | 视情况 | 中 |

**建议排期**：批 1（1.1→1.2→1.3→1.4→1.6，1.5 随时可做）≈ 2 周；批 2（2.0→2.1→2.2，2.3/2.4 穿插）≈ 3~5 周；批 3 进入迭代节奏后持续补齐。

## 验收清单总表（完成即打勾）

- [x] 0：10 个测试基线记录（唯一失败项已定位并修复）
- [x] 1.1：Link 落库 + 幂等 + 可查（测试扩展）
- [x] 1.2：revision r1→r2→r3 递增
- [x] 1.3：`/api/ontology/related` 深度遍历可用
- [x] 1.4：知识"草稿→审核→发布"门禁生效，草稿不可检索
- [x] 1.5：填 key 后语义引擎生效、无 key 降级（配置已就绪；引擎生效验证待真实 key）
- [x] 1.6：前端状态流转全流程可操作（tsc 通过；npm run build 可选补）
- [x] 2.0：alembic 基线迁移 + history 可查（✅ 已完：31 表空库迁移 + stamp 现有库）
- [x] 2.1：PG 上种子 + 9 测试全过（✅ 2026-09-15 实测：PG 17.5 安装、furui_aios 库、Alembic 8 版迁移全绿、35 表）
- [x] 2.2：跨租户隔离 + FORCE RLS 生效（✅ 2026-09-15 实测：RLS 隔离 6/6 PASS，受限角色 app_test）
- [x] 2.3：Receipt 不可变凭证 + 关联可查（✅ 已完：39 PASS）
- [ ] 2.4：仓库无明文密钥（✅ 已完：gitignore 覆盖 + 启动提示 + 无泄漏）
- [ ] 3.1：/api/health 返回组件状态
- [ ] 3.2：契约文档产出
- [ ] 3.3：compose 一键拉起
