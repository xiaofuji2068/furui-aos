# DEPLOYMENT — 部署分区与网络信任边界（TASK-017 / 70-01）

> 适用版本：Furui AI OS v2.0（TASK-017 编排基线，2026-09-29 定稿）
> 目标形态：**核电等高危工业场景客户内网私有化部署**（离线/受限外联环境）
> 本文档是部署的分区与边界契约；编排文件见 `docker-compose.yml` / `Dockerfile.backend` / `Dockerfile.frontend`。

---

## 1. 部署分区

| 分区 | 组件 | 技术栈 | 默认端口 | 职责 |
|---|---|---|---|---|
| **P1 接入区** | 前端 Web | Next.js 14.2.13（App Router, TS） | 3000 | 用户交互唯一入口：页面/对话/画布/管理端；静态资源由 Next 服务 |
| **P2 应用区** | 后端 API | Python 3.13 + FastAPI + Uvicorn | 8000 | 业务 API / SSE 对话流 / Agent 编排 / 资产装配 / RLS 数据访问 |
| **P3 数据区** | 数据库 | PostgreSQL 17 | 5432 | 唯一持久化存储；RLS/FORCE 租户隔离；Alembic 管理 schema |
| **P4 运行区** | Agent/任务运行时 | 进程内（后端承载） | — | 长程任务状态机、审批、密钥 Keychain、Outbox/Ferry（70-03） |

> 说明：当前实现为「前端 + 后端 + 单库」三进程形态（P4 由后端进程承载，不单列服务）。
> 端口引用以 `docker-compose.yml` 为准；本机开发形态见 §5。

## 2. 网络信任边界

```
客户内网（Nuclear Plant OT 区段）
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  用户终端 ──HTTPS──▶ [P1 前端 :3000]                    │
│                          │                              │
│                          │ 仅内网 HTTP（禁止外网直连）      │
│                          ▼                              │
│                    [P2 后端 :8000]                       │
│                          │ 仅本机回环 / 同网段             │
│                          ▼                              │
│                    [P3 PG :5432]                         │
│                                                         │
│  外部互联网 ───────────────✗ 默认不可达（离线/白名单）       │
└─────────────────────────────────────────────────────────┘
```

**信任边界规则**：
1. **前端是唯一对用户开放的面**：所有数据访问经前端 → `/api/backend/:path*` 代理 → 后端；前端不直连数据库。
2. **后端不对外暴露**：绑定内网地址；SSE 对话流同源经前端代理；外部调用一律经前端网关。
3. **数据库零暴露**：PG 仅监听内网/回环；不映射公网端口；连接走 `DATABASE_URL`（含凭据，存环境变量/Secret，不落代码）。
4. **Agent 权限继承用户**：Agent/Tool 无独立数据库通道（架构约束：Agent→Tool→Service→Repository→DB）。
5. **外联白名单**：LLM / Embedding / 更新源默认离线；确需外联时按域名白名单放行并记录审计。
6. **升级窗口**：迁移（Alembic）仅在部署窗口执行，前端/后端先发后迁（Expand 先行，见 `UPGRADE.md`）。

## 3. 环境变量引用清单（唯一权威）

| 变量 | 生产建议值 | 用途 | 敏感 |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://app:****@pg:5432/furui_aios` | 主库连接（PSYCOPG 方言） | 🔴 必填 |
| `ACTIVE_LLM_PROVIDER` | `deepseek` / `qwen` / … | 当前对话提供方 | — |
| `DEEPSEEK_API_KEY` 等 6 项 | 留空走内置 mock | 对话模型 Key（也可在「模型管理」页配置） | 🔴 |
| `DASHSCOPE_API_KEY` | 留空走本地哈希 | Embedding（text-embedding-v3 升级路径） | 🔴 |
| `FRONTEND_URL`（如存在） | `http://frontend:3000` | 跨端引用 | — |

> 密钥治理已由 TASK-013 落地：`SecretRef / Keychain`（secret_entries 表 + RLS），生产可经环境变量注入外部 Secret，
> 不要求写 `.env` 文件。`.env.example` 见 `backend/.env.example`。

## 4. 版本引用（当前已锁定）

| 组件 | 版本 | 来源 |
|---|---|---|
| 后端依赖 | `backend/requirements.txt`（fastapi 0.115.0 / sqlalchemy 2.0.35 / alembic 1.19.2 / psycopg 3.3.5 …） | SBOM 生成源（`tools/sbom.py`） |
| 前端依赖 | `frontend/package-lock.json`（next 14.2.13 / react 18.3.1 / tailwindcss 3.4.13 …） | SBOM 生成源 |
| Schema 版本 | Alembic head `8c9d0e1f2a3b`（双库一致：生产 `furui_aios` / 测试 `furui_aios_test`） | `alembic history` |
| 系统版本 | 应用内 `/api/meta`（system_name / version / llm_mode / agent_count） | API 运行时 |

## 5. 本机开发形态（对照）

| 项 | 开发机（Windows） | 部署机（客户内网 Linux） |
|---|---|---|
| 前端 | `node_modules\.bin\next.cmd dev -p 3000 --turbo` | `next build && next start -p 3000`（Dockerfile.frontend） |
| 后端 | `venv\Scripts\python.exe start_backend_pg.py`（强制 PG） | `uvicorn app.main:app --host 0.0.0.0 --port 8000`（Dockerfile.backend） |
| 数据库 | 本机 PG 17（127.0.0.1:5432，postgres/postgres123） | 容器 PG 或客户已有 PG（凭据注入） |
| 迁移 | `alembic upgrade head`（双库） | 部署窗口执行，见 `UPGRADE.md` |

## 6. 部署前置检查（Checklist）

- [ ] `DATABASE_URL` 已注入（生产禁用 SQLite）
- [ ] `alembic upgrade head` 在目标库执行成功（head=8c9d0e1f2a3b）
- [ ] `GET /api/health` 四维全绿（DB / 对话模型 / 语义检索 / 系统）
- [ ] `GET /api/meta` 返回预期 system_name / version
- [ ] admin 登录后可访问资产中心 / Release 管理页（tool:config）
- [ ] 密钥已通过 Keychain 或环境注入（无明文 `.env` 提交）
- [ ] 外联白名单（如需）已配置并审计

---
*本文档与 `docs/HUB-SPOKE.md`（70-03）、`docs/UPGRADE.md`（80-03）配套使用。*
