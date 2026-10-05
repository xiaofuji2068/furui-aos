# UPGRADE — 升级迁移与回滚（TASK-017 / 80-03）

> 前提：Alembic 迁移链已建立（TASK-003 / TASK-016），生产库 `furui_aios` 与测试库 `furui_aios_test`
> 当前 head 一致：`8c9d0e1f2a3b`。本文档把「如何升级 / 如何回滚」固化为可执行流程。

---

## 1. 迁移链现状（唯一权威）

| 版本 | 标题 | 引入任务 |
|---|---|---|
| `a2b3c4d5e6f7` | 低代码页面（app_pages） | TASK-015 |
| `a2b3c4d5e6f8` | RLS 对齐收口（续） | TASK-020 |
| `b7c8d9e0f1a2` | 本体唯一约束租户键（复合 company_id） | TASK-020 |
| `c3d4e5f6a7b8` | 密钥 Keychain（secret_entries） | TASK-013 |
| `d4e5f6a7b8c9` | Phase 3 RLS 贯通（40 表收口） | TASK-020 |
| `e5f6a7b8c9d0` | 系统设置落库（system_settings） | TASK-021 |
| `f6a7b8c9d0e1` | Logic 决策图（logic_graphs/nodes） | TASK-014 |
| `8c9d0e1f2a3b` | 资产装配（asset_bundles/installations） | TASK-016 |

> 以 `alembic history` 实际输出为准；任何「版本与上表不符」都视为风险信号，先核对再升级。

## 2. 升级三阶段（Expand / Backfill / Contract）

> 目标：变更可逆、旧代码兼容新 schema、数据迁移可补偿。

### Phase A — Expand（先扩后缩，旧代码兼容）
1. 编写迁移：**只加**（新表 / 新列 / 新索引 / 新约束可为 NULL 或带 server_default），不删不改旧结构。
2. 测试库先行：`cd backend && $env:DATABASE_URL='postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test'`
   → `alembic upgrade head` → 跑全量回归（0 失败）。
3. 生产库执行：`alembic upgrade head`（迁移窗口，见 §4）。

### Phase B — Backfill（数据回填）
- 新列/新表的存量数据回填：迁移内 `op.execute(...)` 幂等 SQL（`UPDATE ... WHERE col IS NULL` 或 `INSERT ... ON CONFLICT DO NOTHING`）。
- 回填必须幂等：重复执行结果一致；大表分批（`LIMIT` 游标）避免锁表。

### Phase C — Contract（缩列/删表，需旧代码全部下线后）
- 仅在 Expand+Backfill 全量上线并验证后执行；删除列/表走独立迁移，`down_revision` 保留回滚路径。
- 删除前检查：无运行中旧进程引用（前端/后端发版顺序见 §4 步骤 5）。

## 3. 回滚流程（downgrade + 补偿）

| 场景 | 动作 |
|---|---|
| **单版本回滚**（发布后 24h 内发现） | `alembic downgrade -1`（生产库）→ 重启后端 → 验证 `/api/health` + `/api/meta` → 前端回退旧构建 |
| **回滚到指定版本** | `alembic downgrade 8c9d0e1f2a3b`（目标版本号） |
| **数据补偿** | 迁移的 `down_revision` 方向应写反向 SQL（DROP 新表 / 恢复默认值）；无法自动补偿的数据先在迁移前导出备份（`pg_dump -t <table>`） |
| **迁移损坏** | 不要手动改 `alembic_version`；用 `alembic stamp` 仅在「建表方式 = create_all 的测试库」上对齐（生产库严禁 stamp 绕过） |

> 红线：**生产库禁止 `alembic stamp` 绕过真实迁移**（TASK-016 曾修复多 head 依赖链，见 CURRENT.md）。
> 测试库允许 create_all + stamp（已建立基线），生产库一律走真实 upgrade/downgrade。

## 4. 生产升级 SOP（内网私有化）

```text
1) 备份：pg_dump -h 127.0.0.1 -U postgres furui_aios > backup_YYYYMMDD.sql
2) 停写入窗口（或低峰期）：通知业务侧暂停写操作
3) 迁移：cd backend && alembic upgrade head      # 生产库 DATABASE_URL 指向 furui_aios
4) 后端发版：重启后端进程（健康检查 /api/health 四维全绿）
5) 前端发版：next build 产物替换 + next start 重启（BACKEND_URL 指向后端）
6) 验证：登录 → /api/meta 版本一致 → 资产中心/Release 页可用 → 抽样业务页无报错
7) 观察窗：发布后 24h 内保留回滚预案（§3），异常按场景回滚
```

## 5. 双库一致性检查

```text
# 生产
cd backend && $env:DATABASE_URL='postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios'
alembic current            # 期望 8c9d0e1f2a3b

# 测试
$env:DATABASE_URL='postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test'
alembic current            # 期望 8c9d0e1f2a3b
```

> 不一致处理：测试库以 `alembic upgrade head` 补齐；若测试库由 create_all 建表，则 `alembic stamp head`（仅限测试库）。

## 6. 补偿清单（当前未决项）

- B 类 215 处 NOT NULL 无 server_default 列（TASK-020 default 审计）：裸 SQL 写入会违反约束——后续迁移分批补齐 server_default。
- ~~新表加入后需补 RLS（asset_installations 已 RLS/FORCE；后续 releases/edge_sites 同规格）。~~
  已于 2026-10-05 随 TASK-017 收尾：releases（RLS 豁免，系统级）+ release_changes
  （RLS 豁免）+ edge_sites（RLS/FORCE，租户所有）由迁移 9d1f4c7b2e8a 一并建立，
  边界与 asset_bundles 一致（系统目录豁免、租户派生数据严格隔离）。
- 生产库 `sales_tasks / data_datasets / agent_tasks` 为演示 seed（company_id=16）：正式交付前由业务数据替换（TASK-015 遗留备注）。

---
*与 docs/DEPLOYMENT.md（70-01/70-02）、docs/HUB-SPOKE.md（70-03）配套。*
