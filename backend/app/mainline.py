"""销售下降归因主线 — 持久化编排器（TASK-008 / TASK-010 / TASK-030）。

清单「第一版必须跑通的完整测试案例」：
    用户提问 → AI 工作台创建任务 → 调用销售分析 Agent → Agent 制定计划
    → 查 ERP → 查 CRM → 查企业知识 → Agent 分析 → 生成原因 → 提出建议
    → 用户确认 → 创建销售任务 → 记录日志 → 返回结果 → Dashboard 更新

与旧 orchestrator 的根本区别：
  旧版把任务放在内存 list 里，重启即丢，也没有步骤、依赖、执行日志。
  本编排器每一步都落库（AgentTask / AgentStep / AgentExecution / Approval），
  所以过程可回放、可审计、可断点续跑。

结论生成原则：
  数字全部来自 SQL 真实计算，绝不靠 LLM 编造。
  LLM 只在有 key 时负责把已算清的事实润色成自然语言；没有 key 就用规则化模板，
  保证端到端永远能跑通、结论永远可复核。
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from sqlalchemy.orm import Session

from .models import User
from .models_ai import (
    Agent, AgentExecution, AgentStage, AgentStep, AgentTask, Approval,
    Notification, STAGE_PLAN, write_audit,
)
from .rag import format_citations
from .tool_gateway import ToolContext, execute as gw_execute


# 主线执行计划：kind 决定前端展示的过程文案
PLAN: List[Dict[str, Any]] = [
    {"seq": 1, "title": "查询 ERP 销售订单数据",     "kind": "data",      "tool": "query_erp_orders"},
    {"seq": 2, "title": "查询 CRM 客户与分级信息",   "kind": "data",      "tool": "query_crm_customers"},
    {"seq": 3, "title": "检索企业知识库归因规范",    "kind": "knowledge", "tool": "search_knowledge"},
    {"seq": 4, "title": "按三维度做销售归因分析",    "kind": "tool",      "tool": "analyze_sales_drop", "depends": [1, 2]},
    {"seq": 5, "title": "生成归因结论与改进建议",    "kind": "report",    "depends": [3, 4]},
    {"seq": 6, "title": "创建销售跟进任务（需审批）", "kind": "approval",  "tool": "create_sales_task", "depends": [5]},
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
    return PLAN_INSPECTION if getattr(agent, "code", "") == "inspection-analyst" else PLAN


class MainlineRunner:
    """一次主线任务的完整生命周期。"""

    def __init__(self, db: Session, agent: Agent, user: User,
                 company_id: int, conversation_id: str = ""):
        self.db = db
        self.agent = agent
        self.user = user
        self.company_id = company_id
        self.conversation_id = conversation_id or f"C-{uuid.uuid4().hex[:8].upper()}"

    # ---------- 内部工具 ----------

    @property
    def ctx(self) -> ToolContext:
        return ToolContext(db=self.db, agent=self.agent, user=self.user,
                           company_id=self.company_id, task_id=self.task.id if self.task else None)

    def _log_exec(self, step: Optional[AgentStep], *, action: str, label: str,
                  status: str = "Completed", input_data=None, output_data=None,
                  error: str = "", tool_name: str = "", started: float = 0) -> None:
        rec = AgentExecution(
            company_id=self.company_id,
            task_id=self.task.id if self.task else None,
            step_id=step.id if step else None,
            agent_id=self.agent.id if self.agent else None,
            action=action, label=label, status=status,
            input_data=json.dumps(input_data or {}, ensure_ascii=False)[:4000],
            output_data=json.dumps(output_data or {}, ensure_ascii=False)[:4000],
            error=error, tool_name=tool_name,
            duration_ms=int((time.time() - started) * 1000) if started else 0,
        )
        self.db.add(rec)
        self.db.flush()

    def _step(self, step: AgentStep, status: str, **kw) -> None:
        step.status = status
        for k, v in kw.items():
            setattr(step, k, v)
        if status == "Running" and not step.started_at:
            step.started_at = datetime.utcnow()
        if status in ("Completed", "Failed", "Skipped"):
            step.finished_at = datetime.utcnow()
        self.db.flush()

    def _progress(self) -> None:
        if not self.task:
            return
        steps = self.task.steps
        if not steps:
            return
        done = sum(1 for s in steps if s.status in ("Completed", "Skipped"))
        self.task.progress = int(done / len(steps) * 100)

    def _build_brief(self, question: str) -> str:
        """TASK-012 TaskBrief：把用户诉求固化为任务契约（goal/scope/acceptance/constraints）。

        Brief 是长程任务开始前的"共同理解"，供后续复核（Review）对照：
        任务要交付什么、以什么标准验收、边界在哪里。
        """
        return json.dumps({
            "goal": question[:200],
            "scope": "销售下降归因：ERP 订单 → CRM 客户 → 企业知识 → 归因分析 → 报告 → 行动任务",
            "acceptance": [
                "归因数字全部来自真实 SQL 计算，可复核",
                "输出含主因/次因/影响金额/建议动作",
                "创建销售任务属于写入动作，须人工审批后执行",
            ],
            "constraints": [
                "禁止编造任何数字",
                "Level 3 写入动作必须审批",
                "无 LLM key 时使用规则化报告兜底",
            ],
            "owner": self.user.name if self.user else "",
            "agent": self.agent.name if self.agent else "",
        }, ensure_ascii=False)

    def _advance_stage(self, step: AgentStep) -> None:
        """步骤完成后推进所属阶段：阶段内步骤全部完成 → 阶段 Completed + 写 Checkpoint。

        Checkpoint 是阶段产物摘要，供前端时间线投影展示（40-06 Stage/Checkpoint）。
        """
        if not self.task:
            return
        stage = next((s for s in self.task.stages if step.seq in s.step_list), None)
        if stage is None or stage.status in ("Completed", "Failed"):
            return
        if stage.status == "Pending":
            stage.status = "Running"
            stage.started_at = stage.started_at or datetime.utcnow()
        inner = [s for s in self.task.steps if s.seq in stage.step_list]
        if inner and all(s.status in ("Completed", "Skipped", "Failed") for s in inner):
            stage.status = "Completed"
            stage.finished_at = datetime.utcnow()
            stage.checkpoint = json.dumps(self._stage_checkpoint(stage), ensure_ascii=False)

    def _stage_checkpoint(self, stage: AgentStage) -> Dict[str, Any]:
        """阶段检查点摘要：从步骤 output/error 提炼可读产出。"""
        cp: Dict[str, Any] = {"stage": stage.name}
        if stage.kind == "data":
            cnt = 0
            for s in self.task.steps:
                if s.seq not in stage.step_list:
                    continue
                try:
                    out = json.loads(s.output_data or "{}")
                except (TypeError, ValueError):
                    out = {}
                if out.get("summary"):
                    cp[s.title] = out["summary"]
                elif out.get("rows"):
                    cnt += len(out["rows"])
            if cnt:
                cp["rows"] = cnt
        elif stage.kind == "analysis":
            for s in self.task.steps:
                if s.seq not in stage.step_list or s.status != "Completed":
                    continue
                try:
                    out = json.loads(s.output_data or "{}")
                except (TypeError, ValueError):
                    out = {}
                if out.get("top_drop_customer"):
                    top = out["top_drop_customer"]
                    cp["top_drop_customer"] = f"{top.get('name')}（贡献 {top.get('share')}%）"
                if s.kind == "report":
                    cp["report_chars"] = len(s.output_data or "")
        elif stage.kind == "approval":
            for s in self.task.steps:
                if s.seq not in stage.step_list:
                    continue
                if s.status == "Skipped":
                    cp["result"] = "跳过：未定位明确下滑客户"
                try:
                    out = json.loads(s.output_data or "{}")
                except (TypeError, ValueError):
                    out = {}
                if isinstance(out, dict) and out.get("approval_id"):
                    cp["approval_id"] = out["approval_id"]
        return cp

    def _fail(self, step: AgentStep, p: Dict[str, Any], err: str) -> List[Dict[str, Any]]:
        """步骤失败处理：标记失败、任务置 Failed，返回待推送的事件序列。

        TASK-008 要求每步都要记录执行状态与错误。工具调用失败时不能静默继续 ——
        否则报告会拿着残缺数据"一本正经地下结论"，比直接报错危险得多。
        """
        self._step(step, "Failed", error=err)
        self._progress()
        self.task.transition("Failed")
        self.task.error = f"第 {p['seq']} 步「{p['title']}」失败：{err}"
        self.task.finished_at = datetime.utcnow()
        if self.agent:
            self.agent.status = "Error"
        self.db.commit()

        return [
            {"event": "step", "data": {"seq": p["seq"], "title": p["title"],
                                       "status": "Failed", "error": err}},
            {"event": "error", "data": {"seq": p["seq"], "step": p["title"],
                                        "message": self.task.error}},
            {"event": "done", "data": {"task_id": self.task.id,
                                       "agent": self.agent.name if self.agent else "",
                                       "status": "Failed",
                                       "progress": self.task.progress}},
        ]

    # ---------- 主流程 ----------

    async def run(self, question: str,
                  existing: Optional[AgentTask] = None) -> AsyncIterator[Dict[str, Any]]:
        db = self.db
        # TASK-014：优先读 DB 中的 Logic 图（30-03），无图时回退代码 PLAN（兼容既有测试）
        graph_plan = None
        try:
            from .logic import get_active_plan
            graph_plan = get_active_plan(db, self.company_id,
                                         getattr(self.agent, "code", ""))
        except Exception:  # noqa: BLE001 表未就绪/seed 异常时回退代码链路
            graph_plan = None
        self.plan = graph_plan if graph_plan else _pick_plan(self.agent)

        # ---- 1. 创建或重置持久化任务（TASK-012：retry 复用同一任务重跑） ----
        if existing is not None:
            self.task = existing
            for s in list(existing.steps):
                db.delete(s)
            for s in list(existing.stages):
                db.delete(s)
            for e in db.query(AgentExecution).filter(
                    AgentExecution.task_id == existing.id).all():
                db.delete(e)
            existing.status = "Planning"
            existing.progress = 0
            existing.result = ""
            existing.error = ""
            existing.started_at = None
            existing.finished_at = None
            existing.retry_count += 1
            existing.brief = self._build_brief(question)
            db.flush()
        else:
            self.task = AgentTask(
                company_id=self.company_id,
                agent_id=self.agent.id,
                user_id=self.user.id if self.user else None,
                conversation_id=self.conversation_id,
                title=question[:200],
                input_text=question,
                mode="深度分析",
                status="Planning",
                priority=2,
                brief=self._build_brief(question),
            )
            db.add(self.task)
            db.flush()

        for p in self.plan:
            db.add(AgentStep(
                task_id=self.task.id, seq=p["seq"], title=p["title"], kind=p["kind"],
                depends_on=json.dumps(p.get("depends", [])), status="Pending",
            ))
        # TASK-012：按 STAGE_PLAN 创建阶段投影（Stage/Checkpoint）
        for st in STAGE_PLAN:
            db.add(AgentStage(
                task_id=self.task.id, seq=st["seq"], name=st["name"], kind=st["kind"],
                step_seqs=json.dumps(list(st["steps"])), status="Pending",
            ))
        db.flush()
        db.refresh(self.task)

        steps = {s.seq: s for s in self.task.steps}
        write_audit(db, action="task.create", actor_type="agent",
                    actor_id=self.agent.id, actor_name=self.agent.name,
                    company_id=self.company_id, target=question[:100],
                    detail={"task_id": self.task.id}, result="success")
        db.commit()

        yield {"event": "task", "data": {"task_id": self.task.id,
                                         "conversation_id": self.conversation_id,
                                         "plan": [{"seq": p["seq"], "title": p["title"]} for p in self.plan]}}

        self.task.transition("Running")
        self.task.started_at = datetime.utcnow()
        db.commit()

        # ---- 2. 逐步执行 ----
        collected: Dict[str, Any] = {}

        for p in self.plan[:5]:                       # 前 5 步自动执行，第 6 步需人工确认
            step = steps[p["seq"]]
            t0 = time.time()
            self._step(step, "Running")
            yield {"event": "step", "data": {"seq": p["seq"], "title": p["title"], "status": "Running"}}
            await asyncio.sleep(0.15)            # 让前端能看清过程推进

            if p["kind"] == "data" and p["tool"] == "query_monitoring_stations":
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

            elif p["kind"] == "data" and p["tool"] == "query_erp_orders":
                r = gw_execute(self.ctx, "query_erp_orders", {})
                collected["erp"] = r.get("result", {})
                ok = bool(r.get("ok"))
                err = "" if ok else (r.get("error") or r.get("reason") or "ERP 查询失败")
                self._log_exec(step, action="query_data", label="AI 正在查询 ERP 销售数据",
                               tool_name="query_erp_orders",
                               input_data={"sql_hint": "orders JOIN customers/products"},
                               output_data=r.get("result", {}).get("summary"),
                               status="Completed" if ok else "Failed", error=err, started=t0)
                yield {"event": "tool_result", "data": {"tool": "query_erp_orders",
                                                        "ok": ok, "error": err,
                                                        "summary": r.get("result", {}).get("summary")}}
                if not ok:
                    for ev in self._fail(step, p, err):
                        yield ev
                    return
                step.output_data = json.dumps(
                    {"summary": r.get("result", {}).get("summary")}, ensure_ascii=False)

            elif p["kind"] == "data" and p["tool"] == "query_crm_customers":
                r = gw_execute(self.ctx, "query_crm_customers", {"level": "A"})
                collected["crm"] = r.get("result", {})
                ok = bool(r.get("ok"))
                err = "" if ok else (r.get("error") or r.get("reason") or "CRM 查询失败")
                self._log_exec(step, action="query_data", label="AI 正在查询 CRM 客户信息",
                               tool_name="query_crm_customers", input_data={"level": "A"},
                               output_data={"rows": r.get("result", {}).get("rows", [])[:5]},
                               status="Completed" if ok else "Failed", error=err, started=t0)
                yield {"event": "tool_result", "data": {"tool": "query_crm_customers",
                                                        "ok": ok, "error": err,
                                                        "rows": r.get("result", {}).get("rows", [])[:5]}}
                if not ok:
                    for ev in self._fail(step, p, err):
                        yield ev
                    return
                step.output_data = json.dumps(
                    {"summary": r.get("result", {}).get("summary"),
                     "rows": r.get("result", {}).get("rows", [])[:5]}, ensure_ascii=False)

            elif p["kind"] == "knowledge":
                if getattr(self.agent, "code", "") == "inspection-analyst":
                    q = "巡检异常归因 辐射防护限值 设备健康度 工单处置"
                else:
                    q = "销售下降归因 大客户流失 价格下调 新客户"
                r = gw_execute(self.ctx, "search_knowledge", {"query": q, "top_k": 4})
                hits = r.get("result", {}).get("hits", [])
                collected["knowledge"] = hits
                self._log_exec(step, action="retrieve", label="AI 正在检索企业知识库",
                               tool_name="search_knowledge", input_data={"query": q},
                               output_data={"hits": [h["doc_title"] for h in hits]},
                               status="Completed", started=t0)
                for h in hits:
                    h["_step"] = p["seq"]
                yield {"event": "tool_result", "data": {"tool": "search_knowledge",
                                                        "ok": True,
                                                        "hits": [{"title": h["doc_title"],
                                                                  "score": h["score"]} for h in hits]}}

            elif p["kind"] == "tool" and p["tool"] == "analyze_inspection_anomaly":
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

            elif p["kind"] == "tool" and p["tool"] == "analyze_sales_drop":
                r = gw_execute(self.ctx, "analyze_sales_drop", {})
                collected["analysis"] = r.get("result", {})
                ok = bool(r.get("ok"))
                err = "" if ok else (r.get("error") or r.get("reason") or "归因分析失败")
                self._log_exec(step, action="call_tool", label="AI 正在按三维度做归因分析",
                               tool_name="analyze_sales_drop",
                               output_data=collected["analysis"],
                               status="Completed" if ok else "Failed", error=err, started=t0)
                yield {"event": "tool_result", "data": {"tool": "analyze_sales_drop",
                                                        "ok": ok, "error": err,
                                                        "overview": collected["analysis"].get("overview")}}
                if not ok:
                    for ev in self._fail(step, p, err):
                        yield ev
                    return
                step.output_data = json.dumps(collected["analysis"], ensure_ascii=False)

            elif p["kind"] == "report":
                report = self._render_report(collected)
                polished = await self._polish(report, collected)
                collected["report"] = polished
                self._log_exec(step, action="think", label="AI 正在生成归因结论与建议",
                               output_data={"chars": len(polished)}, status="Completed", started=t0)
                for ch in polished:
                    yield {"event": "token", "data": ch}
                    await asyncio.sleep(0.004)

            self._step(step, "Completed")
            self._progress()
            self._advance_stage(step)
            db.commit()
            yield {"event": "step", "data": {"seq": p["seq"], "title": p["title"], "status": "Completed"}}

        # ---- 3. 提出行动建议 → 落入审批回路（TASK-030 洞察转任务）----
        step6 = steps[6]
        self._step(step6, "Running")
        db.commit()
        yield {"event": "step", "data": {"seq": 6, "title": step6.title, "status": "Running"}}

        analysis = collected.get("analysis") or {}
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
            payload: Dict[str, Any] = {}
        if top:
            if getattr(self.agent, "code", "") == "inspection-analyst":
                self._advance_stage(step6)
                self._progress()
                db.commit()
                if self.task.status != "WaitingApproval":
                    self.task.transition("Completed")
                    self.task.finished_at = datetime.utcnow()
                    for st in self.task.stages:
                        if st.status != "Completed":
                            st.status = "Completed"
                            st.finished_at = datetime.utcnow()
                self.task.result = collected.get("report", "")
                if self.agent:
                    self.agent.total_tasks += 1
                    self.agent.today_tasks += 1
                    if self.task.status == "Completed":
                        self.agent.success_tasks += 1
                db.commit()
                yield {"event": "done", "data": {
                    "task_id": self.task.id,
                    "agent": self.agent.name if self.agent else "",
                    "status": self.task.status,
                    "progress": self.task.progress,
                }}
                return
            payload = {
                "title": f"{top['name']}流失挽回专项跟进",
                "customer_name": top["name"],
                "priority": "high",
                "owner": "李明",
                "due_date": self._due_date(),
                "detail": (f"{top['name']}（{top['level']} 类）订单额由 {top['prev_wan']} 万元降至 "
                           f"{top['curr_wan']} 万元，环比减少 {top['delta_wan']} 万元，"
                           f"占本月总降幅 {top['share']}%。按《大客户流失预警与挽回流程》"
                           f"二级响应要求：5 日内由销售负责人带队现场拜访并出具书面挽回方案。"),
                "_reason": f"该客户贡献了本月 {top['share']}% 的降幅，属归因结论中的主因。",
                "_evidence": {"customer": top, "overview": analysis.get("overview")},
                "_plan": {"action": "create_sales_task", "level": 3,
                          "steps": ["预约客户关键对接人", "现场拜访", "出具挽回方案", "30 日复盘"]},
            }
            r = gw_execute(self.ctx, "create_sales_task", payload)
            collected["approval"] = r
            self._log_exec(step6, action="call_tool", label="AI 请求创建销售跟进任务",
                           tool_name="create_sales_task", input_data=payload,
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
                    "title": "创建销售跟进任务",
                    "customer": top["name"],
                    "message": f"建议为 {top['name']} 创建流失挽回跟进任务，需你确认后执行。",
                }}
            else:
                self._step(step6, "Completed", error=str(r.get("error", "")))
                self._advance_stage(step6)
                yield {"event": "step", "data": {"seq": 6, "title": step6.title, "status": "Completed"}}
        else:
            self._step(step6, "Skipped", error="未定位到明确的下滑客户，跳过任务创建")
            self._advance_stage(step6)
            yield {"event": "step", "data": {"seq": 6, "title": step6.title, "status": "Skipped"}}

        self._progress()
        db.commit()

        # ---- 4. 收尾（TASK-012：状态机迁移 + 阶段投影完成） ----
        if self.task.status != "WaitingApproval":
            self.task.transition("Completed")
            self.task.finished_at = datetime.utcnow()
            # 确保所有阶段标记完成（若个别阶段因审批等待未收敛）
            for st in self.task.stages:
                if st.status != "Completed":
                    st.status = "Completed"
                    st.finished_at = datetime.utcnow()
        self.task.result = collected.get("report", "")

        if self.agent:
            self.agent.total_tasks += 1
            self.agent.today_tasks += 1
            if self.task.status == "Completed":
                self.agent.success_tasks += 1
        db.commit()

        yield {"event": "done", "data": {
            "task_id": self.task.id,
            "agent": self.agent.name if self.agent else "",
            "status": self.task.status,
            "progress": self.task.progress,
        }}

    # ---------- 报告生成 ----------

    def _render_report(self, c: Dict[str, Any]) -> str:
        if getattr(self.agent, "code", "") == "inspection-analyst":
            return self._render_inspection_report(c)
        a = c.get("analysis") or {}
        ov = a.get("overview") or {}
        prev, curr = ov.get("previous") or {}, ov.get("current") or {}
        months = a.get("months") or {}
        top = a.get("top_drop_customer")
        prices = a.get("price_moves") or []
        new_curr, new_prev = a.get("new_curr", 0), a.get("new_prev", 0)
        hits = c.get("knowledge") or []

        L: List[str] = []
        L.append(f"## 销售下降归因分析（{months.get('current','')} 对比 {months.get('previous','')}）\n")
        L.append("### 一、总体情况\n")
        L.append(f"- 订单量：**{prev.get('cnt','-')} → {curr.get('cnt','-')}** 笔（{ov.get('delta_cnt','-')} 笔）")
        L.append(f"- 销售额：**{prev.get('amt_wan','-')} → {curr.get('amt_wan','-')}** 万元"
                 f"（{ov.get('delta_amt_wan','-')} 万元，**{ov.get('pct','-')}%**）\n")

        L.append("### 二、归因结论\n")
        idx = 1
        if top:
            L.append(f"**主因 {idx}｜大客户订单骤降（贡献 {top['share']}%）**")
            L.append(f"{top['name']}（{top['level']} 类）订单额由 {top['prev_wan']} 万元降至 "
                     f"{top['curr_wan']} 万元，减少 **{top['delta_wan']} 万元**。")
            L.append("依据《销售异常归因标准指引》：单一客户贡献降幅超过 40%，判定为「大客户因素」。\n")
            idx += 1
        if prices:
            for pm in prices:
                L.append(f"**次因 {idx}｜{pm['product']}单价下调 {abs(pm['change_pct'])}%**")
                L.append(f"单价由 {pm['prev_price']:,.0f} 元降至 {pm['curr_price']:,.0f} 元。")
                L.append("依据《客户分级管理办法》：服务类单价下调超过 10% 须评估毛利影响并报财务备案。\n")
                idx += 1
        if new_prev and new_curr < new_prev:
            L.append(f"**次因 {idx}｜新客户首单断档**")
            L.append(f"新客户首单数由 {new_prev} 家降至 **{new_curr} 家**。")
            L.append("依据《新客户获取与转化管理规范》：连续两月低于目标值 50% 须启动获客渠道复盘。\n")
            idx += 1

        L.append("### 三、建议动作\n")
        n = 1
        if top:
            L.append(f"{n}. 【紧急】按《大客户流失预警与挽回流程》二级响应，5 日内由销售负责人"
                     f"带队拜访 {top['name']}，出具书面挽回方案。")
            n += 1
        if prices:
            L.append(f"{n}. 【本周】{prices[0]['product']}降价事项报财务备案，评估对整体毛利的影响。")
            n += 1
        if new_prev and new_curr < new_prev:
            L.append(f"{n}. 【本周】市场部启动获客渠道复盘，优先投入老客户转介绍渠道。")
            n += 1
        L.append(f"{n}. 【持续】将三大战略客户纳入周度监测，环比波动超 30% 自动预警。\n")

        if top:
            L.append("### 四、待确认\n")
            L.append(f"是否需要为 **{top['name']}** 创建流失挽回跟进任务？"
                     "该动作属于 Level 3，需你确认后才会真正写入 CRM。")

        if hits:
            L.append(format_citations(hits))
        return "\n".join(L)

    def _render_inspection_report(self, c: Dict[str, Any]) -> str:
        a = c.get("analysis") or {}
        ov = a.get("overview") or {}
        months = a.get("months") or {}
        top = a.get("top_alarm")
        alarms = a.get("alarm_dimension") or []
        deltas = a.get("delta_dimension") or []
        hits = c.get("knowledge") or []

        L: List[str] = []
        L.append(f"## 核电巡检异常归因分析（{months.get('current','')} 对比 {months.get('previous','')}）\n")
        L.append("### 一、总体情况\n")
        curr_ov = ov.get("current") or {}
        L.append(f"- 监测站总数：**{curr_ov.get('total_stations','-')}** 个")
        L.append(f"- 异常站点：**{ov.get('alarm_stations_curr','-')}** 个（辐射 / 温度 / 振动任一指标超限）\n")

        L.append("### 二、归因结论\n")
        idx = 1
        if top:
            L.append(f"**主因 {idx}｜{top['station_name']}（{top['station_code']}）{top['metric']}超限 {abs(top['over_pct'])}%**")
            L.append(f"位于{top['area']}，{top['metric']}读数为 {top['value']}{top['unit']}，"
                     f"阈值 {top['threshold']}{top['unit']}，超出 {abs(top['over_pct'])}%。")
            L.append("依据《辐射防护与监测限值标准》：超过限值须 15 分钟内完成初步归因并人工复核。\n")
            idx += 1
        for al in alarms[1:3]:
            L.append(f"**次因 {idx}｜{al['station_name']}（{al['station_code']}）{al['metric']}超限 {abs(al['over_pct'])}%**")
            L.append(f"{al['metric']}读数为 {al['value']}{al['unit']}，阈值 {al['threshold']}{al['unit']}。")
            L.append("依据《核电设备巡检异常归因标准》：单指标超限 ≥15% 生成工单，24 小时内处置。\n")
            idx += 1
        if deltas:
            for d in deltas:
                if d.get("change_pct") and d["change_pct"] >= 15 and d.get("station_code") != (top or {}).get("station_code"):
                    L.append(f"**次因 {idx}｜{d['station_code']} {d['metric']}环比上升 {d['change_pct']}%**")
                    L.append(f"由 {d['prev_value']}{d['unit']} 升至 {d['curr_value']}{d['unit']}，呈持续劣化趋势。")
                    L.append("依据《核电设备巡检异常归因标准》：持续劣化按时间维度归因，纳入工单处置。\n")
                    idx += 1

        L.append("### 三、建议动作\n")
        n = 1
        if top:
            L.append(f"{n}. 【紧急】对 {top['station_name']}（{top['station_code']}）按《辐射防护与监测限值标准》"
                     f"处置流程执行：15 分钟归因 → 人工复核 → 2 小时内出具工单。")
            n += 1
        for al in alarms[1:3]:
            L.append(f"{n}. 【24 小时】处置 {al['station_name']}（{al['station_code']}）的 {al['metric']} 超限，"
                     f"完成现场确认与消缺。")
            n += 1
        L.append(f"{n}. 【持续】将全部监测站纳入日巡检重点，健康度低于 60 自动升级预警。\n")

        if top:
            L.append("### 四、待确认\n")
            L.append(f"是否需要为 **{top['station_name']}**（{top['station_code']}）创建巡检处置工单？"
                     "该动作属于 Level 3，需你确认后才会真正写入工单系统。")

        if hits:
            L.append(format_citations(hits))
        return "\n".join(L)

    async def _polish(self, report: str, c: Dict[str, Any]) -> str:
        """有 LLM key 时润色，无 key 直接返回规则化报告（离线兜底）。"""
        from .config import settings
        if not settings.llm_enabled:
            return report
        try:
            from openai import OpenAI
            cli = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
            resp = cli.chat.completions.create(
                model=settings.model_name,
                messages=[
                    {"role": "system", "content":
                     "你是资深销售分析师。下面给出的是基于真实数据算出的归因报告，"
                     "请在不改动任何数字的前提下润色表达，使其更简洁有力、适合管理层阅读。"
                     "保留 Markdown 结构与小标题，不要新增未经数据支持的结论。"},
                    {"role": "user", "content": report},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content or report
        except Exception:
            return report

    @staticmethod
    def _due_date() -> str:
        d = datetime.utcnow()
        return f"{d.year}-{d.month:02d}-{(min(d.day + 7, 28)):02d}"
