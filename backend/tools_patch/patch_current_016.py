# -*- coding: utf-8 -*-
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks\CURRENT.md"
s = io.open(p, encoding="utf-8").read()

# 1) Status: READY -> DONE
old_status = """---
# Task ID
TASK-016
---
# Status
READY（执行顺序第 6 位，前序 TASK-015 已 DONE，可领取开工）
---"""
new_status = """---
# Task ID
TASK-016
---
# Status
DONE（执行顺序第 6 位；2026-09-27 后端 35/35 + API 端到端 + 浏览器联调全通，下一任务 TASK-017）
---
# 执行进展（2026-09-27 TASK-016 完成记录）
## Completed（本轮）
1. **后端资产装配核心全部落地**：AssetBundle（系统目录，code 唯一 uq_asset_bundles_code，RLS 豁免）+ AssetInstallation
   （租户派生安装，company_id+bundle_id 唯一，**RLS/FORCE 启用**）两模型；assets.py 全套逻辑（seed_bundles 幂等内置 2 Bundle /
   catalog list/get / create 带 manifest.requires 与 content 一致性校验 / publish / install_bundle 派生安装幂等 /
   rederive 显式补齐 / uninstall 卸载清理 / resolve / installed_assets / installed_nav 动态导航）；assets_api.py 10 路由
   （目录类 get_current_user，写操作 require_perm("tool:config")）；bootstrap init_all 接入 seed_bundles（后端启动自动有目录）。
2. **修复 rederive 语义缺陷（原 2 FAIL）**：rederive 原以 installation 记录（derived_graphs_json）判断缺失 → 记录过期时
   （派生图被删但记录仍在）不补齐。改为**以 DB 实体实际存在性为准**（按 company_id+code 实查 AppPage/LogicGraph），
   修复后测试库 PG 全量 **PASS 35 / FAIL 0 / SKIP 0**。
3. **环境级 SQLite 建表 bug 定性（与业务代码无关）**：venv Python 3.13.12 + SQLite 3.53.1 下任何 CREATE TABLE 都不落库
   （同一连接 SELECT sqlite_master 为空、INSERT 报 no such table），dbg5-dbg23 系列探针（SA/原生/显式事务/autocommit/
   最小 CREATE t1）全部证实；结论：本环境 SQLite create_all 路径不可用，测试与建库验证一律走 PG。
4. **迁移链修复 + 双库对齐**：真链 head 为 b7c8d9e0f1a2（a2b3c4d5e6f7→a2b3c4d5e6f8→b7c8d9e0f1a2），
   新迁移 8c9d0e1f2a3b down_revision 从 a2b3c4d5e6f7 改为 b7c8d9e0f1a2（消除多 head）；生产库 alembic upgrade head
   （current=8c9d0e1f2a3b，asset 两表 + asset_installations RLS/FORCE=t 验证通过）；测试库 stamp 对齐。
5. **前端资产中心接线**：api.ts assets 段（bundle 目录/安装/重新派生/卸载/installed-nav/resolve，类型与后端结构对齐）；
   新建 frontend/app/assets/center/page.tsx（统计卡 + 动态导航 + Bundle 卡片：安装/重新派生/卸载按钮，权限 tool:config）；
   Sidebar 主菜单新增「📦 平台资产」入口（tool:config）。
6. **API 端到端 + 浏览器联调全通**（admin/王欢，company 16）：登录 → /assets/bundles 2 条 → 安装 nuclear-inspection-bundle
   （created=True，派生 1 页 + 1 图）→ installed-nav ☢️ 核电巡检总览 → /pages/nuclear-overview 运行时页 5 Widget 全渲染
   （KPI 卡/对象列表/最近任务/数据资产）→ 浏览器安装 sales-command-bundle → 动态导航新增 📊 销售经营看板。
## Files
- backend/app/models_ai.py（+AssetBundle/AssetInstallation）
- backend/app/assets.py（新建：seed/catalog/create/publish/install/rederive/uninstall/resolve/installed_nav）
- backend/app/api/assets_api.py（新建 10 路由）+ app/api/__init__.py（assets_router 已注册）+ app/bootstrap.py（init_all 接 seed_bundles）
- backend/alembic/versions/8c9d0e1f2a3b_asset_bundles.py（新建；down_revision 修正为 b7c8d9e0f1a2；生产库已 upgrade、测试库已 stamp）
- backend/tests/test_asset_bundle.py（新建，35 断言）
- frontend/lib/api.ts（assets 段 7 函数 + 类型）
- frontend/app/assets/center/page.tsx（新建资产中心页）
- frontend/components/Sidebar.tsx（+「📦 平台资产」tool:config）
## Tests
- PG 测试库 test_asset_bundle：**PASS 35 / FAIL 0 / SKIP 0**（seed 幂等/manifest 校验/派生安装幂等/rederive 补齐/
  跨租户隔离/卸载清理/installed-nav/未发布拒装）
- API 端到端（api_e2e.txt）：登录→目录 2→安装→动态导航→派生页 5 widgets 全通
- 浏览器联调（computer_use_tool plane=bu）：资产中心页渲染/安装按钮/动态导航/派生页跳转全通
- 前端 tsc --noEmit：0 错误
- 结果：PASS
## Risks
- 测试库目前靠 create_all + alembic stamp 对齐；新表走迁移链后需 stamp 或 upgrade 保持双库一致；
- asset_bundles 为系统级目录（RLS 豁免，多企业共享），仅 asset_installations 租户隔离——符合「目录全局、安装派生」设计；
- 本机内存紧张（free 2.3-2.5GB）：后端/前端/浏览器并行时偶发超时，重启需先停 node 进程。
## Next
TASK-017 交付发布与部署形态（70/80 全系）——见 BACKLOG 执行顺序表第 7 位。
---
# Title
平台内核与资产装配（50 全系）"""
if old_status not in s:
    raise SystemExit("status anchor missing")
s = s.replace(old_status, new_status, 1)

io.open(p, "w", encoding="utf-8").write(s)
print("CURRENT OK")
