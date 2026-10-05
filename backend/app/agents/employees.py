"""AI 员工定义 — 每个员工 = 系统提示词 + 专属 Skill 集合 + 头像/状态。

参考 Claude Skills：员工能力由 Skills 驱动，而不是写死在长 prompt 里。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..skills import REGISTRY


@dataclass
class Agent:
    name: str
    role: str
    avatar: str                          # emoji 头像
    color: str                           # 卡片配色
    system_prompt: str
    skills: List[str] = field(default_factory=list)
    status: str = "idle"                 # idle / working / waiting_human / error
    current_task: str = ""
    progress: int = 0                    # 0-100

    def has_skill(self, name: str) -> bool:
        return name in self.skills


# 演示数据完全对应 UI 截图（销售分析师、财务助手、设备运维工程师、知识助手）
SALES_ANALYST = Agent(
    name="销售分析师",
    role="分析华东区域销售数据",
    avatar="👨‍💼",
    color="from-rose-500 to-orange-500",
    system_prompt=(
        "你是「销售分析师」，傅瑞科技的 AI 员工之一。\n"
        "你的职责是分析销售订单，识别异常下滑、潜力客户，给出建议。\n"
        "回答要简洁、有结论、会引用具体数字（订单号、金额、区域）。\n"
        "如需写入操作（建工单、发通知、写报告），先说明计划，由人类确认。"
    ),
    skills=["query_orders", "query_products", "get_dashboard", "draft_report", "send_notification"],
    status="working",
    current_task="分析华东区域销售下降原因",
    progress=75,
)

FINANCE_ASSISTANT = Agent(
    name="财务助手",
    role="生成资金流动分析报告",
    avatar="👩‍💼",
    color="from-emerald-500 to-teal-500",
    system_prompt=(
        "你是「财务助手」，傅瑞科技的 AI 员工之一。\n"
        "你负责现金流分析、损益回顾、预算差异说明。\n"
        "输出需要带具体数字、对比期、口径说明。\n"
        "遇到需要走写入动作（发通知、写报告）的需求，先给出方案，由人类确认。"
    ),
    skills=["query_orders", "get_dashboard", "draft_report", "send_notification"],
    status="idle",
    current_task="暂无任务",
    progress=0,
)

OPS_ENGINEER = Agent(
    name="设备运维工程师",
    role="处理设备告警",
    avatar="👷",
    color="from-sky-500 to-blue-500",
    system_prompt=(
        "你是「设备运维工程师」，傅瑞科技的 AI 员工之一。\n"
        "你负责设备状态监测、故障排查、工单创建与派发。\n"
        "在创建工单或发送通知前，必须给出依据与计划，由人类确认。"
    ),
    skills=["query_devices", "query_workorders", "query_kb", "create_workorder", "send_notification"],
    status="working",
    current_task="分析3号监测站报警原因",
    progress=60,
)

KNOWLEDGE_ASSISTANT = Agent(
    name="知识助手",
    role="整理企业知识",
    avatar="🧑‍🏫",
    color="from-violet-500 to-purple-500",
    system_prompt=(
        "你是「知识助手」，傅瑞科技的 AI 员工之一。\n"
        "你负责从企业知识库（销售/财务/运维/制度文档）里检索与归纳。\n"
        "回答时附上引用条目，让用户能继续展开。"
    ),
    skills=["query_kb", "query_devices", "query_workorders", "get_dashboard"],
    status="working",
    current_task="更新设备维护手册",
    progress=40,
)

REGISTRY_AGENTS: Dict[str, Agent] = {
    a.name: a for a in [SALES_ANALYST, FINANCE_ASSISTANT, OPS_ENGINEER, KNOWLEDGE_ASSISTANT]
}


def list_agents() -> List[Agent]:
    return list(REGISTRY_AGENTS.values())


def get_agent(name: str) -> Agent | None:
    return REGISTRY_AGENTS.get(name)


def register_agent(
    name: str,
    role: str,
    avatar: str = "🤖",
    color: str = "from-slate-500 to-slate-600",
    system_prompt: str = "",
    skills: List[str] | None = None,
    status: str = "idle",
    current_task: str = "",
    progress: int = 0,
) -> bool:
    """创建向导调用：把新 AI 员工同步进运行时注册表，使 /api/agents 列表可见。"""
    if name in REGISTRY_AGENTS:
        return False
    REGISTRY_AGENTS[name] = Agent(
        name=name,
        role=role,
        avatar=avatar,
        color=color,
        system_prompt=system_prompt or f"你是「{name}」，傅瑞科技的 AI 员工之一。",
        skills=skills or ["get_dashboard"],
        status=status,
        current_task=current_task,
        progress=progress,
    )
    return True
