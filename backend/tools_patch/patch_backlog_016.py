# -*- coding: utf-8 -*-
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks\BACKLOG.md"
s = io.open(p, encoding="utf-8").read()

# 1) 执行顺序表第 6 行勾选
old_row = "| 6 | TASK-016 | 平台内核与资产装配（50 全系） | P2 | — | Bundle/Registry/Resolver/Installation/Plugin |"
new_row = ("| 6 | TASK-016 | 平台内核与资产装配（50 全系） | P2 | — | ✅ 2026-09-27 完成（见 Backlog 行备注），下一个开工 TASK-017 |")
assert old_row in s, "row6 missing"
s = s.replace(old_row, new_row, 1)

# 2) 领取规则下加一行 TASK-017 提示（第 7 位说明改）
old_next = "| 7 | TASK-017 | 交付发布与部署形态（70/80 全系） | P2 | — | Compose/Helm、Release/Channel/SBOM |"
new_next = "| 7 | TASK-017 | 交付发布与部署形态（70/80 全系） | P2 | — | ← 当前下一个可领取（TASK-016 已 DONE）；Compose/Helm、Release/Channel/SBOM |"
assert old_next in s, "row7 missing"
s = s.replace(old_next, new_next, 1)

# 3) Backlog Items 表 TASK-016 行 DONE + 备注
old_item = "| TASK-016 | 平台内核与资产装配（50 全系） | P2 | BACKLOG | — | Bundle/Registry/Resolver/Installation/Plugin + Manifest/签名 + 租户安装/覆盖 |"
new_item = ("| TASK-016 | 平台内核与资产装配（50 全系） | P2 | DONE | — | 2026-09-27 完成：AssetBundle/AssetInstallation 两表（installation RLS/FORCE）+ assets.py 全套（seed 幂等 2 Bundle/catalog/create 校验/publish/install 派生幂等/rederive 以 DB 实体为准/uninstall/resolve/installed_nav）+ assets_api 10 路由（tool:config）+ bootstrap 接 seed_bundles；修复 rederive 记录过期缺陷后 PG 测试 35/35；迁移 8c9d0e1f2a3b 修正 down=b7c8d9e0f1a2 消除多 head，生产 upgrade/测试 stamp 双库对齐；前端资产中心页（assets/center 安装/卸载/重新派生/动态导航）+ Sidebar「平台资产」；API 端到端 + 浏览器联调全通（安装→动态导航→派生页 5 Widget）；tsc 0 错误 |")
assert old_item in s, "item missing"
s = s.replace(old_item, new_item, 1)

# 4) 顶部备注加一行 2026-09-27 记录
old_top = "> 2026-09-23：TASK-014 完成（见行内备注）"
new_top = ("> 2026-09-27：TASK-016 完成（见行内备注）：平台内核与资产装配全链落地——Bundle/Registry/Resolver/Installation/Plugin + 前端资产中心；"
           "PG 测试 35/35（含 rederive 以 DB 实体为准修复）；迁移链多 head 修复（8c9d0e1f2a3b down=b7c8d9e0f1a2）双库对齐；"
           "浏览器联调安装→动态导航→派生页全通；前端 tsc 0 错误。\n> 2026-09-23：TASK-014 完成（见行内备注）")
assert old_top in s, "top anchor missing"
s = s.replace(old_top, new_top, 1)

io.open(p, "w", encoding="utf-8").write(s)
print("BACKLOG OK")
