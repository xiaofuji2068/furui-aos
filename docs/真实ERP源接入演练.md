# 真实 ERP 源接入演练（路线图第 3 步）

> 目标：验证「傅瑞最小真实连接器」能真正接住一个**外部** ERP/CRM REST 数据源，
> 把数据物化进 `erp_crm.db`，并让既有销售闭环（只读网关 → 脱敏 → 归因建单）在真实数据上跑通。

---

## 一、与 `test_connector.py` 的差异（本演练新增覆盖）

| 维度 | test_connector.py | 本次演练（test_real_erp_drill.py） |
|---|---|---|
| 调用路径 | 直接调 `connector.sync_source` | 走**生产接线** `store_data_sources.add_source` → `pull_source`（与 API `POST /api/data-sources/{id}/sync`、bootstrap 的 `FURUI_SYNC_ERP_SOURCE_ID` 门控**同一函数**） |
| 鉴权 | 无 | 连接器带 **Bearer Token**，本地 ERP 服务校验，错 token 返回 401 |
| 字段映射 | 默认列名=JSON 字段名 | ERP 返回**异名字段**，靠 `config.mapping` 归一化到表列 |
| 数据库 | 复用真实 `erp_crm.db`（末尾 `init_erp_db(force=True)` 还原） | **隔离临时库**（monkeypatch `ERP_DB_PATH`），绝不污染共享库 |
| 负向用例 | 无 | 错 token 时 `sync_source` 返回 error、不破坏既有数据 |

---

## 二、运行方式

```bash
cd backend
./venv/Scripts/python.exe tests/test_real_erp_drill.py
# 预期：PASS 8 / FAIL 0
```

脚本自检清单（8 项）：
1. `add_source` 成功注册 rest 数据源
2. `pull_source` 走真实同步且 `status == connected`
3. 拉数后 `orders` 入表（真实数据经只读网关可见）
4. **字段映射生效**（ERP 异名字段正确写入表列）
5. **PII 脱敏**在真实数据上照样生效（`contact_phone` → `137****1111`）
6. 真实数据可定位头号下滑客户（远图智能，降幅 7,680,000）→ 归因主线可触发建单
7. 错 token 被 401 拒绝、同步状态置为 `error`
8. 错误同步不破坏既有真实数据

---

## 三、如何指向一个「真实」ERP 端点

演练用的是本机 `http.server` 模拟的真实外部服务。要接入真实 ERP，只需改**数据源配置**，代码零改动：

### 1. 注册数据源（任选其一）
- 运行时通过 API：`POST /api/data-sources`（body 含 `type:"rest"` + `config`）；
- 或在 `store_data_sources._SOURCES` 里加一条 `type:"rest"` 的种子源。

### 2. `config` 字段说明
```json
{
  "endpoint": "https://erp.<你的域名>/api/snapshot",   // 必填，返回 {customers,products,sales_reps,orders:[...]}
  "method": "GET",                                       // 或 POST
  "auth": { "type": "bearer", "env": "ERP_API_KEY" },    // 生产从环境变量取密钥，绝不明文
  "mapping": {                                            // 可选；缺省列名=JSON字段名
    "orders": { "dt": "order_date", "amt": "amount", "cid": "customer_id" }
  },
  "timeout_sec": 10
}
```

> 端点返回结构兼容三种：`{实体:[...]}`、顶层数组（按 orders 处理）、或 `{"data":{实体:[...]}}`。
> 每个实体数组会被**全量幂等覆盖**进对应表（DELETE + INSERT），并复用既有表结构。

### 3. 密钥管理（重要）
- 生产态：`auth.env` 指向环境变量名（如 `ERP_API_KEY`），密钥只在运维侧配置，不进仓库。
- 演练/dev 态：允许 `auth.token` 内联（仅本地）。

### 4. 启动期自动拉数（env 门控，可选）
在 `bootstrap.init_all()` 启动时若设置：
```bash
export FURUI_SYNC_ERP_SOURCE_ID=real-erp      # 该 id 必须已注册且 type=rest、status≠disconnected
```
`bootstrap` 会在初始化 `erp_crm.db` 之后、调用 `pull_source(id)` 用真实数据覆盖四张销售表。
**未设置则该环境变量时，系统保持 mock，与旧版行为完全一致。**
真实同步失败不会阻断启动（try/except 兜底，mock 仍可用）。

---

## 四、闭环结论

- 连接器只负责在「同步」时把真实数据**物化**进 `erp_crm.db`（外部系统的缓存投影）。
- 所有 ERP 读取仍收敛在 `data_gateway.query()`（gw_query）的只读闸门 + PII 脱敏，
  真实数据上这些安全机制**天然生效**，无需为真实源另写逻辑。
- 下游销售归因主线（读 ERP → SQL 分析 → 审批 → 建单）在真实数据上可正常触发
  （演练中"远图智能"环比骤降被准确归因）。
- **零改动销售主线 / 分析 / 只读网关**——这是本连接器设计的落点，演练已验证成立。

---

## 五、注意事项

- ⚠️ `erp_crm.db` 路径写死在 `backend/data/erp_crm.db`（`data_gateway.ERP_DB_PATH`）。
  任何演练/测试若需写库，务必先 monkeypatch 到临时路径，避免污染共享库或影响 CI 基线。
- ⚠️ 真实接入前确认：ERP 接口可用、字段 mapping 对齐、令牌权限只读。
- ⚠️ 当前仅实现 REST JSON 一种连接器；JDBC / MQTT / SAP 等留作后续（连接器抽象已预留 `build_connector` 扩展点）。
