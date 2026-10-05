# -*- coding: utf-8 -*-
"""TASK-002 种子幂等修复：_seed_agents / _seed_datasources / _seed_scenarios 改为逐条增量补齐。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\bootstrap.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

changed = []

# ---------- 1. _seed_agents：既有补齐逻辑后，继续处理"完全新增"的 Agent ----------
old_agents = '''    existing = {a.code: a for a in db.query(Agent).filter(Agent.company_id == company_id).all()}
    if existing:
        # 幂等补齐：老库升级时回填 color/capabilities，并补绑新增 Skill（如 create_workorder）
        for a in AGENT_SEED:
            ag = existing.get(a["code"])
            if not ag:
                continue
            changed = False
            if not ag.color and a.get("color"):
                ag.color = a["color"]
                changed = True
            if ag.capabilities in ("", "[]") and a.get("capabilities"):
                ag.capabilities = json.dumps(a["capabilities"], ensure_ascii=False)
                changed = True
            bound = {s.skill_name for s in ag.skills}
            for s in a["skills"]:
                if s in tool_ids and s not in bound:
                    db.add(AgentSkill(agent_id=ag.id, skill_name=s, enabled=True))
                    tid = tool_ids[s]
                    if tid not in ag.tool_ids:
                        ag.allowed_tool_ids = json.dumps(ag.tool_ids + [tid])
                    changed = True
            if changed:
                db.commit()
        return
'''
new_agents = '''    existing = {a.code: a for a in db.query(Agent).filter(Agent.company_id == company_id).all()}
    if existing:
        # 幂等补齐：老库升级时回填 color/capabilities，并补绑新增 Skill（如 create_workorder）
        for a in AGENT_SEED:
            ag = existing.get(a["code"])
            if not ag:
                continue
            changed = False
            if not ag.color and a.get("color"):
                ag.color = a["color"]
                changed = True
            if ag.capabilities in ("", "[]") and a.get("capabilities"):
                ag.capabilities = json.dumps(a["capabilities"], ensure_ascii=False)
                changed = True
            bound = {s.skill_name for s in ag.skills}
            for s in a["skills"]:
                if s in tool_ids and s not in bound:
                    db.add(AgentSkill(agent_id=ag.id, skill_name=s, enabled=True))
                    tid = tool_ids[s]
                    if tid not in ag.tool_ids:
                        ag.allowed_tool_ids = json.dumps(ag.tool_ids + [tid])
                    changed = True
            if changed:
                db.commit()
    # 逐条补齐完全新增的 Agent（如 TASK-002 巡检分析 Agent）
    for a in AGENT_SEED:
        if a["code"] in existing:
            continue
        agent = Agent(
            company_id=company_id,
            department_id=dept_map.get("销售部"),
            name=a["name"],
            code=a["code"],
            avatar=a["avatar"],
            position=a["position"],
            agent_type=a["agent_type"],
            description=a["description"],
            system_prompt=a["system_prompt"],
            goal=a["goal"],
            rules=a["rules"],
            status=a["status"],
            # 四类白名单：知识 / 数据 / 工具 / 操作
            allowed_knowledge_ids=json.dumps(kb_ids if a["code"] != "knowledge-assistant" else kb_ids),
            allowed_datasource_ids=json.dumps(
                ds_ids if a["code"] in ("sales-analyst", "inspection-analyst", "ops-engineer")
                else []),
            allowed_tool_ids=json.dumps([tool_ids[s] for s in a["skills"] if s in tool_ids]),
            allowed_actions=json.dumps(a["actions"]),
            approval_level=a["approval_level"],
            color=a.get("color", ""),
            capabilities=json.dumps(a.get("capabilities", []), ensure_ascii=False),
        )
        db.add(agent)
        db.flush()
        for s in a["skills"]:
            db.add(AgentSkill(agent_id=agent.id, skill_name=s, enabled=True))
        existing[a["code"]] = agent
    db.commit()
'''
assert old_agents in src, "agents block missing"
src = src.replace(old_agents, new_agents, 1)
changed.append("agents_incremental")

# ---------- 2. _seed_datasources：逐条按 name 补齐 ----------
old_ds = '''def _seed_datasources(db: Session, company_id: int) -> List[int]:
    if db.query(DataSource).filter(DataSource.company_id == company_id).count() > 0:
        return [d.id for d in db.query(DataSource).filter(DataSource.company_id == company_id).all()]

    erp = DataSource('''
new_ds = '''def _seed_datasources(db: Session, company_id: int) -> List[int]:
    ds_map = {d.name: d for d in db.query(DataSource).filter(DataSource.company_id == company_id).all()}
    if ds_map:
        existing = [d.id for d in ds_map.values()]
        # 逐条补齐新增数据源（如 TASK-002 IoT 设备监测系统）
        if "IoT 设备监测系统" not in ds_map:
            iot = DataSource(
                company_id=company_id, name="IoT 设备监测系统", source_type="SQLite", category="IoT",
                description="模拟 IoT：核电监测站、设备指标、巡检记录（只读）",
                allowed_tables=json.dumps(["monitoring_stations", "device_metrics", "inspection_records"]),
                sensitive_fields=json.dumps([]),
                read_only=True, status="Connected",
            )
            db.add(iot)
            db.flush()
            from .models_ai import DataConnection
            db.add(DataConnection(
                source_id=iot.id, company_id=company_id, name="IoT 设备监测主连接",
                dsn="data/erp_crm.db", status="Connected", created_by="系统初始化",
            ))
            db.commit()
            existing.append(iot.id)
        return existing

    erp = DataSource('''
assert old_ds in src, "ds block missing"
src = src.replace(old_ds, new_ds, 1)
changed.append("datasource_incremental")

# ---------- 3. _seed_scenarios：逐条按 name 补齐（含巡检场景） ----------
old_scn = '''def _seed_scenarios(db: Session, company_id: int) -> None:
    if db.query(BusinessScenario).filter(BusinessScenario.company_id == company_id).count() > 0:
        return
'''
new_scn = '''def _seed_scenarios(db: Session, company_id: int) -> None:
    # 已存在的场景名集合（用于增量补齐新场景）
    existing_names = {s.name for s in db.query(BusinessScenario).filter(BusinessScenario.company_id == company_id).all()}
    if existing_names and not {"监测站异常自动归因", "设备健康度预警"} - existing_names:
        return
'''
assert old_scn in src, "scn block missing"
src = src.replace(old_scn, new_scn, 1)
changed.append("scenario_incremental_gate")

# 场景函数末尾：在 app2 之前加"已有销售场景则跳过销售部分"保护（保持原样即可，因为巡检场景是新代码块）
# 检查现有巡检场景块是否已被种入（名字存在则跳过创建），改为在创建 app2 前判断
old_app2 = '''    app2 = AIApplication(
        company_id=company_id, name="核电巡检智能分析", code="NUCLEAR-INSPECT-AI",'''
if old_app2 in src:
    new_app2 = '''    if "监测站异常自动归因" in existing_names:
        return
    app2 = AIApplication(
        company_id=company_id, name="核电巡检智能分析", code="NUCLEAR-INSPECT-AI",'''
    src = src.replace(old_app2, new_app2, 1)
    changed.append("scenario_incremental_body")

with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("SEED FIX OK:", changed)
