"""FastAPI 路由汇总。

GET  /api/overview          企业总览（KPI + 洞察 + 数据源）
GET  /api/agents            AI 员工列表
GET  /api/employees         AI 员工档案列表
GET  /api/employees/{name}  单个 AI 员工完整档案
GET  /api/tasks             任务列表（可传 category）
POST /api/tasks/confirm     确认任务（触发写入型 Skill）
GET  /api/activities        最近活动
GET  /api/workbench         AI 工作台（历史对话 + 步骤 + 图表）
GET  /api/knowledge         企业知识资产中心
GET  /api/scenes            业务场景中心
POST /api/chat-stream       对话流（SSE）
"""
from __future__ import annotations

from typing import AsyncIterator, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .workbench import get_workbench_payload
from .employees import (
    get_employee_payload, list_employee_names,
    create_employee, delete_employee,
)
from .dashboard import router as dashboard_router
from .knowledge import router as knowledge_router
from .scenes import get_scenes_payload
from .data_sources import router as data_sources_router
from .data_assets import router as data_assets_router
from .admin import router as admin_router
from .auth_api import router as auth_router
from .org import router as org_router
from .mainline_api import router as mainline_router, router_tasks
from .approvals import router as approvals_router, router_sales
from .ontology_api import router as ontology_router
from .object_actions import router as object_actions_router
from .health import router as health_router
from .logic_api import router as logic_router
from .pages_api import router as pages_router
from .assets_api import router as assets_router
from .release_api import router as release_router
from ..agents import orchestrator
from ..agents.coordinator import coordinator
from ..config import settings
from ..auth import get_current_user, require_perm
from ..db import SessionLocal, get_db
from ..models import User
from ..models_ai import Agent
from ..skills import REGISTRY, WRITE_SKILLS


router = APIRouter(prefix="/api")

# 数据源管理（独立子路由，自带前缀 /api/data-sources）
router.include_router(data_sources_router)
# 数据资产（图谱 10-01/10-02，自带前缀 /api/data-assets）
router.include_router(data_assets_router)
# 管理后台（数据管理 / 系统集成 / 权限 / 模型 / 日志 / 设置）
router.include_router(admin_router)
# 认证（登录 / 退出 / 用户信息）
router.include_router(auth_router)
# 组织与权限（企业 / 部门 / 用户 / 角色 / 权限）
router.include_router(org_router)
# 主线执行（SSE）与任务中心
router.include_router(mainline_router)
router.include_router(router_tasks)
# 审批中心与销售跟进任务
router.include_router(approvals_router)
router.include_router(router_sales)
# 本体图探索（图谱 20-04）
router.include_router(ontology_router)
# 对象 AIP/Action 嵌入（图谱 40-04）
router.include_router(object_actions_router)
# 系统健康检查（图谱 90-01）
router.include_router(health_router)
# Logic 决策编排画布（30-03）
router.include_router(logic_router)
# 低代码页面（40-03）
router.include_router(pages_router)
# 资产装配（50 全系：Bundle/Registry/Resolver/Installation/Plugin）
router.include_router(assets_router)
# 交付发布与边缘协同（70-03 Hub-Spoke / 80-01 Release+Channel+SBOM+签名 / 80-02 Promotion+Recall）
router.include_router(release_router)


# 企业总览（独立子路由，自带鉴权与真实统计）
router.include_router(dashboard_router)


# ---------- 各子页面 ----------

@router.get("/workbench")
def workbench():
    """AI 工作台：历史对话 + 当前会话步骤 + 图表数据"""
    return get_workbench_payload()


@router.get("/employees")
def employees_list():
    """AI 员工档案列表（只返回摘要，详情走 /employees/{name}）"""
    items = []
    for name in list_employee_names():
        e = get_employee_payload(name)
        if e:
            items.append({
                "name": e["name"], "role": e["role"], "avatar": e["avatar"],
                "color": e["color"], "status": e["status"],
            })
    return {"items": items}


@router.get("/employees/{name}")
def employee_detail(name: str):
    """单个 AI 员工完整档案：标签 / 绩效 / 日志 / 能力 / 权限"""
    e = get_employee_payload(name)
    if not e:
        raise HTTPException(status_code=404, detail=f"employee '{name}' not found")
    return e


class CreateEmployeeReq(BaseModel):
    name: str
    role: str = ""
    avatar: str = "🤖"
    color: str = "from-violet-500 to-blue-500"
    skills: List[str] = []
    capabilities: List[str] = []
    permissions: List[dict] = []


@router.post("/employees")
def create_employee_api(req: CreateEmployeeReq,
                        user: User = Depends(require_perm("employee:manage")),
                        db=Depends(get_db)):
    res = create_employee(req.dict(), db=db, company_id=user.company_id)
    if "error" in res:
        raise HTTPException(status_code=409, detail=res["error"])
    return res


@router.delete("/employees/{name}")
def delete_employee_api(name: str,
                        user: User = Depends(require_perm("employee:manage")),
                        db=Depends(get_db)):
    res = delete_employee(name, db=db, company_id=user.company_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


# 企业知识（总览 / 知识库 / 文档 / 检索）— 独立子路由，自带前缀 /api/knowledge
router.include_router(knowledge_router)


@router.get("/scenes")
def scenes():
    """业务场景中心：L1-L4 阶段 + 场景卡片"""
    return get_scenes_payload()


class MetaResp(BaseModel):
    system_name: str
    version: str
    llm_enabled: bool
    llm_mode: str
    embedding_enabled: bool
    ontology_mode: str
    agent_count: int
    skill_count: int
    multi_agent: bool


class SkillInfo(BaseModel):
    name: str
    description: str
    write: bool
    param_count: int


@router.get("/meta")
def meta():
    """系统运行态：区分「产品态(真LLM) / 演示态(mock)」，以及本体持久化模式。

    用于前端智能化中心展示当前能力，也作为对外演示的透明说明。
    """
    db = SessionLocal()
    try:
        agent_count = db.query(Agent).filter(
            Agent.status.in_(("Published", "Running", "Testing"))
        ).count()
    finally:
        db.close()
    return MetaResp(
        system_name=settings.system_name,
        version=settings.version,
        llm_enabled=settings.llm_enabled,
        llm_mode="产品态(真LLM)" if settings.llm_enabled else "演示态(mock)",
        embedding_enabled=settings.embedding_enabled,
        ontology_mode="持久化(DB)",
        agent_count=agent_count,
        skill_count=len(REGISTRY),
        multi_agent=True,
    )


@router.get("/skills")
def skills_list():
    """Skills 注册表清单（Claude Skills 风格的工具集）。

    写入型 Skill 标记 write=True，触发人类确认回路（HITL）。
    用于前端智能化中心展示当前可调用的工具能力。
    """
    items = []
    for name, s in REGISTRY.items():
        items.append(SkillInfo(
            name=name,
            description=s.description,
            write=name in WRITE_SKILLS,
            param_count=len(s.parameters.get("properties", {}) or {}),
        ))
    return {"items": items}


# ---------- 对话流（SSE） ----------

class ChatReq(BaseModel):
    message: str
    history: List[dict] = []


@router.post("/chat-stream")
async def chat_stream(req: ChatReq):
    async def gen() -> AsyncIterator[dict]:
        async for ev in orchestrator.chat(req.message, req.history):
            yield ev
    return EventSourceResponse(gen())


class OrchestrateReq(BaseModel):
    message: str


@router.post("/orchestrate")
async def orchestrate(req: OrchestrateReq):
    """多 Agent 会诊：把问题分发给相关专家 Agent，流式回传 plan / agent_view / token / done。

    与 chat-stream 保持一致的鉴权策略（EventSource 无法带头，走同源 fetch + Bearer），
    这里不强制 Depends(get_current_user)，company_id 暂传 None（名册按 status 取全部可执行 Agent）。
    """
    async def gen() -> AsyncIterator[dict]:
        async for ev in coordinator.run(req.message, None):
            yield ev
    return EventSourceResponse(gen())
