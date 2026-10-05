# 傅瑞科技 · 企业 AI 操作系统 v2.0

> 参考 **Palantir Ontology / AIP·AOP / Claude Computer Use / Skills** 架构思想构建的 Deep Agent 编排型 OS。

## 架构特性

| 借鉴对象 | 在本系统中的落点 |
| --- | --- |
| **Palantir Ontology** | `backend/app/ontology/` — Object / Link / Function 三类语义对象，把 ERP/CRM/MES 数据抽象为可被 AI 直接操作的语义图，而非 SQL 表 |
| **Palantir AIP / AOP** | `backend/app/agents/orchestrator.py` — 意图路由 → 任务分发 → 多 Agent 协同 → 人类确认回路 → 流式回报 |
| **Claude Computer Use** | `backend/app/skills/` — 每个 AI 员工可调用真实工具（查询数据库、调用企业系统 API、生成文档） |
| **Claude Skills** | `backend/app/agents/<employee>.py` — 每个 AI 员工拥有专属 Skills 集合，行为由 Skills 驱动而非单纯 prompt |

## 目录结构

```
furui-aios/
├── frontend/                # Next.js 14 (App Router + TypeScript + Tailwind)
└── backend/                 # FastAPI (Python)
    └── app/
        ├── ontology/        # 数据语义层 (Object/Link/Function)
        ├── skills/          # Skills 工具箱 (Tools)
        ├── agents/          # AI 员工 + 编排引擎 (Orchestrator)
        └── api/             # REST + SSE 路由
```

## 启动

### Windows 一键启动

> 数据库是 **PostgreSQL**，不是 SQLite（生产库 `furui_aios`、隔离测试库 `furui_aios_test`，本机 PG 17 / `postgres:postgres123`）。
> **不要**绕开 `start_backend_pg.py` 直接跑 `uvicorn app.main:app`：那样 `DATABASE_URL` 为空会退回 SQLite `backend/data/app.db`，是另一套数据，演示时会看到旧/空数据。

在项目根目录双击 `start.bat`。后端经 `start_backend_pg.py` 钉死到 PG 生产库，前端起在 `:3001` 并自动打开。

> 前端用 `:3001` 是因为本机 `:3000` 被一个无关 Express 服务占用（响应 `X-Powered-By: Express` 且重定向 `/admin.html`）。
> 若 `:3000` 空闲，把 `start.bat` 里的 `-p 3001` 改回 `-p 3000` 即可。

### 手动启动

如果需要分别启动服务，请打开两个终端窗口：

```powershell
# 终端 1：启动后端（必须走 PG 包装脚本，否则退回 SQLite）
cd backend
.\venv\Scripts\python.exe start_backend_pg.py
```

```powershell
# 终端 2：启动前端
cd frontend
npm run dev -- -p 3001
```

启动后访问：

- 前端：http://localhost:3001
- 后端健康检查：http://localhost:8000/api/health

首次启动或依赖缺失时，先安装依赖：

```powershell
cd backend
pip install -r requirements.txt

cd ..\frontend
npm install
```

### macOS / Linux

在项目根目录执行 `./start.sh`。

```bash
# 1. 启动后端（start.sh 内部同样走 start_backend_pg.py）
cd backend
pip install -r requirements.txt
python start_backend_pg.py

# 2. 启动前端
cd ../frontend
npm install
npm run dev -- -p 3001      # http://localhost:3001
```

## 环境变量（`backend/.env`）

对话模型支持多家，**各配独立 Key**，在「管理员 → 模型管理」页可随时切换激活项：

```
DEEPSEEK_API_KEY=sk-xxx          # DeepSeek，默认激活
KIMI_API_KEY=...                 # Moonshot
QWEN_API_KEY=...                 # 通义千问
GLM_API_KEY=...                  # 智谱 GLM
OPENAI_API_KEY=...               # OpenAI
ACTIVE_LLM_PROVIDER=deepseek

DASHSCOPE_API_KEY=               # 语义检索（Embedding），留空则降级本地哈希向量

CUSTOM_BASE_URL=                 # 自定义（兼容 OpenAI 接口）
CUSTOM_MODEL_NAME=
CUSTOM_API_KEY=
```

> `DASHSCOPE_API_KEY` 为空时 RAG 语义检索降级为本地哈希向量——离线可跑，但检索质量下降。

## 回归测试

一律跑隔离库 **furui_aios_test**，绝不碰生产库：

```powershell
cd backend

# 1) 重建测试库（drop/create + alembic upgrade head + init_all + furui_app 授权）
.\venv\Scripts\python.exe tools_patch\reset_test_db.py

# 2) 全量回归（25 个脚本）
.\venv\Scripts\python.exe run_tests.py

# 只跑单个脚本
.\venv\Scripts\python.exe run_tests.py tests/test_asset_bundle.py
```

## 版本管理

仓库已初始化（Git 2.55，主分支 `master`，提交身份沿用全局配置）。首提交基线见 git log：

```
5289164 chore: 剔除首提交中误入的表格抓取 dump
3b86d67 chore: 初始化仓库并收口 TASK-017 交付发布与边缘协同
```

纳入版本库的只有**产品代码 + 文档 + 工程约定**（`.ai/`、`docs/`、`frontend/` 源码、`backend/` 应用代码与迁移、`sheets` 之外的模板）。以下一律不入库：依赖与构建产物（`node_modules/`、`.next*/`）、密钥（`.env`、`*.key`、`*.pem`，`backend/.env.example` 为白名单占位文件）、数据库与本地存储（`*.db`、`backend/data/`）、日志与一次性排查脚本、`sheets/`（表格抓取 dump）。

> 注意：`backend/.env` 里的 `DASHSCOPE_API_KEY` 仍未填，知识库语义检索当前走本地哈希向量兜底，填了才升级为 text-embedding-v3 真实语义向量（维度一致无需重建索引）。

`reset_test_db.py` 走的是**迁移链**（`alembic upgrade head`），不是 `create_all`：
这样测试库与任何新环境冷启动的路径完全一致，每次回归顺带验证迁移链可用。
它还会跑一遍 `bootstrap.init_all`（补角色/权限/账号/ontology）并给受限角色
`furui_app` 授权——后者是 RLS 测试的前提，缺了它应用连接就是超管、隔离策略不起作用。

`run_tests.py` 会把 `DATABASE_URL` 钉死到 `furui_aios_test`；脚本崩溃时判 `ERR`（不会误报成通过）。

当前基线：**25 脚本全绿，PASS 660 / FAIL 0 / SKIP 0**（含 `test_release_delivery` 37 断言）。

### 交付发布与边缘协同（TASK-017 / 70-03 + 80-01 + 80-02）

主导航两页（均需 `tool:config`）：

| 路由 | 干什么 |
|---|---|
| **/releases** | Release 列表与通道推进：draft → staging → production，召回、变更单、签名一致性徽标 |
| **/edge-sites** | Hub-Spoke 边缘站点：注册（**明文令牌只展示一次**）、心跳、应运行版本、待升级标记、注销 |

- 签名 `sha256(version\|manifest\|sbom)`，读接口回带 `signature_valid`，内容被改过会直接标红。
- 站点令牌服务端只存 `sha256(token)`，明文仅在注册响应出现一次 → 转到 API 直接调用：

```powershell
# 建版本并签名（POST 需 tool:config）
curl -X POST http://127.0.0.1:8000/api/releases -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"version":"2.6.0","channel":"draft","changes":[{"kind":"fix","summary":"心跳超时阈值改为 3 个周期"}]}'

# 站点注册（响应里的 token 只出现这一次）
curl -X POST http://127.0.0.1:8000/api/edge-sites/register -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"site_code":"EDGE-HANGZHOU-01"}'

# 查某站点「应运行版本」，from/to 不一致即待升级
curl http://127.0.0.1:8000/api/edge-sites/EDGE-HANGZHOU-01/sync -H "Authorization: Bearer $TOKEN"
```

协议细节见 `docs/HUB-SPOKE.md`。

> 排障提示：若为某一条测试改了代码又想确认「只有它变红/变绿」，直接单跑该脚本即可，
> 多数测试已能自助清理上一轮残留；剩下对库状态敏感的，先跑一次 `reset_test_db.py`。

**两个曾经踩过、别再信的旧结论**（均为已修正）：

1. 旧注释称 `alembic/env.py` 依赖 psycopg2、迁移链在 psycopg3 下跑不了——**是误判**。
   driver 本来就是 psycopg3（`PGDialect_psycopg`），真正让人以为坏掉的原因是拿
   `postgresql://`（SQLAlchemy 默认走 psycopg2）当 DSN，以及残留的 `create_all` 表
   让迁移撞 `DuplicateTable`。干净库上 17 个迁移（`8c9d0e1f2a3b` 链 + 新增 `9d1f4c7b2e8a`）一次跑通。
   想自己复验：`tools_patch/verify_migration_fresh.py` 会建一次性库 `furui_aios_migtest`
   跑完整迁移链再比对模型表数。
2. `test_asset_bundle` 曾长期「第一次绿、第二次红」——根因是它只靠重置库才能跑，
   且断言把 `seed_bundles` 的返回语义当成「目录总条数」。现已改为自清理 + 幂等口径。
