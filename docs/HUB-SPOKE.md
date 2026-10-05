# 中心-边缘协同 Hub-Spoke（70-03）

> 配套文档：`docs/DEPLOYMENT.md`（部署形态 / 信任边界）、`docs/UPGRADE.md`（升级与回滚）
> 落地位置：迁移 `9d1f4c7b2e8a`（建 `releases` / `release_changes` / `edge_sites`），
> 代码在 `backend/app/models_release.py` + `backend/app/release.py` + `backend/app/api/release_api.py`。

## 为什么要 Hub-Spoke

核电/辐射类客户的私有化交付是**中心研发 + 现场边缘**的两段式：

| 角色 | 在哪 | 干什么 |
|---|---|---|
| **Hub（中心）** | 傅瑞内网 / 客户总部机房 | 研发构建 Release、管通道、待升级站点清单 |
| **Spoke（边缘）** | 核现场、辐射站、无外网的内网机 | 跑着某个版本的产品 Agent，定期心跳、按需拉新版本 |

问题不是"能不能传文件"，而是三件硬事：

1. **现场机器可能永远连不进中心**（单向网闸 / 内网离线），所以同步必须是 **Spoke 主动拉**（`GET /sync`），不能是中心推。
2. **"现场跑的是哪个版本"必须中心可见**——否则出事时说不清口径。
3. **升级这件事要可审计**：哪个站点、什么时候、从哪个版本升到哪个版本。

## 数据模型与权限边界

| 表 | 归属 | RLS | 说明 |
|---|---|---|---|
| `releases` | 系统级交付目录 | **豁免**（跨租户共享） | 一个 Release 是产品版本，不属于某家客户；同 `asset_bundles` / `permissions` 先例 |
| `release_changes` | 系统级 | **豁免** | 按 release 逐条变更，供交付审计按 kind 过滤/计数 |
| `edge_sites` | **租户所有** | **RLS/FORCE + policy** | policy：`company_id = NULLIF(current_setting('app.company_id',true),'')::int` |

> 区分口径（`app/models_release.py` 文件头已写明）：
> `assets.py` 管「租户装了哪些页面/Logic 资产」（50 资产装配）；
> 本模块管「产品版本怎么发到各环境、再下发到客户边缘站点」（70/80 交付）。

## 协议（三段）

### 1. 注册 — Hub 侧发起，令牌只出现一次

```http
POST /api/edge-sites/register
Authorization: Bearer <admin token>
Content-Type: application/json

{ "site_code": "EDGE-HANGZHOU-01", "name": "杭州现场机",
  "site_type": "edge", "endpoint": "http://10.20.3.11:8000",
  "metadata": { "network": "air-gapped" } }
```

- `site_code` 唯一（`uq_edge_sites_code`），重复注册 **409**。
- 服务端 `secrets.token_urlsafe(32)` 生成令牌，`sha256(token)` 入库，**明文只在本次响应里出现一次**
  （`_site_dto(site, token=token)` 的 `token` 分支只有这样一条出口，其它任何接口都不带）。
- 新站点默认挂当前最新 Release（`release_id` + `version` 直接对齐），状态 `registered`。
- 响应体含 `token` / `site_code` / `status` / `release_id`。

### 2. 心跳 — Spoke 侧主动上报（续约 + 版本 + 运行状态）

```http
POST /api/edge-sites/EDGE-HANGZHOU-01/heartbeat
Content-Type: application/json

{ "token": "<注册时拿到的明文令牌>",
  "version": "1.4.0",
  "status": "healthy",
  "endpoint": "http://10.20.3.11:8000" }
```

- 校验：`sha256(token) == site_token_hash`，否则 **403**（令牌错误）。
- 成功：置 `status=online`、刷新 `last_heartbeat_at`、`version` 更新、运行时状态写进 `metadata.runtime_status`。
- **默认不强制带令牌**——跨网段部署的心跳可能拿不到令牌。宁可少一道校验，也不要让边缘站点因为拿不到令牌就永远 `offline`。

### 3. 同步 — Hub 下发「应运行」版本，Spoke 据此升级

```http
GET /api/edge-sites/EDGE-HANGZHOU-01/sync
```

```json
{
  "site_code": "EDGE-HANGZHOU-01",
  "company_id": 16,
  "from_version": "1.4.0",
  "to_version": "2.5.0",
  "upgrade_needed": true,
  "release": { "id": 3, "version": "2.5.0", "channel": "production",
               "status": "promoted", "signature": "…", "signature_valid": true,
               "manifest": {}, "sbom": [], "changes": [{"kind":"fix","summary":"…"}] },
  "served_at": "2026-10-05T09:40:00Z"
}
```

`from_version`（站点已运行）与 `to_version`（应运行）不一致 → `upgrade_needed=true`，Spoke 侧据此拉包升级；一致则无需动作。未知站点 **404**。

## Release 状态机（80-01 / 80-02）

`channel`（投放到哪条流水线）与 `status`（生命周期）**正交**，避免「staging 上的版本也叫 promoted」这种歧义：

| channel | draft → staging → production（终点） |
|---|---|
| status | `draft` / `promoted` / `recalled` / `superseded` |

- `POST /api/releases/{id}/promote`：走 `PROMOTE_ORDER` 显式白名单，**禁止非法跳态**（如 draft 直接 production → 409）；推走旧档会把旧的 `promoted` 自动置 `superseded` 留痕。
- `POST /api/releases/{id}/recall`：**仅 `promoted` 可召回**；重复召回同态返回，不改数据。
- `GET /api/releases?channel=production` 按通道过滤。

**签名**：`signature = sha256(version|manifest|sbom)`，固定 `|` 分隔符而非 JSON 序列化——JSON 键序在不同 Python 版本间可能不同，会让同一内容产出两个签名，审计时对不上账。
每次读 Release 的响应都带 `signature_valid`（现算现比），内容被改过即 `false`，交付审计可据此判篡改。

## 错误码

| 场景 | 状态码 |
|---|---|
| `ValueError`（版本重复 / 缺 site_code / channel 非法） | 409 |
| `KeyError`（release / 站点不存在，或站点未注册） | 404 |
| `IllegalTransition`（越态推进、非 promoted 召回） | 409 |
| `PermissionError`（心跳令牌无效） | 403 |

## 管理入口（前端）

主导航两页，均需 `tool:config`：

| 路由 | 能做什么 |
|---|---|
| **/releases** | 通道筛选 + 版本卡（channel / status / **签名一致·签名不符** 徽标 / 变更单逐条）+ 推进（按钮按 `NEXT_CHANNEL` 动态显示「推进到 staging」，production 显示「已是终点」）+ 召回（仅 promoted 可点）+ 新建（变更单每行 `kind: summary`） |
| **/edge-sites** | 站点卡（待升级整卡转琥珀底并显示 `已运行 → 应运行`）+ 查应运行版本 / 模拟心跳上报 / 注销 + **一次性令牌弹层**（注册后明文 token 仅此一次，带复制按钮） |

两条路由都走 `lib/api.ts` 的 releases / edge-sites 段（9 个函数）。

## 已知边界（别误当 bug）

1. **签名是非对称签名的占位实现**。无密钥体系，用固定定长 sha256 摘要；将来换 RSA/ECDSA 只需替换 `sign_release` / `verify_signature` 两个函数。它防的是**改动后未重新落签名**（可审计、可比对），不是防的值攻击者伪造持有私钥者——那个要上密钥体系。
2. **心跳无超时判离线**。目前由 Hub 侧读 `last_heartbeat_at` 自行判断（离线阈值未落库、未做定时任务）。`status` 的 `offline` / `syncing` 枚举已预留但尚未自动置位。
3. **升级动作本身不在此闭环**。本模块只回答「你该升到哪个版本」并给出 manifest，包怎么传、怎么装由部署层（离线 `docs/UPGRADE.md` 流程）负责。

## 验证

- 测试：`backend/tests/test_release_delivery.py`（37 断言）——含注册/令牌哈希不落明文/重复注册 409/心跳 403/版本上报/sync from-to/租户隔离/RLS 受限角色查空。
- 全量回归：25 脚本 **PASS 660 / FAIL 0 / SKIP 0**（`backend/tools_patch/regress_r13.txt`）。
- 双库（`furui_aios` / `furui_aios_test`）均已在 head `9d1f4c7b2e8a`，49 表、`edge_sites` RLS+FORCE 已开。
