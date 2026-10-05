# -*- coding: utf-8 -*-
"""2026-09-23 排定执行顺序：BACKLOG.md 加执行顺序章节 + 登记 TASK-020/021。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks\BACKLOG.md"
with io.open(p, "r", encoding="utf-8") as f:
    b = f.read()

# ---------- 1) 在 "# Backlog Items" 前插入执行顺序章节 ----------
order_block = """# 执行顺序（2026-09-23 排定，用户拍板按序执行）

| 序 | TASK-ID | 标题 | 优先级 | 前置 | 说明 |
|---|---|---|---|---|---|
| 1 | TASK-013 | SecretRef 密钥引用（60-04） | P1 | TASK-003 ✅ | 已 READY，下一个开工 |
| 2 | TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | TASK-003 ✅ | 差距清单 3.Y.2 剩余三件事 |
| 3 | TASK-021 | 前端对象语境真实化体验深化 | P1 | TASK-002 ✅ | 用户长期痛点：把巡检工单/监测站/审批做进对象中心与仪表盘 |
| 4 | TASK-014 | Logic 决策编排画布（30-03） | P2 | — | 服务端图 + Logic 画布 |
| 5 | TASK-015 | 低代码构建（40-03）+ 应用运行时（40-02） | P2 | — | Canvas / Widget Registry / Publish |
| 6 | TASK-016 | 平台内核与资产装配（50 全系） | P2 | — | Bundle/Registry/Resolver/Installation/Plugin |
| 7 | TASK-017 | 交付发布与部署形态（70/80 全系） | P2 | — | Compose/Helm、Release/Channel/SBOM |
| 8 | TASK-018 | 成熟度矩阵/差异地图（90-02） | P2 | — | 系统健康汇总与状态地图 |

> 排序口径：P1 地基（1~3）优先于 P2 横切（4~8）；同优先级内按依赖链与用户价值排。
> 领取规则：每完成一个，从本顺序表取下一条写入 CURRENT.md；遇到需要拍板的决策点停下来问用户。

"""

anchor = "---\n\n# Backlog Items"
if anchor in b:
    b = b.replace(anchor, "---\n\n" + order_block + "# Backlog Items", 1)
else:
    print("WARN: Backlog Items anchor not found")

# ---------- 2) 表格登记 TASK-020 / TASK-021（插在 TASK-019 之后） ----------
old19 = "| TASK-019 | 前端走查修复 + 添加数据源闭环（用户现场反馈） | P0 | DONE | 无 | 2026-09-20~21 完成：17 路由走查→admin 六页（data/integration/permission/logs/settings/model）空白修复（`frontend/app/admin/[slug]/page.tsx` 两处解包：`d?.data ?? d`、`d?.data?.items || []`，tsc 通过）→新增数据源闭环端到端（catalog 8 类→选择→命名→确认→新行入库→toggle connected）；`mysql_00599\"核电站巡检报表库\"` 为验证产物可删；CDP 对管理页表格区截图空白为工具合成层缺陷（DOM 正常已验证） |"

add020 = "| TASK-020 | Phase 3 收尾：应用层 RLS 贯通 + 复合租户键/canary + default 列收口 | P1 | BACKLOG | TASK-003（已 DONE） | 2026-09-23 登记（差距清单 3.Y.2 剩余）：① app 用受限角色连接 + set_tenant_context 登录链路实测 ② 复合租户键/负向 canary ③ 系统收口其余 Python default 列 |"

add021 = "| TASK-021 | 前端对象语境真实化体验深化 | P1 | BACKLOG | TASK-002（已 DONE） | 2026-09-23 登记（用户长期痛点）：把巡检工单/监测站/审批做进对象中心与仪表盘，让页面不再\"像演示\" |"

if old19 in b:
    b = b.replace(old19, old19 + "\n" + add020 + "\n" + add021, 1)
else:
    print("WARN: TASK-019 row not found")

with io.open(p, "w", encoding="utf-8") as f:
    f.write(b)
print("BACKLOG.md updated")
