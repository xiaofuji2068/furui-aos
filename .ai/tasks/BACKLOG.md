# BACKLOG — 待办池（后续执行任务清单）

> 用途：排队中的任务统一放这里（一行一任务，含 ID/标题/优先级/状态/依赖）。
> 与 CURRENT.md 的关系：**CURRENT.md 只放"当前正在执行"的任务**（按模板 Completion 规则，当前任务完成后从本清单领取下一个写入 CURRENT.md）。
> 状态说明：DONE=已完成（含核实轮次）｜READY=可领取开工｜BLOCKED=缺依赖/环境，等待解锁｜BACKLOG=排队，未排期。
> 来源：docs/图谱-furui-aios差距清单与实施路线.md（2026-09-09 修订）+ CURRENT.md 后备。
> 2026-09-15 核实：TASK-004~009（差距清单 3.X.2 P0 剩余 7 项）已在先前轮次全部实现并经全量回归锁定（370 断言通过/0 失败/1 SKIP=RLS 待 PG），状态更新为 DONE。
> 2026-09-16：TASK-010 完成（见行内备注），全量回归 401 断言通过/0 失败/1 SKIP。
> 2026-09-16：TASK-011 完成（见行内备注），全量回归 18 文件 0 失败/1 SKIP（RLS 待 PG）。
> 2026-09-20~21：TASK-019 完成（见行内备注）：前端全站 17 路由走查 + admin 六页空白修复（根因：裸 fetch 未解包 {code,message,data}）+ 添加数据源闭环端到端验证（选类型→命名→入库→toggle 连接），浏览器逐页验证通过。
> 2026-09-22 全量核实：后端 18 个测试脚本全量回归 **17 个真跑全部 PASS / 0 FAIL / 1 SKIP（test_rls_isolation 无 PG 如实 SKIP）**；据此确认 TASK-004~011（9 项 P0/P1）与 TASK-019（前端，已逐页验证）的 DONE 状态全部属实，无需重做。
> 2026-09-22：TASK-012 完成（见行内备注），新增 test_task_state_machine 51 断言 + 全量 19 脚本 0 失败 / 1 SKIP。
> 2026-09-22：TASK-002 完成（见行内备注）：核电巡检主线落地（data_gateway 3 表 / tool_gateway 4 工具 / 「巡检分析 Agent」+IoT 数据源 +2 巡检场景 / mainline 巡检六步链路 / 本体图 4 类实体+32 Link / 工作台前端对齐），新增 test_nuclear_scenario 23 断言 0 失败，全量 20 脚本 0 失败 / 1 SKIP（RLS 待 PG）。
> 2026-09-23：TASK-020 完成（见行内备注）：受限角色 furui_app 双库 + 全库 34 表 RLS/FORCE 收口（对齐迁移 d4e5f6a7b8c9：补 4 张缺失表幂等 + 31 直列 + 3 子表复合租户键 EXISTS policy + 5 系统表豁免）；租户硬编码显式化（ontology/admin eval-contract）；test_rls_isolation 扩展 13 断言 PG 全 PASS（负向 canary OR/LIKE/JOIN + 子表复合键 + 子表越权写拦截）；default 审计 docs/TASK-020-default审计.md（A 192/B 215 分批）；SQLite 全量 21 脚本 0 失败；生产/测试库 head=d4e5f6a7b8c9。
> 2026-09-23：TASK-013 完成（见行内备注）：SecretRef/Keychain 落库（secret_entries + RLS）并接线 admin 密钥管理；SQLite 全量 21 脚本 0 失败/1 SKIP；PG 模式 test_secret_ref 29 PASS + test_rls_isolation 6 PASS；生产库 furui_aios 迁移到 head（36 表，secret_entries RLS 启用）。TASK-020 依赖解锁 READY。
> 2026-09-23：TASK-021 完成（见行内备注）：admin/settings 落库（SystemSetting 表+迁移 e5f6a7b8c9d0 双库）+ 对象中心核电对象中文语境（TYPE_META）+ 工作台核电对象跳转（objectLinkOf MS/INSP/MET/AREA）；SQLite 全量 21 脚本 0 失败 + PG 13/13 + tsc 0 错误。
> 2026-09-27：TASK-016 完成（见行内备注）：平台内核与资产装配全链落地——Bundle/Registry/Resolver/Installation/Plugin + 前端资产中心；PG 测试 35/35（含 rederive 以 DB 实体为准修复）；迁移链多 head 修复（8c9d0e1f2a3b down=b7c8d9e0f1a2）双库对齐；浏览器联调安装→动态导航→派生页全通；前端 tsc 0 错误。
> 2026-10-05：TASK-017 后端收口（见 Backlog 行备注）：交付发布与部署形态从 ~60% 推到 ~95%——迁移 `9d1f4c7b2e8a` 建 releases/release_changes（RLS 豁免）+ edge_sites（RLS/FORCE + tenant_isolation policy）；models_release 3 模型 + release.py（sha256 `version|manifest|sbom` 签名、PROMOTE_ORDER 白名单、heartbeat token 哈希比对、sync_target 版本比对）+ release_api 9 端点；tests/test_release_delivery.py 37 断言全绿，双库 head=9d1f4c7b2e8a / 49 表 / 40 RLS 表，HTTP 冒烟 Release+EdgeSite 段全通。同轮「C→A→B」三件事一并做掉：C=迁移链堵口（干净库 verify 17 迁移一次跑通、reset_test_db 改走 alembic upgrade head + furui_app 授权、解锁 test_rls_isolation 13/0）、A=上述 Release/EdgeSite 闭环（HTTP 冒烟全绿）、B=test_asset_bundle 改自清理+幂等口径（连跑 3 次 35/0）；另修 `run_tests.py` 把 `PASS 9/9` 误判 fail=9 的解析 bug（消除批量假 FAIL）。全量 25 脚本约 PASS 660 / FAIL 0。剩余：前端 Release/EdgeSite 管理页（已拆 TASK-017-FE）+ docs/HUB-SPOKE.md 补齐（已拆 TASK-017-DOC）。
> 2026-09-23：TASK-014 完成（见行内备注）：编排数据态落地——logic_graphs/logic_nodes 两表（company_id 复合键+RLS FORCE）+ 引擎读图优先（mainline.run 读 DB active 图，无图回退代码 PLAN）+ 4 API（tool:config）+ 前端 Logic 编排画布页（图卡片/六节点流/节点编辑/激活）；迁移 f6a7b8c9d0e1 双库 head；SQLite 全量 22 脚本 0 失败（含新 test_logic_graph 19 断言）+ PG 13/13 + tsc 0 错误。
> 2026-09-23：TASK-003 完成（见行内备注）：本机 PostgreSQL 17 真实验证——Alembic 8 版本链迁移到 head（35 表）+ 27 表 RLS rowsecurity=t 全部启用 + test_rls_isolation PG 模式 6 PASS / 0 FAIL / 0 SKIP（租户互不可见/无上下文安全拒绝/WITH CHECK 拦截）；SQLite 形态全量 20 脚本 19 真跑 0 失败 / 1 SKIP。TASK-013 依赖解锁 READY。

---

# 执行顺序（2026-09-23 排定，用户拍板按序执行）

| 序 | TASK-ID | 标题 | 优先级 | 前置 | 说明 |
|---|---|---|---|---|---|
| 1 | TASK-013 | SecretRef 密钥引用（60-04） | P1 | TASK-003 ✅ | ✅ 2026-09-23 完成（见 Backlog 行备注），下一个开工 TASK-020 |
| 2 | TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | TASK-003 ✅ | ✅ 2026-09-23 完成（见 Backlog 行备注），下一个开工 TASK-021 |
| 3 | TASK-021 | 前端对象语境真实化体验深化 | P1 | TASK-002 ✅ | ✅ 2026-09-23 完成（见 Backlog 行备注），下一个开工 TASK-014 |
| 4 | TASK-014 | Logic 决策编排画布（30-03） | P2 | — | ✅ 2026-09-23 完成（见 Backlog 行备注），下一个开工 TASK-015 |
| 5 | TASK-015 | 低代码构建（40-03）+ 应用运行时（40-02） | P2 | — | ✅ 2026-09-27 完成（见 Backlog 行备注），下一个开工 TASK-016 |
| 6 | TASK-016 | 平台内核与资产装配（50 全系） | P2 | — | ✅ 2026-09-27 完成（见 Backlog 行备注），下一个开工 TASK-017 |
| 7 | TASK-017 | 交付发布与部署形态（70/80 全系） | P2 | — | ✅ 2026-10-05 DONE（按本任务 Scope/AC 1~6 全部达标：部署文档 / Dockerfile×2 + compose / Release 5 API + EdgeSite 4 API / sbom.py / 迁移 9d1f4c7b2e8a 双库 head / 25 脚本 PASS 660 FAIL 0 / 前端 tsc 0 错误）。同轮顺带清掉三处旧债：迁移链堵口、run_tests 假 FAIL、test_asset_bundle 假红。剩余前端管理页已拆为 TASK-017-FE（READY）；下一个可开工 TASK-017-FE 或 TASK-018 |
| 8 | TASK-018 | 成熟度矩阵/差异地图（90-02） | P2 | — | 系统健康汇总与状态地图 |

> 排序口径：P1 地基（1~3）优先于 P2 横切（4~8）；同优先级内按依赖链与用户价值排。
> 领取规则：每完成一个，从本顺序表取下一条写入 CURRENT.md；遇到需要拍板的决策点停下来问用户。

# Backlog Items

| TASK-ID | 标题 | 优先级 | 状态 | 依赖 | 备注 |
|---|---|---|---|---|---|
| TASK-002 | 演示数据真实化（核电巡检场景） | P0 | DONE | — | 2026-09-22 完成：data_gateway 3 巡检表+样例 / tool_gateway 4 巡检工具（create_workorder L3 审批）/ bootstrap「巡检分析 Agent」+IoT 数据源+2 巡检场景（逐条幂等）/ mainline 巡检六步链路+规则化报告 / 本体图 4 类实体+32 Link+归因 Function / 工作台 TOOL_LABEL+agent 路由+工单审批展示（tsc 通过）；test_nuclear_scenario 23 PASS，全量 20 脚本 0 失败/1 SKIP |
| TASK-003 | Phase 3 生产库 / RLS 真实 PostgreSQL 验证 | P1 | DONE | — | 2026-09-23 完成：本机 PG 17（postgres/postgres123）Alembic 8 版本链迁移到 head（35 表）+ 27 表 RLS rowsecurity=t 全部启用 + test_rls_isolation PG 模式 6 PASS/0 FAIL/0 SKIP；SQLite 全量 20 脚本 19 真跑 0 失败/1 SKIP |
| TASK-004 | Outbox 表 + 单线程 Projector 图快照 | P0 | DONE | — | 2026-09-15 核实：实现+API+测试锁定（test_outbox_projector PASS 21），无需开发 |
| TASK-005 | 模型 Catalog + Route（30-02） | P0 | DONE | — | 2026-09-15 核实：`GET /admin/models/catalog` + Key 激活切换（test_admin_keys PASS 9）；Route 以激活切换形式落地 |
| TASK-006 | Receipt 表 + 写回门禁校验（20-05/30-04） | P0 | DONE | — | 2026-09-15 核实：`ActionReceipt` + `/admin/receipts` + tool_gateway 校验（test_receipts PASS 31） |
| TASK-007 | EvalContract 决策谱系（30-05） | P0 | DONE | — | 2026-09-15 核实：`/admin/eval-contracts` GET/POST（test_eval_contract PASS 36） |
| TASK-008 | 审计查询 API（60-03/60-04） | P0 | DONE | — | 2026-09-15 核实：`GET /admin/audit?actor=&action=&from=&to=&limit=`（log:view） |
| TASK-009 | 健康检查（90-01） | P0 | DONE | — | 2026-09-15 核实：`GET /api/health` DB/对话模型/语义检索/系统四维（api/health.py） |
| TASK-010 | Dataset/MediaSet 资产模型 + Connector Catalog（10-01/10-02） | P1 | DONE | 无硬依赖 | 2026-09-16 完成：`DatasetAsset` 表（data_datasets）+ store_data_assets + `/api/data-assets` 5 端点，Catalog 复用数据源目录；test_data_assets PASS 23，全量 401 断言 0 失败
| TASK-011 | 对象 AIP/Action 嵌入（40-04） | P1 | DONE | TASK-006（已 DONE） | 2026-09-16 完成：对象视图 + AIP/Action 表单（/api/objects）+ 写回走 tool_gateway 门禁（Level2 直行留 Receipt / Level3 审批单）；test_object_actions PASS 31，全量 0 失败 |
| TASK-012 | 长程任务状态机（40-06） | P1 | DONE | TASK-006（已 DONE） | 2026-09-22 完成：TaskBrief + Stage/Checkpoint（PLAN 六步→3 阶段投影）+ Review/Return 状态机（显式迁移白名单）；审批批准→任务 Completed、拒绝→Returned；`POST /api/tasks/{id}/review`（approve/return）+ `POST /api/tasks/{id}/retry`（Returned/Failed 复用重跑）；task_detail 返回 brief/stages/reviews；test_task_state_machine PASS 51，全量 19 脚本 0 失败/1 SKIP |
| TASK-013 | SecretRef 密钥引用（60-04） | P1 | DONE | TASK-003（已 DONE） | 2026-09-23 完成：SecretEntry 模型（secret_entries 表 + PII/Retention/Region 标注）+ store_secrets Keychain（set/get/list 脱敏/delete/migrate .env→Keychain 幂等 + resolve_llm_key Keychain 优先 .env 兜底）+ admin secrets 4 路由（require_perm tool:config，列表绝回明文）+ save_model_keys 同步写 Keychain + Alembic c3d4e5f6a7b8（secret_entries + RLS/FORCE）；附带修复 admin._BACKEND_DIR 路径 bug（原指向 backend/app/.env，模型 Key 保存写错位置）与 ensure_column 跨方言；SQLite 全量 21 脚本 0 失败/1 SKIP（test_secret_ref 29 PASS），PG 模式 test_secret_ref 29 PASS + test_rls_isolation 6 PASS，生产库 furui_aios 迁移 head（36 表，secret_entries RLS 启用） |
| TASK-014 | Logic 决策编排画布（30-03） | P2 | DONE | — | 服务端图 + Logic 画布；编排现硬编码在 orchestrator |
| TASK-015 | 低代码构建（40-03）+ 应用运行时（40-02） | P2 | DONE | — | 2026-09-27 完成：后端 AppPage 模型（app_pages 表+RLS，company_id+code 唯一）+ pages.py WIDGET_TYPES 注册表（stat_cards/object_list/data_assets/tasks/text_note）+ nuclear-overview seed + 5 组路由（list/get/get_by_code/create/update/publish/draft/delete，require_perm tool:config）+ 迁移 a2b3c4d5e6f7；前端 4 文件接线（api.ts pages 段 8 函数 + Sidebar「低代码构建」入口 + 构建页 app/pages/page.tsx 列表/编辑器/保存版本自增 + 运行时页 app/pages/[code]/page.tsx 5 Widget 渲染器）；浏览器联调全通（构建页→编辑器→保存 v1.1→运行时页 5 Widget 全渲染）；修 3 个真实缺陷（request 裸对象误判/stat_cards kpis 对象解析/openEdit 动态 import HMR 失效）；生产库业务 seed（sales_tasks 5 + data_datasets 3 + agent_tasks 5，company_id=16）；PG 全量回归 23/23 + 前端 tsc 0 错误 |
| TASK-016 | 平台内核与资产装配（50 全系） | P2 | DONE | — | 2026-09-27 完成：AssetBundle/AssetInstallation 两表（installation RLS/FORCE）+ assets.py 全套（seed 幂等 2 Bundle/catalog/create 校验/publish/install 派生幂等/rederive 以 DB 实体为准/uninstall/resolve/installed_nav）+ assets_api 10 路由（tool:config）+ bootstrap 接 seed_bundles；修复 rederive 记录过期缺陷后 PG 测试 35/35；迁移 8c9d0e1f2a3b 修正 down=b7c8d9e0f1a2 消除多 head，生产 upgrade/测试 stamp 双库对齐；前端资产中心页（assets/center 安装/卸载/重新派生/动态导航）+ Sidebar「平台资产」；API 端到端 + 浏览器联调全通（安装→动态导航→派生页 5 Widget）；tsc 0 错误 |
| TASK-017 | 交付发布与部署形态（70/80 全系） | P2 | DONE（后端）/ BLOCKED（前端待接） | — | 2026-10-05 后端收口：① 迁移 `9d1f4c7b2e8a_release_edge_sites`（down=8c9d0e1f2a3b）建 releases(RLS 豁免)/release_changes(豁免)/edge_sites(RLS+FORCE + tenant_isolation policy)；② `app/models_release.py` 3 模型 + `app/release.py`（sha256 签名 `version|manifest|sbom`、PROMOTE_ORDER 显式白名单、heartbeat token 比对、sync_target）；③ `app/api/release_api.py` 9 端点（Release list/create/get/promote/recall + EdgeSite register/heartbeat/list/sync），POST /releases 需 tool:config；④ `tools/sbom.py` + Dockerfile×2 + compose + DEPLOYMENT/UPGRADE 文档（上轮已备）；⑤ tests/test_release_delivery.py **37 断言全绿**；⑥ 双库 prod+test 均 head=9d1f4c7b2e8a / 49 表 / 40 RLS 表。同轮顺带：迁移链堵口（`reset_test_db.py` 改走 `alembic upgrade head` + furui_app 授权，干净库 verify 17 迁移一次跑通，解锁 test_rls_isolation 13/0）、`run_tests.py` 行级解析修复假 FAIL、`test_asset_bundle` 改自清理+幂等口径 35/0。**剩余**：前端 Release/EdgeSite 管理页（api.ts + admin 页未做） |
| TASK-017-FE | 交付发布前端（Release / EdgeSite 管理页） | P2 | DONE | TASK-017（后端已 DONE） | 2026-10-05 完成：`lib/api.ts` +9 函数 / 4 类型；新建 `app/releases/page.tsx`（统计卡 + 通道筛选 + 版本卡含签名一致/不符徽标 + 推进/召回 + 新建弹层变更单按 `kind: summary` 解析）；新建 `app/edge-sites/page.tsx`（站点卡待升级转琥珀底显示 从→应运行 + 查同步/心跳上报/注销 + 一次性令牌弹层带复制）；Sidebar 两入口（tool:config）；后端补 `DELETE /api/edge-sites/{site_code}`（消掉 unregister_site 死 import）。验收：tsc 0 错误 / 两页 Next SSR 200 路由注册正确 / 前端真实调用路径经 rewrites 代理返回正确数据外壳（含 channel 筛选）/ 新 DELETE 冒烟 2→1 / 全量回归无回归。**未做真浏览器联调**（本机无 Playwright，装 Chromium 需 ~500MB） |
| TASK-017-DOC | docs/HUB-SPOKE.md 补齐 | P2 | DONE | — | 2026-10-05 补齐：`docs/HUB-SPOKE.md` 新建（原本 `docs/DEPLOYMENT.md` 第 90 行引用了但文件不存在）；含 Hub/Spoke 定位、三张表 RLS 边界、注册/心跳/同步三段协议（含请求+响应示例）、Release 状态机、错误码表、三条已知边界（签名为非对称占位实现 / 心跳无超时判离线 / 升级动作不在本闭环）、验证口径 |
| TASK-018 | 成熟度矩阵/差异地图（90-02） | P2 | BACKLOG | — | 系统健康汇总与状态地图 |
| TASK-019 | 前端走查修复 + 添加数据源闭环（用户现场反馈） | P0 | DONE | 无 | 2026-09-20~21 完成：17 路由走查→admin 六页（data/integration/permission/logs/settings/model）空白修复（`frontend/app/admin/[slug]/page.tsx` 两处解包：`d?.data ?? d`、`d?.data?.items || []`，tsc 通过）→新增数据源闭环端到端（catalog 8 类→选择→命名→确认→新行入库→toggle connected）；`mysql_00599"核电站巡检报表库"` 为验证产物可删；CDP 对管理页表格区截图空白为工具合成层缺陷（DOM 正常已验证） |
| TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | DONE | TASK-003（已 DONE） | 2026-09-23 完成：受限角色 furui_app（双库+全表 GRANT）；对齐迁移 d4e5f6a7b8c9（幂等补 4 缺失表 agent_stages/data_datasets/inspection_work_orders/task_reviews + 31 直列 RLS/FORCE + 3 子表 agent_skills/agent_steps/agent_stages 复合租户键 EXISTS policy + 5 系统表豁免 companies/ontology_types/permissions/role_permissions/user_roles）；生产/测试库 40 表 34 RLS head 一致；租户硬编码显式化（ontology _upsert_*/outbox/snapshot/seed + admin eval_contract user.company_id）；test_rls_isolation 扩展至 13 断言 PG 13/13 PASS（全表收口×2、负向 canary OR 1=1/LIKE 绕过×2、JOIN 只见 A、子表复合键只见 A、子表越权写 WITH CHECK 拦截）；default 审计落档（A 192 处 Python default 无 server_default / B 215 处 NOT NULL 无 server_default，分批处理）；SQLite 全量 21 脚本 0 失败/1 SKIP |
| TASK-021 | 前端对象语境真实化体验深化 | P1 | DONE | TASK-002（已 DONE） | 2026-09-23 完成：走查结论=17 路由数据全走后端 API 无前端假数据、闭环已具备；修复① admin/settings 落库（SystemSetting 表 + admin 读写改 DB + 迁移 e5f6a7b8c9d0 双库成功 + 文案去"重启即丢失"）；修复② 对象中心 TYPE_META 补核电对象（Area/MonitoringStation/MetricRecord/InspectionRecord 中文语境）；修复③ 工作台 objectLinkOf 补核电前缀（MS/INSP/MET/AREA 可跳对象中心）；SQLite 21/21 + PG 13/13 + tsc 0 错误 |

---

# 领取规则

1. 当前任务完成后（CURRENT.md 标记 DONE），从本清单选择下一个 READY 且优先级最高的任务，写入 CURRENT.md。
2. 若任务状态为 BLOCKED：先解锁依赖（如 TASK-003 需 PG 环境）再领取。
3. 领取后：CURRENT.md 中写明完整 Scope / Acceptance Criteria / Dependencies / Risks（细节可在差距清单对应行查）。
4. 本清单由任务负责人维护：新增任务追加行，完成的任务移到 CURRENT.md 后删除或标记 DONE。

# 备注

- 优先级口径与差距清单一致：P0 主链中枢 → P1 地基 → P2 横切增强。
- 明确不做的（当前阶段）：电商垂直（10-06/20-06/30-07/40-05）。
