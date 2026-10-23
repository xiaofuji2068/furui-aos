# 真实 ERP 接入 · 上线手册

> 目标：把销售主线从 mock 数据切到**真实 ERP 源**，跑在真数据上的端到端闭环。
> 适用对象：傅瑞科技·企业 AI 操作系统（`furui-aos`）。
> 最后更新：2026-10-22

---

## 0. 一句话定位

连接器**只负责在「同步」时把真实数据物化（materialize）进 `backend/data/erp_crm.db`**（外部系统的缓存投影）。
下游的销售分析、只读网关、PII 脱敏、归因建单**全部原样复用**——接真实源不需要改任何业务代码。

```
真实 ERP ──REST/CSV──▶ connector.pull() ──▶ materialize() ──▶ erp_crm.db
                                                            │
                                            data_gateway.query()（只读 + 脱敏）
                                                            │
                                              销售主线 / 归因 / 建单
```

---

## 1. 唯一硬卡点（开干前必须拿到）

| 项 | 说明 | 谁给 |
| --- | --- | --- |
| **ERP 端点 URL** | REST 地址，返回 JSON（结构见 §3） | 用户 / 客户 IT |
| **鉴权方式与凭证** | `bearer` 或 `apikey` + 密钥 | 用户 / 客户 IT |
| **字段映射**（如有异名） | ERP 字段名 ≠ 表列名时给出 `ERP_MAPPING_JSON` | 对照 §3 表结构 |

> 没有这三项，端到端闭环无法跑在真数据上。其余工作（重试加固、脚本、本手册）已在本仓库就绪。

---

## 2. 两种连接器

| 类型 | `type` | 何时用 | 配置要点 |
| --- | --- | --- | --- |
| REST JSON | `rest` | ERP 提供 API（最常见） | `endpoint` / `method` / `auth` / `mapping` / `timeout_sec` / `retries` / `backoff_sec` |
| CSV 文件 | `file` | ERP 仅能导出 CSV（Excel 导出等） | `base_dir` / `files` / `mapping` / `encoding`（默认 utf-8-sig） |

`rest` 连接器已具备**指数退避重试**（应对外网抖动）：
- 网络错误 / 超时 / **5xx** → 重试 `retries` 次，第 n 次等待 `backoff_sec * 2^n` 秒；
- **4xx（含 401/403 鉴权错）→ 不重试，立即上报**（重试无意义且会刷屏）。

---

## 3. ERP 返回结构（三类归一化写法都支持）

连接器 `pull()` 兼容三种 JSON 形态，任选其一：

1. **分实体**：`{ "customers":[...], "products":[...], "sales_reps":[...], "orders":[...] }`
2. **顶层数组**（默认当 `orders`）：`[ {...}, {...} ]`
3. **嵌套**：`{ "data": { "customers":[...], "orders":[...] } }`

### 四张目标表与列（字段映射基准）

| 实体 | 表 | 关键列 |
| --- | --- | --- |
| customers | customers | id, name, level, region, industry, contact_name, contact_phone, owner_rep_id, created_at |
| products | products | id, code, name, category, unit_price, cost |
| sales_reps | sales_reps | id, name, region, hire_date |
| orders | orders | id, order_no, customer_id, product_id, rep_id, region, qty, amount, status, order_date |

> 只有上表登记的列允许写入（防 JSON 注入未知列）；**主键 `id` 缺失的行会被丢弃**。

### 字段映射示例（ERP 异名字段 → 表列）

当 ERP 字段名与表列不同，用 `ERP_MAPPING_JSON` 指定，例如：

```json
{
  "customers": {"cust_id":"id","cust_name":"name","grade":"level","area":"region",
                "sector":"industry","contact":"contact_name","phone":"contact_phone",
                "rep_id":"owner_rep_id","since":"created_at"},
  "orders": {"oid":"id","so_no":"order_no","cid":"customer_id","pid":"product_id",
             "rid":"rep_id","area":"region","qty":"qty","amt":"amount",
             "st":"status","dt":"order_date"}
}
```

---

## 4. 一键演练 / 上线（env 驱动脚本）

脚本：`backend/scripts/sync_real_erp.py`，**密钥只从环境变量读取，绝不写进配置文件**。

### 4.1 演练（DRY-RUN，不落库）

```bash
cd backend
ERP_ENDPOINT=https://erp.xxx.com/api/sales \
ERP_AUTH_TYPE=bearer ERP_API_KEY=xxxx \
ERP_MAPPING_JSON='{...见上文...}' \
./venv/Scripts/python.exe scripts/sync_real_erp.py
```

输出各实体拉取到的记录数，**不写库**。用来验证：端点通、鉴权过、字段映射对、记录数合理。

### 4.2 真实落库（确认无误后）

在 4.1 命令末尾追加 `--yes`：

```bash
ERP_ENDPOINT=https://erp.xxx.com/api/sales \
ERP_AUTH_TYPE=bearer ERP_API_KEY=xxxx \
ERP_MAPPING_JSON='{...}' \
./venv/Scripts/python.exe scripts/sync_real_erp.py --yes
```

- 走 `connector.sync_source`，与前端 **API `POST /api/data-sources/{id}/sync`**、`bootstrap` 的 `FURUI_SYNC_ERP_SOURCE_ID` 门控**完全一致**；
- `materialize` 是**幂等全量覆盖**四张销售表，重复跑安全；
- 下游只读网关的 PII 脱敏 + 只读闸门在真实数据上自动复用。

### 4.3 也可用 CSV 连接器

若 ERP 只能导出 CSV，把文件放进某目录后：

```bash
ERP_ENDPOINT=  # 留空，改用 file 类型
# 直接改脚本或调 connector.CsvFileConnector({"base_dir":"/path/csv","mapping":{...}})
```

---

## 5. 安全约束（上线前自查清单）

- [ ] 密钥只走环境变量 / `auth.env`，**不进代码、不进配置库、不进 git**；
- [ ] 先在 DRY-RUN 验证字段映射与记录数，再 `--yes`；
- [ ] 确认 `erp_crm.db` 是缓存投影（可随时全量重建），**不是权威源**；
- [ ] 下游只读网关五道闸门（只读 / 白名单 / SQL 白名单 / 限流 / 脱敏）在真实数据上生效；
- [ ] `sync_source` 失败返回 `error` 且不破坏既有数据（已测：错 token 401 不污染）；
- [ ] 外网抖动由 `retries` / `backoff_sec` 兜底，不会一次失败就断同步。

---

## 6. 验收回归（本仓库已含）

```bash
cd backend
./venv/Scripts/python.exe tests/test_connector.py          # 物化 + 网关可读 + 脱敏 + 归因
./venv/Scripts/python.exe tests/test_real_erp_drill.py     # 生产接线 + 鉴权 + 映射 + 闭环
./venv/Scripts/python.exe tests/test_connector_retry.py    # 5xx 重试 / 401 不重试 / 网络不可达
```

三条全绿，即代表「接真实 ERP 这条路」在代码层已闭环，只差 §1 的真实端点与凭证。
