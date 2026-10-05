# -*- coding: utf-8 -*-
"""TASK-014 收尾：更新 CURRENT.md（TASK-014 DONE + TASK-015 READY）与 BACKLOG.md（第 4 位✅+日志）。"""
from pathlib import Path

TK = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\.ai\tasks")

# ---------- CURRENT.md ----------
p = TK / "CURRENT.md"
s = p.read_text(encoding="utf-8")

head_marker = "# 上一任务完成记录（TASK-021 → DONE）"
idx = s.index(head_marker)
new_head = """# CURRENT TASK
# Task ID
TASK-015
---
# Status
READY（执行顺序第 5 位；TASK-014 已完成）
---
# Title
低代码构建（40-03）+ 应用运行时（40-02）
---
# Goal
把「从数据源/对象到可用页面」的构建过程低代码化：
1. 画布式编排（40-03）：对象/工具/图表以组件（Widget）形式拖拽成页面。
2. 应用运行时（40-02）：已发布页面可运行、可访问、可挂到侧边栏。
---
# Scope
1. Widget Registry（可复用组件注册表：对象表格/对象详情/统计卡片/图表）。
2. Canvas 构建页（拖拽或表单式排版，落库 PageDef）。
3. 运行时渲染器（读 PageDef 渲染页面）+ 发布态入口。
---
# Acceptance Criteria
1. 可创建一张页面定义并落库（PageDef + Widget 列表）。
2. 已发布页面可通过 URL 访问且不报错。
3. 页面可挂到侧边栏（与现有导航一致）。
4. SQLite 全量回归 0 失败；前端 tsc 0 错误。
---
# Dependencies
TASK-014（已 DONE）— Logic 图/画布模式可复用为低代码底座。
TASK-002（已 DONE）— 对象/数据源基线。
---
# Risks
- 运行时渲染与现有页面体系叠加可能引入路由冲突，需保持现有路由优先。
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
.ai/rules/frontend.md
.ai/rules/backend.md
.ai/workflows/feature.md
---
# Completion
完成以后：
更新 CURRENT.md
将本任务状态改为 DONE
然后将下一任务（TASK-016，执行顺序第 6 位）写入 CURRENT.md
---
# 上一任务完成记录（TASK-014 → DONE）
## Completed
Logic 决策编排画布（TASK-014，30-03）完成：把硬编码在 orchestrator/mainline 的编排提升为「服务端图 + 画布」。
1. 数据态图：logic_graphs / logic_nodes 两表（company_id 复合租户键，Unique(company_id,code)/(graph_id,seq)），
   默认 seed 两张图 sales-drop / inspection-anomaly（各 6 节点：数据→数据→知识→归因→报告→审批），seed 幂等不覆盖 active。
2. 执行引擎读图：mainline.run() 优先读 DB active 图（get_active_plan，按 agent code 选图），无图回退代码 PLAN（兼容既有测试）。
3. API：GET /api/logic/graphs、GET /api/logic/graphs/{id}、POST /nodes（节点编辑）、POST /activate（同 code 唯一 active），权限 tool:config。
4. 前端：Sidebar 主菜单新增「Logic 编排」入口（tool:config），新建 frontend/app/logic/page.tsx 画布页
   （图列表卡片 + 六节点横向流 + 节点内联编辑保存 + 激活切换 + 依赖关系展示），视觉与对象中心一致。
5. 迁移 f6a7b8c9d0e1（down=e5f6a7b8c9d0）：双库 upgrade 成功（head=f6a7b8c9d0e1），logic 两表 RLS/FORCE 已启用。
## Files
- backend/app/models_ai.py（+LogicGraph/LogicNode，logic_nodes 带 company_id）
- backend/app/logic.py（新建：seed/list/get/update_node/activate_graph/get_active_plan）
- backend/app/mainline.py（run() 读图优先 + 代码兜底）
- backend/app/api/logic_api.py（新建 4 路由）+ api/__init__.py 注册
- backend/alembic/versions/f6a7b8c9d0e1_logic_graphs.py（新建，双库已跑）
- backend/tests/test_logic_graph.py（新建 19 断言）
- frontend/lib/api.ts（+4 函数与类型）、frontend/components/Sidebar.tsx（入口）、frontend/app/logic/page.tsx（新建画布页）
## Tests
- test_logic_graph 19 PASS / 0 FAIL（seed/幂等/读图一致/节点编辑/激活/引擎读图）
- SQLite 全量 22 脚本 PASS / 0 FAIL（含新增 test_logic_graph）
- PG 模式 test_rls_isolation 13 PASS / 0 FAIL（双库 head=f6a7b8c9d0e1，logic 两表 RLS t/t）
- 前端 tsc --noEmit 0 错误
## Risks
- 图节点编辑目前只改结构（title/label/kind/tool），工具实现仍是代码——图是「结构数据」，工具是「代码能力」，边界符合 CURRENT Scope。
- PG 生产库已有用户数据，logic 表由 seed 首次访问生成（幂等，不影响现有行）。
## Next
TASK-015 低代码构建（40-03）+ 应用运行时（40-02）——见本文件顶部 READY 块。
"""
new = new_head + "\n" + s[idx:]
p.write_text(new, encoding="utf-8")
print("OK CURRENT.md -> TASK-015 READY + TASK-014 DONE 记录")

# ---------- BACKLOG.md ----------
p = TK / "BACKLOG.md"
s = p.read_text(encoding="utf-8")

# 1) 执行顺序表第 4 位打勾
old = "| 4 | TASK-014 | Logic 决策编排画布（30-03） | P2 | — | 服务端图 + Logic 画布 |"
new = "| 4 | TASK-014 | Logic 决策编排画布（30-03） | P2 | — | ✅ 2026-09-23 完成（见 Backlog 行备注），下一个开工 TASK-015 |"
assert old in s, "backlog order row"
s = s.replace(old, new, 1)

# 2) 顶部日志追加
old = "> 2026-09-23：TASK-003 完成"
add = "> 2026-09-23：TASK-014 完成（见行内备注）：编排数据态落地——logic_graphs/logic_nodes 两表（company_id 复合键+RLS FORCE）+ 引擎读图优先（mainline.run 读 DB active 图，无图回退代码 PLAN）+ 4 API（tool:config）+ 前端 Logic 编排画布页（图卡片/六节点流/节点编辑/激活）；迁移 f6a7b8c9d0e1 双库 head；SQLite 全量 22 脚本 0 失败（含新 test_logic_graph 19 断言）+ PG 13/13 + tsc 0 错误。\n> 2026-09-23：TASK-003 完成"
assert old in s, "backlog log anchor"
s = s.replace(old, add, 1)

# 3) Backlog Items 区 TASK-014 行（若存在）状态更新：检查是否有 TASK-014 行
if "| TASK-014 |" in s:
    # 行内更新：找 Backlog Items 的 TASK-014 行
    import re
    def rep(m):
        line = m.group(0)
        if "DONE" in line:
            return line
        return line.replace("| READY |", "| DONE |", 1).replace("| BACKLOG |", "| DONE |", 1)
    s2 = re.sub(r"\| TASK-014 \|[^\n]*", rep, s)
    s = s2
p.write_text(s, encoding="utf-8")
print("OK BACKLOG.md")