# -*- coding: utf-8 -*-
"""TASK-002 完成后更新 CURRENT.md / BACKLOG.md（UTF-8 安全写入）。"""
import io

base = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks"
cur = base + r"\CURRENT.md"
back = base + r"\BACKLOG.md"

# ---------------- CURRENT.md 整段重写 ----------------
cur_new = """# CURRENT TASK
# Task ID
TASK-002
---
# Status
DONE
---
# Title
演示数据真实化（核电巡检场景）
---
# Goal
把 furui-aios 从「销售分析演示」为主链路，增量改造成「核电巡检为主链路 + 保留销售链路」，贴合杭州傅瑞科技主业（工业空间智能·核电高危场景）。
---
# Completion Record
完成轮次：2026-09-22（用户拍板「核电为主 + 保留销售」双场景后执行）。
- 数据层（data_gateway.py）：ALLOWED_TABLES 扩入 monitoring_stations / device_metrics / inspection_records；三表 schema + 样例种子（5 监测站 MS-01~05 / 10 指标 / 10 巡检记录），老库增量补表幂等，228 笔销售订单保留。已实测。
- 模型层（models_ai.py）：新增 InspectionWorkOrder（inspection_work_orders，与 SalesTask 同构），create_all 建表。
- 工具层（tool_gateway.py）：新增 query_monitoring_stations / query_device_metrics / analyze_inspection_anomaly / create_workorder（Level 3 必须审批）；_approval_title 补 create_workorder 分支。4 工具 E2E 实测 ok。
- 种子层（bootstrap.py）：KB_SEED 补《辐射防护与监测限值标准》《核电设备巡检异常归因标准》；AGENT_SEED 新增「巡检分析 Agent」(inspection-analyst)；TOOL_SEED 注册 4 新工具；_seed_datasources 新增 IoT 数据源；_seed_scenarios 新增「监测站异常自动归因」「设备健康度预警」两场景；全部改为逐条增量幂等（3 次 init_all 收敛：4 Agent / 3 DS / 4 场景 / 11 知识）。
- mainline.py：新增 PLAN_INSPECTION 六步（查监测站→查指标→查知识→归因→报告→建工单审批）+ _pick_plan 按 agent.code 选链路 + _render_inspection_report（规则化报告）+ step6 巡检工单分支（含提前 return 避免落入销售分支）+ 销售分支兼容。
- 本体图（ontology/__init__.py）：新增 MonitoringStation(5)/Area(3)/MetricRecord(5)/InspectionRecord(5) 四类实体 + 32 条 Link（Station→Area / Metric→Station / Inspection→Station / WorkOrder→Station / Device→Station）+ analyze_inspection_anomaly Function。
- 前端（frontend/app/workbench/page.tsx）：TOOL_LABEL 补 4 新工具中文名；run() 按问题关键词路由 agent_code（巡检→inspection-analyst，销售→sales-analyst）；审批通过后按工单/任务分别展示结果；快捷问题补「8月核电设备巡检异常归因」等 2 条。tsc --noEmit 通过。
- 测试：新增 tests/test_nuclear_scenario.py（23 断言，巡检主线 6 步 / 审批通过工单落库 / 审批拒绝任务回退 / 本体图实体），23 PASS / 0 FAIL；离线模式 ENABLE_REAL_LLM=false 验证，数字全来自 SQL/内存真实计算。
---
# Previous Task
TASK-012 长程任务状态机（40-06）— 2026-09-22 DONE
---
# Next Task（候选，待拍板）
推荐：TASK-003 Phase 3 生产库 / RLS 真实 PostgreSQL 验证 — BLOCKED，待提供 PostgreSQL 环境（用户已定：暂时不改数据库）
备选：
- TASK-014 Logic 决策编排画布（40-03）— P2 BACKLOG
- 前端「对象语境真实化」体验深化：把巡检工单/监测站/审批做进对象中心与仪表盘（承接 P2 截图反馈）
---
# Development Rule
开始开发之前：
必须读取：
.ai/README.md
.ai/PROJECT.md
.ai/PRINCIPLES.md
.ai/ARCHITECTURE.md
.ai/DOMAIN.md
.ai/AI.md
.ai/workflows/feature.md
.ai/rules/coding.md
.ai/rules/frontend.md
.ai/rules/backend.md
---
# Completion
完成以后：
更新 CURRENT.md
将本任务状态改为 DONE
然后将下一任务写入 CURRENT.md
"""
with io.open(cur, "w", encoding="utf-8") as f:
    f.write(cur_new)
print("CURRENT.md updated")

# ---------------- BACKLOG.md 增量更新 ----------------
with io.open(back, "r", encoding="utf-8") as f:
    b = f.read()

# 1) 顶部时间线加一行
anchor = "> 2026-09-22锛歍ASK-012 瀹屾垚锛堣琛屽唴澶囨敞锛夛紝鏂板 test_task_state_machine 51 鏂█ + 鍏ㄩ噺 19 鑴氭湰 0 澶辫触 / 1 SKIP銆?"
add = "> 2026-09-22锛歍ASK-002 瀹屾垚锛堣琛屽唴澶囨敞锛夛細鏍哥數宸℃绔夸富绾胯惤鍦?data_gateway 3 琛?/ tool_gateway 4 宸ュ叿 / bootstrap 鈥滃贰妫€鍒嗘瀽 Agent鈥?+ IoT 鏁版嵁婧?+ 2 宸℃绔垮満鏅?/ mainline PLAN_INSPECTION 鍏亾 / 鏈綋鍥 4 绫诲疄浣?+32 Link / 宸ヤ綔鍙板墠绔榻愶級锛涙柊 test_nuclear_scenario 23 鏂█ 0 澶辫触锛屽叏閲忓洖褰 20 鑴氭湰 0 澶辫触 / 1 SKIP锛圧LS 寰?PG锛夈€?"
if anchor in b:
    b = b.replace(anchor, anchor + "\n" + add, 1)
else:
    print("WARN: timeline anchor not found")

# 2) TASK-002 行状态 READY -> DONE
old_row = "| TASK-002 | 婕旂ず鏁版嵁鐪熷疄鍖栵紙鏍哥數宸℃绔満鏅?| P0 | READY | 鐢ㄦ埛鎷嶆澘锛氣憼鏈綋鍥惧疄浣撴竻鍗?鈶＄煡璇嗗簱绱犳潗鏂瑰悜 | 6 澶勬敼閫犻潰锛圓GENT/TOOL/KB_SEED銆佸満鏅€佹湰浣撳浘銆丏ashboard锛夛紝鐗靛姩 4+ 娴嬭瘯鍚屾鏀瑰啓 |"
new_row = "| TASK-002 | 婕旂ず鏁版嵁鐪熷疄鍖栵紙鏍哥數宸℃绔満鏅?| P0 | DONE | 鈥?| 2026-09-22 瀹屾垚锛氭暟鎹眰3琛?/ 宸ュ叿4涓?/ Agent+Iot+2鍦烘櫙 / mainline鍏亾 / 鏈綋鍥?绫?+32Link / 宸ヤ綔鍙伴綈锛泃est_nuclear_scenario 23 PASS锛屽叏閲?20鑴氭湰 0澶辫触/1SKIP |"
if old_row in b:
    b = b.replace(old_row, new_row, 1)
else:
    print("WARN: TASK-002 row not found")

with io.open(back, "w", encoding="utf-8") as f:
    f.write(b)
print("BACKLOG.md updated")
