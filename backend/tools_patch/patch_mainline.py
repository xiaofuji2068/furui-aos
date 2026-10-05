# -*- coding: utf-8 -*-
"""TASK-002 主线补丁 v2：mainline.py 按 Agent 选择链路（销售 / 核电巡检）。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\mainline.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

changed = []

# ---------- 1. PLAN 之后追加 PLAN_INSPECTION + _pick_plan ----------
old_plan = '''    {"seq": 6, "title": "创建销售跟进任务（需审批）", "kind": "approval",  "tool": "create_sales_task", "depends": [5]},
]'''
assert old_plan in src, "plan tail missing"
new_plan = '''    {"seq": 6, "title": "创建销售跟进任务（需审批）", "kind": "approval",  "tool": "create_sales_task", "depends": [5]},
]

# ---- TASK-002 核电巡检主线（inspection-analyst 使用）----
PLAN_INSPECTION: List[Dict[str, Any]] = [
    {"seq": 1, "title": "查询核电监测站台账",        "kind": "data",      "tool": "query_monitoring_stations"},
    {"seq": 2, "title": "查询设备指标与阈值读数",    "kind": "data",      "tool": "query_device_metrics"},
    {"seq": 3, "title": "检索巡检归因与辐射防护规范", "kind": "knowledge", "tool": "search_knowledge"},
    {"seq": 4, "title": "按指标/站点/环比做异常归因",  "kind": "tool",      "tool": "analyze_inspection_anomaly", "depends": [1, 2]},
    {"seq": 5, "title": "生成巡检归因结论与处置建议",  "kind": "report",    "depends": [3, 4]},
    {"seq": 6, "title": "创建巡检处置工单（需审批）",  "kind": "approval",  "tool": "create_workorder", "depends": [5]},
]


def _pick_plan(agent: Agent) -> List[Dict[str, Any]]:
    """按 Agent code 选择执行链路；默认销售链路（兼容既有测试）。"""
    return PLAN_INSPECTION if getattr(agent, "code", "") == "inspection-analyst" else PLAN'''
src = src.replace(old_plan, new_plan, 1)
changed.append("plan_inspection")

# ---------- 2. run() 内三处 PLAN 引用改为 self.plan，并在开头设定 ----------
old_set = '''        db = self.db

        # ---- 1. 创建或重置持久化任务'''
new_set = '''        db = self.db
        self.plan = _pick_plan(self.agent)

        # ---- 1. 创建或重置持久化任务'''
assert old_set in src, "run head missing"
src = src.replace(old_set, new_set, 1)
changed.append("run_plan_set")

src = src.replace("        for p in PLAN:\n", "        for p in self.plan:\n", 1)
src = src.replace('"plan": [{"seq": p["seq"], "title": p["title"]} for p in PLAN]}',
                  '"plan": [{"seq": p["seq"], "title": p["title"]} for p in self.plan]}', 1)
src = src.replace("        for p in PLAN[:5]:", "        for p in self.plan[:5]:", 1)
changed.append("run_plan_refs")

# ---------- 3. data 分支：新增巡检两步（在 query_erp_orders 之前） ----------
old_data1 = '''            if p["kind"] == "data" and p["tool"] == "query_erp_orders":'''
assert old_data1 in src, "data1 missing"
new_data1 = '''            if p["kind"] == "data" and p["tool"] == "query_monitoring_stations":
                r = gw_execute(self.ctx, "query_monitoring_stations", {})
                collected["stations"] = r.get("result", {})
                ok = bool(r.get("ok"))
                err = "" if ok else (r.get("error") or r.get("reason") or "监测站查询失败")
                self._log_exec(step, action="query_data", label="AI 正在查询核电监测站台账",
                               tool_name="query_monitoring_stations",
                               output_data=r.get("result", {}).get("summary"),
                               status="Completed" if ok else "Failed", error=err, started=t0)
                yield {"event": "tool_result", "data": {"tool": "query_monitoring_stations",
                                                        "ok": ok, "error": err,
                                                        "summary": r.get("result", {}).get("summary")}}
                if not ok:
                    for ev in self._fail(step, p, err):
                        yield ev
                    return
                step.output_data = json.dumps(
                    {"summary": r.get("result", {}).get("summary")}, ensure_ascii=False)

            elif p["kind"] == "data" and p["tool"] == "query_device_metrics":
                r = gw_execute(self.ctx, "query_device_metrics", {"month": "2026-08"})
                collected["metrics"] = r.get("result", {})
                ok = bool(r.get("ok"))
                err = "" if ok else (r.get("error") or r.get("reason") or "设备指标查询失败")
                self._log_exec(step, action="query_data", label="AI 正在查询设备指标读数",
                               tool_name="query_device_metrics", input_data={"month": "2026-08"},
                               output_data={"rows": r.get("result", {}).get("rows", [])[:5]},
                               status="Completed" if ok else "Failed", error=err, started=t0)
                yield {"event": "tool_result", "data": {"tool": "query_device_metrics",
                                                        "ok": ok, "error": err,
                                                        "rows": r.get("result", {}).get("rows", [])[:5]}}
                if not ok:
                    for ev in self._fail(step, p, err):
                        yield ev
                    return
                step.output_data = json.dumps(
                    {"summary": r.get("result", {}).get("summary"),
                     "rows": r.get("result", {}).get("rows", [])[:5]}, ensure_ascii=False)

            elif p["kind"] == "data" and p["tool"] == "query_erp_orders":'''
src = src.replace(old_data1, new_data1, 1)
changed.append("data_branches")

# ---------- 4. knowledge 分支：查询词按链路分流 ----------
old_kq = '''            elif p["kind"] == "knowledge":
                q = "销售下降归因 大客户流失 价格下调 新客户"'''
assert old_kq in src, "knowledge missing"
new_kq = '''            elif p["kind"] == "knowledge":
                if getattr(self.agent, "code", "") == "inspection-analyst":
                    q = "巡检异常归因 辐射防护限值 设备健康度 工单处置"
                else:
                    q = "销售下降归因 大客户流失 价格下调 新客户"'''
src = src.replace(old_kq, new_kq, 1)
changed.append("knowledge_query")

# ---------- 5. tool 分支：新增巡检归因（在 analyze_sales_drop 之前） ----------
old_tool = '''            elif p["kind"] == "tool" and p["tool"] == "analyze_sales_drop":'''
assert old_tool in src, "tool anchor missing"
new_tool = '''            elif p["kind"] == "tool" and p["tool"] == "analyze_inspection_anomaly":
                r = gw_execute(self.ctx, "analyze_inspection_anomaly", {})
                collected["analysis"] = r.get("result", {})
                ok = bool(r.get("ok"))
                err = "" if ok else (r.get("error") or r.get("reason") or "巡检归因失败")
                self._log_exec(step, action="call_tool", label="AI 正在按指标/站点/环比做巡检归因",
                               tool_name="analyze_inspection_anomaly",
                               output_data=collected["analysis"],
                               status="Completed" if ok else "Failed", error=err, started=t0)
                yield {"event": "tool_result", "data": {"tool": "analyze_inspection_anomaly",
                                                        "ok": ok, "error": err,
                                                        "overview": collected["analysis"].get("overview")}}
                if not ok:
                    for ev in self._fail(step, p, err):
                        yield ev
                    return
                step.output_data = json.dumps(collected["analysis"], ensure_ascii=False)

            elif p["kind"] == "tool" and p["tool"] == "analyze_sales_drop":'''
src = src.replace(old_tool, new_tool, 1)
changed.append("tool_branch")

# ---------- 6. step6 分支：巡检工单（在 sales top 之前） ----------
old_step6 = '''        analysis = collected.get("analysis") or {}
        top = analysis.get("top_drop_customer")
        payload: Dict[str, Any] = {}'''
assert old_step6 in src, "step6 missing"
new_step6 = '''        analysis = collected.get("analysis") or {}
        if getattr(self.agent, "code", "") == "inspection-analyst":
            top = analysis.get("top_alarm")
            payload: Dict[str, Any] = {}
            if top:
                payload = {
                    "title": f"{top['station_name']}巡检异常处置",
                    "station_code": top["station_code"],
                    "station_name": top["station_name"],
                    "priority": "high",
                    "owner": "张工",
                    "due_date": self._due_date(),
                    "detail": (f"{top['station_name']}（{top['station_code']}）位于{top['area']}，"
                               f"{top['metric']}读数 {top['value']}{top['unit']}，"
                               f"超阈值 {top['threshold']}{top['unit']}（超限 {abs(top['over_pct'])}%）。"
                               f"按《核电设备巡检异常归因标准》：单指标超限 ≥15% 生成工单，"
                               f"人工复核后 24 小时内处置并闭环验收。"),
                    "_reason": f"该站点为巡检异常主因，超限 {abs(top['over_pct'])}%，处置优先级高。",
                    "_evidence": {"station": top, "overview": analysis.get("overview")},
                    "_plan": {"action": "create_workorder", "level": 3,
                              "steps": ["人工复核归因结论", "现场确认异常状态",
                                        "消缺处置", "24 小时闭环验收"]},
                }
                r = gw_execute(self.ctx, "create_workorder", payload)
                collected["approval"] = r
                self._log_exec(step6, action="call_tool", label="AI 请求创建核电巡检工单",
                               tool_name="create_workorder", input_data=payload,
                               output_data=r, status="WaitingApproval",
                               started=time.time())
                step6.output_data = json.dumps(r, ensure_ascii=False)[:4000]
                if r.get("blocked"):
                    self.task.transition("WaitingApproval")
                    self._step(step6, "Completed")
                    self._progress()
                    self._advance_stage(step6)
                    db.commit()
                    yield {"event": "step", "data": {"seq": 6, "title": step6.title, "status": "Completed"}}
                    yield {"event": "pending", "data": {
                        "approval_id": r["approval_id"],
                        "title": "创建核电巡检工单",
                        "station": top["station_code"],
                        "message": f"建议为 {top['station_name']} 创建巡检处置工单，需你确认后执行。",
                    }}
                else:
                    self._step(step6, "Completed", error=str(r.get("error", "")))
                    self._advance_stage(step6)
                    yield {"event": "step", "data": {"seq": 6, "title": step6.title, "status": "Completed"}}
            else:
                self._step(step6, "Skipped", error="未定位到明确的异常站点，跳过工单创建")
                self._advance_stage(step6)
                yield {"event": "step", "data": {"seq": 6, "title": step6.title, "status": "Skipped"}}
        else:
            top = analysis.get("top_drop_customer")
            payload: Dict[str, Any] = {}'''
src = src.replace(old_step6, new_step6, 1)
changed.append("step6_inspection")

# ---------- 7. _render_report 分派 + _render_inspection_report ----------
old_render = '''    def _render_report(self, c: Dict[str, Any]) -> str:
        a = c.get("analysis") or {}'''
assert old_render in src, "render missing"
new_render = '''    def _render_report(self, c: Dict[str, Any]) -> str:
        if getattr(self.agent, "code", "") == "inspection-analyst":
            return self._render_inspection_report(c)
        a = c.get("analysis") or {}'''
src = src.replace(old_render, new_render, 1)

old_polish = '''    async def _polish(self, report: str, c: Dict[str, Any]) -> str:'''
assert old_polish in src, "polish missing"
new_polish = '''    def _render_inspection_report(self, c: Dict[str, Any]) -> str:
        a = c.get("analysis") or {}
        ov = a.get("overview") or {}
        months = a.get("months") or {}
        top = a.get("top_alarm")
        alarms = a.get("alarm_dimension") or []
        deltas = a.get("delta_dimension") or []
        hits = c.get("knowledge") or []

        L: List[str] = []
        L.append(f"## 核电巡检异常归因分析（{months.get('current','')} 对比 {months.get('previous','')}）\\n")
        L.append("### 一、总体情况\\n")
        curr_ov = ov.get("current") or {}
        L.append(f"- 监测站总数：**{curr_ov.get('total_stations','-')}** 个")
        L.append(f"- 异常站点：**{ov.get('alarm_stations_curr','-')}** 个（辐射 / 温度 / 振动任一指标超限）\\n")

        L.append("### 二、归因结论\\n")
        idx = 1
        if top:
            L.append(f"**主因 {idx}｜{top['station_name']}（{top['station_code']}）{top['metric']}超限 {abs(top['over_pct'])}%**")
            L.append(f"位于{top['area']}，{top['metric']}读数为 {top['value']}{top['unit']}，"
                     f"阈值 {top['threshold']}{top['unit']}，超出 {abs(top['over_pct'])}%。")
            L.append("依据《辐射防护与监测限值标准》：超过限值须 15 分钟内完成初步归因并人工复核。\\n")
            idx += 1
        for al in alarms[1:3]:
            L.append(f"**次因 {idx}｜{al['station_name']}（{al['station_code']}）{al['metric']}超限 {abs(al['over_pct'])}%**")
            L.append(f"{al['metric']}读数为 {al['value']}{al['unit']}，阈值 {al['threshold']}{al['unit']}。")
            L.append("依据《核电设备巡检异常归因标准》：单指标超限 ≥15% 生成工单，24 小时内处置。\\n")
            idx += 1
        if deltas:
            for d in deltas:
                if d.get("change_pct") and d["change_pct"] >= 15 and d.get("station_code") != (top or {}).get("station_code"):
                    L.append(f"**次因 {idx}｜{d['station_code']} {d['metric']}环比上升 {d['change_pct']}%**")
                    L.append(f"由 {d['prev_value']}{d['unit']} 升至 {d['curr_value']}{d['unit']}，呈持续劣化趋势。")
                    L.append("依据《核电设备巡检异常归因标准》：持续劣化按时间维度归因，纳入工单处置。\\n")
                    idx += 1

        L.append("### 三、建议动作\\n")
        n = 1
        if top:
            L.append(f"{n}. 【紧急】对 {top['station_name']}（{top['station_code']}）按《辐射防护与监测限值标准》"
                     f"处置流程执行：15 分钟归因 → 人工复核 → 2 小时内出具工单。")
            n += 1
        for al in alarms[1:3]:
            L.append(f"{n}. 【24 小时】处置 {al['station_name']}（{al['station_code']}）的 {al['metric']} 超限，"
                     f"完成现场确认与消缺。")
            n += 1
        L.append(f"{n}. 【持续】将全部监测站纳入日巡检重点，健康度低于 60 自动升级预警。\\n")

        if top:
            L.append("### 四、待确认\\n")
            L.append(f"是否需要为 **{top['station_name']}**（{top['station_code']}）创建巡检处置工单？"
                     "该动作属于 Level 3，需你确认后才会真正写入工单系统。")

        if hits:
            L.append(format_citations(hits))
        return "\\n".join(L)

    async def _polish(self, report: str, c: Dict[str, Any]) -> str:'''
src = src.replace(old_polish, new_polish, 1)
changed.append("render_inspection")

with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("MAINLINE PATCH OK:", changed)
