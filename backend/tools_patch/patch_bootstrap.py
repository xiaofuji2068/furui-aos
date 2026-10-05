# -*- coding: utf-8 -*-
"""TASK-002 种子补丁：bootstrap.py 新增巡检 Agent / IoT 数据源 / 新工具 / 巡检场景 / 知识补全。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\bootstrap.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

changed = []

# ---------- 1. KB_SEED：工业空间智能知识库补 2 篇（辐射防护 / 巡检归因标准） ----------
old_kb_tail = '''            {
                "title": "AI 辅助巡检作业规范",
                "source": "技术中心 · 运维组",
                "content": """AI 辅助巡检作业规范
'''
# 直接在 AI 辅助巡检作业规范这篇之前插入两篇新文档
kb_anchor = '            {\n                "title": "AI 辅助巡检作业规范",'
assert kb_anchor in src, "kb anchor missing"
new_docs = '''            {
                "title": "辐射防护与监测限值标准",
                "source": "安全环保部 · 2026 版",
                "content": """辐射防护与监测限值标准

一、适用范围
核电厂运行与检修期间的辐射监测、个人剂量控制与异常响应。

二、监测限值
1. 区域剂量率（核岛运行区）常规限值 20 uSv/h，超过即触发告警。
2. 个人年剂量限值 20 mSv，月剂量超过 1/12 年度限值须评估作业安排。
3. 辐射监测站读数与阈值须每季度校准一次，偏差超过 5% 须上报。

三、异常响应
1. 剂量率超过限值时，AI 系统应在 15 分钟内完成初步归因：
   区分「设备故障 / 源项异常 / 测量装置漂移 / 背景波动」四类。
2. 初步归因须附带数据依据（读数、时间序列、关联设备状态），
   人工复核确认后 2 小时内生成处置工单。
3. 处置完成后 24 小时内闭环验收，异常记录保存期不少于 3 年。
""",
            },
            {
                "title": "核电设备巡检异常归因标准",
                "source": "技术中心 · 运维组",
                "content": """核电设备巡检异常归因标准

一、适用范围
辐射监测站、转动设备（主冷却泵等）、管道阀门等关键设备的
在线监测异常分析与处置。

二、归因维度（按序排查）
1. 指标维度：辐射剂量率、温度、振动三指标分别与各自阈值比对，
   超限指标单独归因。
2. 站点维度：同一厂区内多个监测站同时异常，优先怀疑共因
   （电源、网络、环境）；单站异常优先怀疑设备本体。
3. 时间维度：与上月同周期对比，识别持续劣化（连续上升）与
   突发的区别。

三、处置分级
1. 单指标超限 <15%：生成预警，纳入日巡检重点。
2. 单指标超限 ≥15% 或健康度 <60：生成工单，人工确认后 24 小时内处置。
3. 多指标同时超限或健康度 <40：升级为紧急工单，2 小时内响应。

四、闭环要求
工单须记录：异常描述、归因结论、处置动作、验收结果，全程留痕。
""",
            },
            {
                "title": "AI 辅助巡检作业规范",'''
src = src.replace(kb_anchor, new_docs, 1)
changed.append("kb_docs")

# ---------- 2. AGENT_SEED：新增巡检分析 Agent ----------
old_ops = '''    {
        "name": "设备运维 Agent",
        "code": "ops-engineer",'''
assert old_ops in src, "ops agent anchor missing"
new_ops = '''    {
        "name": "巡检分析 Agent",
        "code": "inspection-analyst",
        "avatar": "☢️",
        "position": "核电巡检分析师",
        "agent_type": "analyst",
        "description": "负责核电设备巡检数据分析、异常归因与处置工单建议，可查询监测站与设备指标数据。",
        "system_prompt": "你是核电巡检分析师。回答必须基于真实查询结果，禁止编造数据；超限结论须引用辐射防护与巡检归因标准。",
        "goal": "及时发现设备异常并给出可执行的处置建议。",
        "rules": "1. 先查数据再下结论；2. 引用巡检归因标准；3. 创建工单需人工审批。",
        "actions": ["read", "analyze", "report", "write"],
        "approval_level": 3,
        "skills": ["query_monitoring_stations", "query_device_metrics",
                   "search_knowledge", "analyze_inspection_anomaly", "create_workorder"],
        "color": "from-amber-500 to-red-500",
        "capabilities": ["监测站状态监控", "设备指标分析", "异常归因",
                         "健康度预警", "巡检工单生成", "辐射防护合规核查"],
        "status": "Published",
    },
    {
        "name": "设备运维 Agent",
        "code": "ops-engineer",'''
src = src.replace(old_ops, new_ops, 1)
changed.append("agent")

# ---------- 3. TOOL_SEED：新增 3 工具 + 更新 create_workorder 文案 ----------
old_tool_wo = '    ("create_workorder",    "创建设备工单",     "执行工具", "为设备异常创建维护工单（写入动作）", 3, "tool:use"),'
new_tool_wo = '''    ("create_workorder",          "创建核电巡检工单", "执行工具", "为监测站/设备异常创建巡检处置工单（写入动作）", 3, "tool:use"),
    ("query_monitoring_stations", "查询核电监测站台账", "查询工具", "查询监测站基础信息与状态", 1, "datasource:view"),
    ("query_device_metrics",      "查询设备指标读数",   "查询工具", "查询辐射/温度/振动指标与阈值", 1, "datasource:view"),
    ("analyze_inspection_anomaly", "巡检异常归因分析", "分析工具", "按指标/站点/环比三维度拆解巡检异常", 1, "tool:use"),'''
assert old_tool_wo in src, "tool seed anchor missing"
src = src.replace(old_tool_wo, new_tool_wo, 1)
changed.append("tool_seed")

# ---------- 4. _seed_datasources：新增 IoT 数据源 ----------
old_ds = '''    db.add_all([erp, crm])
    db.flush()'''
assert old_ds in src, "ds anchor missing"
new_ds = '''    iot = DataSource(
        company_id=company_id, name="IoT 设备监测系统", source_type="SQLite", category="IoT",
        description="模拟 IoT：核电监测站、设备指标、巡检记录（只读）",
        allowed_tables=json.dumps(["monitoring_stations", "device_metrics", "inspection_records"]),
        sensitive_fields=json.dumps([]),
        read_only=True, status="Connected",
    )
    db.add_all([erp, crm, iot])
    db.flush()'''
src = src.replace(old_ds, new_ds, 1)

old_conn = '''    db.add(DataConnection(
        source_id=crm.id, company_id=company_id, name="CRM 主连接",
        dsn="data/erp_crm.db", status="Connected", created_by="系统初始化",
    ))
    db.commit()
    return [erp.id, crm.id]'''
assert old_conn in src, "ds conn anchor missing"
new_conn = '''    db.add(DataConnection(
        source_id=crm.id, company_id=company_id, name="CRM 主连接",
        dsn="data/erp_crm.db", status="Connected", created_by="系统初始化",
    ))
    db.add(DataConnection(
        source_id=iot.id, company_id=company_id, name="IoT 设备监测主连接",
        dsn="data/erp_crm.db", status="Connected", created_by="系统初始化",
    ))
    db.commit()
    return [erp.id, crm.id, iot.id]'''
src = src.replace(old_conn, new_conn, 1)
changed.append("datasource")

# ---------- 5. _seed_agents：数据源授权逻辑按 agent code 区分 ----------
old_dsids = '''            allowed_knowledge_ids=json.dumps(kb_ids if a["code"] != "knowledge-assistant" else kb_ids),
            allowed_datasource_ids=json.dumps(ds_ids if a["code"] == "sales-analyst" else []),'''
assert old_dsids in src, "ds ids anchor missing"
new_dsids = '''            allowed_knowledge_ids=json.dumps(kb_ids if a["code"] != "knowledge-assistant" else kb_ids),
            allowed_datasource_ids=json.dumps(
                ds_ids if a["code"] in ("sales-analyst", "inspection-analyst", "ops-engineer")
                else []),'''
src = src.replace(old_dsids, new_dsids, 1)
changed.append("agent_ds")

# ---------- 6. _seed_scenarios：新增核电巡检场景 ----------
old_scn = '''    db.add(BusinessScenario(
        company_id=company_id, application_id=app.id,
        name="大客户流失预警", category="销售", owner="王欢", department="销售部",
        problem="大客户订单下滑发现滞后，错过挽回窗口",
        acceptance="大客户环比下滑超 30% 时自动预警并生成挽回任务",
        stage="测试中", progress=45, status="测试中",
    ))
    db.commit()'''
assert old_scn in src, "scenario anchor missing"
new_scn = '''    db.add(BusinessScenario(
        company_id=company_id, application_id=app.id,
        name="大客户流失预警", category="销售", owner="王欢", department="销售部",
        problem="大客户订单下滑发现滞后，错过挽回窗口",
        acceptance="大客户环比下滑超 30% 时自动预警并生成挽回任务",
        stage="测试中", progress=45, status="测试中",
    ))

    app2 = AIApplication(
        company_id=company_id, name="核电巡检智能分析", code="NUCLEAR-INSPECT-AI",
        description="设备监测异常归因、健康度预警与处置工单", owner="张工", status="running",
    )
    db.add(app2)
    db.flush()

    db.add(BusinessScenario(
        company_id=company_id, application_id=app2.id,
        name="监测站异常自动归因", category="核电巡检", owner="张工", department="运维部",
        problem="设备指标超限后人工排查慢、口径不统一",
        acceptance="输入问题后 60 秒内输出归因报告，超限站点与指标可复核",
        stage="运行中", progress=80, status="运行中",
    ))
    db.add(BusinessScenario(
        company_id=company_id, application_id=app2.id,
        name="设备健康度预警", category="核电巡检", owner="李工", department="运维部",
        problem="设备劣化趋势发现滞后，存在非计划停机风险",
        acceptance="健康度低于阈值或连续劣化时自动预警并生成处置工单",
        stage="测试中", progress=45, status="测试中",
    ))
    db.commit()'''
src = src.replace(old_scn, new_scn, 1)
changed.append("scenarios")

with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("BOOTSTRAP PATCH OK:", changed)
