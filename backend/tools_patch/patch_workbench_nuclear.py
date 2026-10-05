# -*- coding: utf-8 -*-
"""TASK-002 #13：工作台前端对齐——TOOL_LABEL 巡检工具 + agent_code 巡检模式 + 工单审批结果展示 + 巡检快捷问题。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend\app\workbench\page.tsx"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

# ---- 1) TOOL_LABEL 补巡检工具 ----
old = '''const TOOL_LABEL: Record<string, string> = {
  query_erp_orders: "ERP 销售数据",
  query_crm_customers: "CRM 客户信息",
  search_knowledge: "企业知识库",
  analyze_sales_drop: "归因分析引擎",
  create_sales_task: "CRM 任务写入",
};'''
new = '''const TOOL_LABEL: Record<string, string> = {
  query_erp_orders: "ERP 销售数据",
  query_crm_customers: "CRM 客户信息",
  search_knowledge: "企业知识库",
  analyze_sales_drop: "销售归因分析引擎",
  create_sales_task: "CRM 任务写入",
  query_monitoring_stations: "核电监测站台账",
  query_device_metrics: "设备指标读数",
  analyze_inspection_anomaly: "巡检异常归因引擎",
  create_workorder: "巡检处置工单",
};'''
assert old in src, "tool_label anchor missing"
src = src.replace(old, new, 1)

# ---- 2) 快捷问题加巡检场景 ----
old = '''const QUICK = [
  "分析本月销售下降原因",
  "哪些大客户存在流失风险",
  "本月新客户开拓情况如何",
  "各区域销售表现对比",
];'''
new = '''const QUICK = [
  "分析本月销售下降原因",
  "哪些大客户存在流失风险",
  "8月核电设备巡检异常归因",
  "各监测站设备健康度如何",
];'''
assert old in src, "quick anchor missing"
src = src.replace(old, new, 1)

# ---- 3) run() 支持按问题路由 agent_code（巡检问题走 inspection-analyst）----
old = '''      try {
        await streamSSE(
          "/mainline/run",
          { question: q, agent_code: "sales-analyst" },
          (event, data) => {'''
new = '''      try {
        const isInspection = /巡检|监测站|辐射|设备健康|工单/.test(q);
        const agentCode = isInspection ? "inspection-analyst" : "sales-analyst";
        await streamSSE(
          "/mainline/run",
          { question: q, agent_code: agentCode },
          (event, data) => {'''
assert old in src, "agent_code anchor missing"
src = src.replace(old, new, 1)

# ---- 4) 审批通过结果按工单/任务分别展示 ----
old = '''      const txt =
        action === "approve"
          ? r.sales_task
            ? `已执行，生成跟进任务 #${r.sales_task.id}：${r.sales_task.title}（负责人 ${r.sales_task.owner}，截止 ${r.sales_task.due_date}）`
            : "已批准并执行"
          : "已拒绝，Agent 不会执行该动作";'''
new = '''      const workorder = r?.result?.workorder_id || r?.workorder;
      const salesTask = r?.sales_task;
      const txt =
        action === "approve"
          ? workorder
            ? `已执行，生成巡检工单 #${r.result?.workorder_id}：${r.result?.title}（负责人 ${r.result?.owner}，截止 ${r.result?.due_date}）`
            : salesTask
              ? `已执行，生成跟进任务 #${salesTask.id}：${salesTask.title}（负责人 ${salesTask.owner}，截止 ${salesTask.due_date}）`
              : "已批准并执行"
          : "已拒绝，Agent 不会执行该动作";'''
assert old in src, "decide txt anchor missing"
src = src.replace(old, new, 1)

with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("WORKBENCH PATCH OK")
