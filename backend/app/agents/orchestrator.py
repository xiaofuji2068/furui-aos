"""AOP / AIP 风格的编排引擎。

工作流：
1. 接收人类意图（自然语言）
2. 路由到合适的 AI 员工（Agent）
3. 该 Agent 的 Skills 作为工具集，调用 LLM（支持 function calling）
4. LLM 选择 Skill → 后端执行 → 结果回灌 LLM → 生成自然语言答案
5. 写入型 Skill 必须经过"人类确认"回路
6. 全过程用 SSE 流式上报给前端
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI

from ..config import settings
from ..skills import REGISTRY, WRITE_SKILLS, execute_skill, openai_tools
from . import employees


# ---------- 内存版"任务 / 待办 / 活动流" ----------

@dataclass
class TaskItem:
    id: str
    title: str
    source_agent: str
    category: str                         # "待确认" / "已完成" / "进行中"
    description: str
    created_at: str
    urgency: str = "中"                   # 高 / 中 / 低
    payload: Dict[str, Any] = field(default_factory=dict)   # 待确认时的待执行 Skill/参数


@dataclass
class ActivityItem:
    id: str
    actor: str               # AI 员工名
    text: str
    timestamp: str


_TASKS: List[TaskItem] = []
_ACTIVITIES: List[ActivityItem] = []


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _seed_initial_state():
    """首页截图里的两条『待确认』和若干最近活动。"""
    if _TASKS:
        return
    _TASKS.extend([
        TaskItem(
            id="T-2026-0001",
            title="设备维修方案确认",
            source_agent="设备运维工程师",
            category="待确认",
            description="3 号监测站异常，AI 已生成维修方案，发起人：设备运维工程师",
            created_at=_now(),
            urgency="高",
            payload={
                "skill": "create_workorder",
                "args": {"title": "3号监测站红外测温异常 - 现场检测", "priority": "high"},
            },
        ),
        TaskItem(
            id="T-2026-0002",
            title="采购建议确认",
            source_agent="销售分析师",
            category="待确认",
            description="AI 建议采购某型号传感器 50 个，发起人：销售分析师",
            created_at=_now(),
            urgency="中",
            payload={
                "skill": "send_notification",
                "args": {"channel": "dingtalk", "message": "建议采购型号 X 传感器 50 个"},
            },
        ),
        TaskItem(
            id="T-2026-0003",
            title="销售数据分级报告",
            source_agent="销售分析师",
            category="已完成",
            description="完成了销售数据分析报告",
            created_at=_now(),
            urgency="中",
        ),
        TaskItem(
            id="T-2026-0004",
            title="设备告警",
            source_agent="设备运维工程师",
            category="已完成",
            description="处理了设备告警",
            created_at=_now(),
            urgency="中",
        ),
        TaskItem(
            id="T-2026-0005",
            title="设备维护手册",
            source_agent="知识助手",
            category="已完成",
            description="更新了《设备维护手册》",
            created_at=_now(),
            urgency="中",
        ),
        TaskItem(
            id="T-2026-0006",
            title="资金流动分析",
            source_agent="财务助手",
            category="已完成",
            description="生成了资金流动分析报告",
            created_at=_now(),
            urgency="中",
        ),
        TaskItem(
            id="T-2026-0007",
            title="新 AI 员工",
            source_agent="系统管理员",
            category="已完成",
            description="创建了新的 AI 员工：巡检助手",
            created_at=_now(),
            urgency="中",
        ),
    ])
    _ACTIVITIES.extend([
        ActivityItem(id=str(uuid.uuid4()), actor="销售分析师", text=f"完成了销售数据分析报告 · {_now()}", timestamp=_now()),
        ActivityItem(id=str(uuid.uuid4()), actor="设备运维工程师", text=f"处理了设备告警 · {_now()}", timestamp=_now()),
        ActivityItem(id=str(uuid.uuid4()), actor="知识助手",     text=f"更新了《设备维护手册》 · {_now()}", timestamp=_now()),
        ActivityItem(id=str(uuid.uuid4()), actor="财务助手",     text=f"生成了资金流动分析报告 · {_now()}", timestamp=_now()),
        ActivityItem(id=str(uuid.uuid4()), actor="系统管理员",   text=f"创建了新的 AI 员工：巡检助手 · {_now()}", timestamp=_now()),
    ])


_seed_initial_state()


def list_tasks(category: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    for t in _TASKS:
        if category and t.category != category:
            continue
        out.append({
            "id": t.id, "title": t.title, "source_agent": t.source_agent,
            "category": t.category, "description": t.description,
            "created_at": t.created_at, "urgency": t.urgency,
        })
    return out


def confirm_task(task_id: str) -> Dict[str, Any]:
    for t in _TASKS:
        if t.id == task_id:
            if t.payload and t.payload.get("skill"):
                # 真正执行那条写入操作
                args = t.payload.get("args", {})
                res = execute_skill(t.payload["skill"], **args)
            else:
                res = {"ok": True, "result": "no-op"}
            t.category = "已完成"
            t.description += " · 已确认"
            _ACTIVITIES.append(ActivityItem(
                id=str(uuid.uuid4()), actor=t.source_agent, text=f"已确认执行：{t.title}", timestamp=_now()
            ))
            return {"task_id": task_id, "executed": res, "task": {
                "id": t.id, "title": t.title, "source_agent": t.source_agent,
                "category": t.category, "description": t.description,
                "created_at": t.created_at, "urgency": t.urgency,
            }}
    return {"error": f"task {task_id} not found"}


def list_activities(limit: int = 10) -> List[Dict[str, Any]]:
    return [{"id": a.id, "actor": a.actor, "text": a.text, "timestamp": a.timestamp}
            for a in _ACTIVITIES[-limit:]]


# ---------- 编排引擎 ----------

class Orchestrator:
    """意图路由 + 工具调用 + 流式输出。"""

    def __init__(self, client: Optional[AsyncOpenAI] = None):
        self.client = client or AsyncOpenAI(
            api_key=settings.openai_api_key or "sk-placeholder",
            base_url=settings.openai_base_url,
        )

    # ---- 路由 ----

    def route(self, user_msg: str) -> Agent:
        """轻量规则路由 — 真实环境可换成 embedding + LLM 分类。"""
        text = user_msg
        if any(k in text for k in ["销售", "订单", "客户", "区域", "华东", "增长", "下滑", "复盘"]):
            return employees.SALES_ANALYST
        if any(k in text for k in ["现金流", "资金", "利润", "财务", "预算", "报销"]):
            return employees.FINANCE_ASSISTANT
        if any(k in text for k in ["设备", "故障", "工单", "运维", "监测", "3号"]):
            return employees.OPS_ENGINEER
        if any(k in text for k in ["知识", "手册", "制度", "流程", "什么是", "怎么"]):
            return employees.KNOWLEDGE_ASSISTANT
        return employees.SALES_ANALYST  # 默认

    # ---- 主对话流（SSE）----

    async def chat(self, user_msg: str, history: List[Dict[str, str]] = None) -> AsyncIterator[Dict[str, Any]]:
        history = history or []
        agent = self.route(user_msg)
        # 上报被路由的 agent
        # 注意：sse_starlette 2.1.3 对 data 直接 str()，dict 会变成 Python repr（非法 JSON），
        # 所以结构化事件的 data 必须预先 json.dumps 成字符串（与 coordinator 一致）。
        yield {"event": "agent", "data": json.dumps({"name": agent.name, "avatar": agent.avatar, "role": agent.role, "color": agent.color}, ensure_ascii=False)}

        if not settings.llm_enabled:
            async for piece in self._mock_chat(agent, user_msg):
                yield piece
            return

        tools = openai_tools(agent.skills)
        messages = [{"role": "system", "content": agent.system_prompt},
                    *history,
                    {"role": "user", "content": user_msg}]

        # 多轮 function calling
        for turn in range(5):
            stream = await self.client.chat.completions.create(
                model=settings.model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True,
            )

            collected = {"content": "", "tool_calls": []}
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    collected["content"] += delta.content
                    yield {"event": "token", "data": delta.content}
                if delta and delta.tool_calls:
                    # 累积 function calling
                    for tc in delta.tool_calls:
                        while len(collected["tool_calls"]) <= tc.index:
                            collected["tool_calls"].append({"id": "", "function": {"name": "", "arguments": ""}})
                        if tc.id:
                            collected["tool_calls"][tc.index]["id"] = tc.id
                        if tc.function and tc.function.name:
                            collected["tool_calls"][tc.index]["function"]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            collected["tool_calls"][tc.index]["function"]["arguments"] += tc.function.arguments

            # 拼接 assistant 消息
            assistant_msg = {"role": "assistant", "content": collected["content"]}
            if collected["tool_calls"]:
                assistant_msg["tool_calls"] = [
                    {"id": t["id"], "type": "function",
                     "function": t["function"]}
                    for t in collected["tool_calls"] if t["function"]["name"]
                ]
                # 把 arguments 字符串变 dict
                import json as _json
                for t in assistant_msg["tool_calls"]:
                    try:
                        t["function"]["arguments"] = _json.loads(t["function"]["arguments"]) if isinstance(t["function"]["arguments"], str) else t["function"]["arguments"]
                    except Exception:
                        t["function"]["arguments"] = {}
            messages.append(assistant_msg)

            if not collected["tool_calls"]:
                # 文字回答已经完整输出
                try:
                    from ..api.health import mark_llm_call
                    mark_llm_call(True, "对话完成")
                except Exception:  # noqa: BLE001
                    pass
                yield {"event": "done", "data": json.dumps({"agent": agent.name}, ensure_ascii=False)}
                return

            # 执行工具 — 写入型需要人类确认
            for tc in collected["tool_calls"]:
                fname = tc["function"]["name"]
                fargs = tc["function"]["arguments"] if isinstance(tc["function"]["arguments"], dict) else {}
                yield {"event": "tool_call", "data": json.dumps({"name": fname, "args": fargs}, ensure_ascii=False)}

                if fname in WRITE_SKILLS:
                    # 不直接执行 — 创建待确认任务
                    task_id = f"T-{uuid.uuid4().hex[:8].upper()}"
                    desc = f"由 {agent.name} 发起：{fname}({json.dumps(fargs, ensure_ascii=False)})"
                    _TASKS.insert(0, TaskItem(
                        id=task_id,
                        title=f"{fname} 待你确认",
                        source_agent=agent.name,
                        category="待确认",
                        description=desc,
                        created_at=_now(),
                        urgency="高" if fname == "create_workorder" else "中",
                        payload={"skill": fname, "args": fargs},
                    ))
                    _ACTIVITIES.append(ActivityItem(
                        id=str(uuid.uuid4()), actor=agent.name,
                        text=f"请求人类确认：{fname}",
                        timestamp=_now(),
                    ))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps({
                            "status": "awaiting_human_confirmation",
                            "task_id": task_id,
                            "message": "该操作需人类确认后才执行，请向用户说明并等待确认",
                        }, ensure_ascii=False),
                    })
                    yield {"event": "pending", "data": json.dumps({"task_id": task_id, "skill": fname, "args": fargs}, ensure_ascii=False)}
                else:
                    res = execute_skill(fname, **fargs)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(res, ensure_ascii=False, default=str),
                    })
                    yield {"event": "tool_result", "data": json.dumps(res, ensure_ascii=False, default=str)}

            # 继续下一轮让 LLM 总结
        try:
            from ..api.health import mark_llm_call
            mark_llm_call(True, "工具调用链完成")
        except Exception:  # noqa: BLE001
            pass
        yield {"event": "done", "data": json.dumps({"agent": agent.name}, ensure_ascii=False)}

    # ---- 没有 LLM key 时的演示模式 ----

    async def _mock_chat(self, agent, user_msg):
        text = user_msg
        if "销售" in text or "订单" in text:
            reply = (
                "我已经分析完华东区域最新数据：\n"
                "- 本周订单 5 笔，总金额 ≈ ¥111,800\n"
                "- 华东区域占比由上周 62% 下滑到 41%，环比 **-18%**\n"
                "- 主要受影响：A 产品（SKU-A12）下滑 32%\n\n"
                "建议：通知客户经理回访 CUS-001，并通知市场部调整促销方案。需要我帮你起草通知吗？"
            )
        elif "设备" in text or "工单" in text:
            reply = (
                "现场信号：3 号监测站近 24h 报 3 次温度预警。\n"
                "建议派单：今天下午 15:00 现场检测，备件清单已调出。\n"
                "需要创建工单并通知现场工程师吗？"
            )
        elif "现金流" in text or "财务" in text:
            reply = (
                "本周经营性现金流 +¥2.18M，同比 +12%。\n"
                "应收账款回款率 78%（低于上月的 84%），建议催收 CUS-001 / CUS-002。\n"
                "需要我草拟一份客户催收通知吗？"
            )
        elif "知识" in text or "手册" in text:
            reply = (
                "已检索到《设备维护手册》：3 号监测站每周一次红外测温，备件更换周期 90 天。\n"
                "是否要我整理成一份新的 SOP？"
            )
        else:
            reply = (
                f"我已经基于 {agent.name} 的视角理解了你的问题。请告诉我你想分析哪一类数据，"
                "或者直接说『分析华东销售』『查一下 3 号监测站』『拉一份现金流报告』。"
            )

        for ch in reply:
            yield {"event": "token", "data": ch}
            await asyncio.sleep(0.01)
        yield {"event": "done", "data": json.dumps({"agent": agent.name}, ensure_ascii=False)}


# 单例
orchestrator = Orchestrator()
