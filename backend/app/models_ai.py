"""企业 AI 核心对象 — AI 域 ORM 模型（TASK-004 / TASK-005）。

与组织域（models.py）分离的原因：组织域管「谁在用它」，AI 域管「AI 在做什么」，
两者演进节奏不同，混在一个文件里会让 models.py 迅速膨胀到不可维护。

覆盖清单 TASK-004 要求的 AI 域对象：
  AIApplication / BusinessScenario
  Agent / AgentSkill / AgentTask / AgentStep / AgentExecution
  KnowledgeBase / KnowledgeDocument / KnowledgeChunk
  DataSource / DataConnection
  Tool / ToolExecution
  Approval / ApprovalRule
  Notification / AuditLog

设计铁律（对应清单 TASK-003 验收标准「AI Agent 不能直接拥有无限权限」）：
  每个 Agent 必须显式配置四类白名单 —— 知识 / 数据 / 工具 / 操作。
  白名单为空即视为无权限，不存在「默认放行」。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.utcnow()


def _jd(obj: Any) -> str:
    """JSON 序列化（统一 ensure_ascii=False，保证中文可读）。"""
    return json.dumps(obj or [], ensure_ascii=False)


# ==================== 业务场景域 ====================

class AIApplication(Base):
    """AI 应用 — 场景的上层归属（如「核应急管理智能系统」）。"""
    __tablename__ = "ai_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(20), default="planning")  # planning/building/testing/running/paused/archived
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


class BusinessScenario(Base):
    """业务场景（TASK-026）— 问题驱动，关联 Agent / 知识 / 数据 / 工具。"""
    __tablename__ = "business_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    application_id: Mapped[int | None] = mapped_column(ForeignKey("ai_applications.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="")
    owner: Mapped[str] = mapped_column(String(64), default="")
    department: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    problem: Mapped[str] = mapped_column(Text, default="")       # 要解决的问题
    acceptance: Mapped[str] = mapped_column(Text, default="")    # 验收标准
    stage: Mapped[str] = mapped_column(String(40), default="调研")  # TASK-027 建设阶段
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="规划中")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


# ==================== Agent 域（TASK-005） ====================

AGENT_STATUS = ("Draft", "Testing", "Published", "Running", "Paused", "Error", "Archived")


class Agent(Base):
    """AI 员工 — 系统的核心执行单元。

    权限模型（清单硬性验收标准）：
      allowed_knowledge_ids  允许访问的知识库
      allowed_datasource_ids 允许查询的数据源
      allowed_tool_ids       允许调用的工具
      allowed_actions        允许执行的操作（read / write / approve…）
    四者均为白名单，空 = 无权限。
    """
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    avatar: Mapped[str] = mapped_column(String(16), default="")   # emoji 或首字母
    agent_type: Mapped[str] = mapped_column(String(40), default="assistant")  # assistant/analyst/operator
    position: Mapped[str] = mapped_column(String(80), default="")  # 岗位，TASK-024 第一步
    color: Mapped[str] = mapped_column(String(64), default="")     # 卡片主题色（Tailwind 渐变类）
    capabilities: Mapped[str] = mapped_column(Text, default="[]")  # 能力标签 JSON 数组

    status: Mapped[str] = mapped_column(String(20), default="Draft")

    # 模型配置
    model_name: Mapped[str] = mapped_column(String(80), default="deepseek-chat")
    temperature: Mapped[float] = mapped_column(default=0.3)

    # 人格与职责（TASK-024 第二步）
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    goal: Mapped[str] = mapped_column(Text, default="")        # 工作目标
    rules: Mapped[str] = mapped_column(Text, default="")       # 工作规则

    # 四类权限白名单（TASK-003 验收标准）
    allowed_knowledge_ids: Mapped[str] = mapped_column(Text, default="[]")
    allowed_datasource_ids: Mapped[str] = mapped_column(Text, default="[]")
    allowed_tool_ids: Mapped[str] = mapped_column(Text, default="[]")
    allowed_actions: Mapped[str] = mapped_column(Text, default="[]")

    # 审批规则（TASK-021 四级动作分类）
    approval_level: Mapped[int] = mapped_column(Integer, default=3)  # 1自动 2通知后执行 3必须审批 4禁止

    # 运行指标（TASK-042/043）
    total_tasks: Mapped[int] = mapped_column(Integer, default=0)
    success_tasks: Mapped[int] = mapped_column(Integer, default=0)
    today_tasks: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"), onupdate=_utcnow)

    skills: Mapped[List["AgentSkill"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    tasks: Mapped[List["AgentTask"]] = relationship(back_populates="agent")

    # ---- 白名单读取 ----

    @property
    def knowledge_ids(self) -> List[int]:
        return json.loads(self.allowed_knowledge_ids or "[]")

    @property
    def datasource_ids(self) -> List[int]:
        return json.loads(self.allowed_datasource_ids or "[]")

    @property
    def tool_ids(self) -> List[int]:
        return json.loads(self.allowed_tool_ids or "[]")

    @property
    def actions(self) -> List[str]:
        return json.loads(self.allowed_actions or "[]")

    @property
    def success_rate(self) -> float:
        if not self.total_tasks:
            return 0.0
        return round(self.success_tasks / self.total_tasks * 100, 1)

    def can(self, action: str) -> bool:
        """Agent 是否具备某项操作权限。"""
        return action in self.actions


class AgentSkill(Base):
    """Agent 技能绑定（清单 AgentSkill 对象）— 决定该 Agent 能用哪些工具。"""
    __tablename__ = "agent_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    skill_name: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True)

    agent: Mapped[Agent] = relationship(back_populates="skills")


# ==================== 任务域（TASK-009 / TASK-010 / TASK-012） ====================

# TASK-012 长程任务状态机（图谱 40-06）
# Pending → Planning → Running → WaitingApproval / InReview → Completed
#                              ↘ Failed        ↘ Returned →（可再次 Running）
TASK_STATUS = ("Pending", "Planning", "Running", "WaitingApproval", "InReview", "Returned", "Completed", "Failed", "Cancelled")
STEP_STATUS = ("Pending", "Running", "Completed", "Failed", "Skipped")
STAGE_STATUS = ("Pending", "Running", "Completed", "Failed")
REVIEW_DECISION = ("approve", "return")

# 显式迁移白名单：key=当前状态，value=允许迁移到的状态集合（P05 Explicit）
TASK_TRANSITIONS: Dict[str, tuple[str, ...]] = {
    "Pending": ("Planning", "Failed", "Cancelled"),
    "Planning": ("Running", "Failed", "Cancelled"),
    "Running": ("WaitingApproval", "InReview", "Completed", "Failed"),
    "WaitingApproval": ("InReview", "Completed", "Returned", "Failed"),
    "InReview": ("Completed", "Returned"),
    "Returned": ("Running", "Cancelled"),   # 退回后可重新执行（retry）
    "Completed": (),
    "Failed": ("Running",),                 # 失败后可重试
    "Cancelled": (),
}

# PLAN 六步 → 阶段分组（Stage/Checkpoint）：seq 区间 → 阶段定义
STAGE_PLAN: List[Dict[str, Any]] = [
    {"seq": 1, "name": "数据采集",   "kind": "data",      "steps": (1, 2)},
    {"seq": 2, "name": "归因分析",   "kind": "analysis",  "steps": (3, 4, 5)},
    {"seq": 3, "name": "行动确认",   "kind": "approval",  "steps": (6,)},
]


def can_transition(current: str, target: str) -> bool:
    """状态机迁移合法性校验。"""
    return target in TASK_TRANSITIONS.get(current, ())


class AgentTask(Base):
    """Agent 任务（TASK-009）— 一次用户诉求的完整生命周期。"""
    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    conversation_id: Mapped[str] = mapped_column(String(64), default="", index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(30), default="智能问答")  # 智能问答/数据分析/文档生成/任务执行/深度分析

    # TASK-012 TaskBrief：任务契约（goal/scope/acceptance/constraints），创建时由编排器写入
    brief: Mapped[str] = mapped_column(Text, default="{}")

    status: Mapped[str] = mapped_column(String(20), default="Pending")
    priority: Mapped[int] = mapped_column(Integer, default=3)   # 1 最高
    progress: Mapped[int] = mapped_column(Integer, default=0)

    result: Mapped[str] = mapped_column(Text, default="")       # 最终产出（Markdown）
    error: Mapped[str] = mapped_column(Text, default="")        # 失败原因
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))

    agent: Mapped[Agent | None] = relationship(back_populates="tasks")
    steps: Mapped[List["AgentStep"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    stages: Mapped[List["AgentStage"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    reviews: Mapped[List["TaskReview"]] = relationship(back_populates="task", cascade="all, delete-orphan")

    @property
    def brief_obj(self) -> Dict[str, Any]:
        """TaskBrief 解析（JSON 字段统一入口）。"""
        try:
            v = json.loads(self.brief or "{}")
            return v if isinstance(v, dict) else {}
        except (TypeError, ValueError):
            return {}

    def transition(self, target: str) -> bool:
        """按状态机迁移白名单更新状态；非法迁移返回 False 且不修改。"""
        if not can_transition(self.status, target):
            return False
        self.status = target
        return True


class AgentStep(Base):
    """任务步骤（TASK-010 任务规划 / Step Dependency）— Agent 拆出的执行计划。"""
    __tablename__ = "agent_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(30), default="think")  # think/knowledge/data/tool/approval/report
    # 依赖的上游步骤 ID，全部完成后本步才可开始
    depends_on: Mapped[str] = mapped_column(Text, default="[]")

    status: Mapped[str] = mapped_column(String(20), default="Pending")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    input_data: Mapped[str] = mapped_column(Text, default="{}")
    output_data: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    task: Mapped[AgentTask] = relationship(back_populates="steps")

    @property
    def deps(self) -> List[int]:
        return json.loads(self.depends_on or "[]")


class AgentStage(Base):
    """任务阶段（TASK-012 图谱 40-06 Stage/Checkpoint）— 长程任务的阶段投影。

    AgentStep 是"执行计划的最小动作"，AgentStage 是"面向人的阶段视图"：
    PLAN 六步聚合为 数据采集 → 归因分析 → 行动确认 三个阶段。
    每个阶段完成时写入 checkpoint（阶段摘要），供前端时间线/投影展示。
    """
    __tablename__ = "agent_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(80), default="")
    kind: Mapped[str] = mapped_column(String(20), default="data")  # data/analysis/approval
    # 覆盖的步骤区间（JSON 数组），用于进度计算
    step_seqs: Mapped[str] = mapped_column(Text, default="[]")

    status: Mapped[str] = mapped_column(String(20), default="Pending")
    # 检查点摘要（JSON）：阶段产出、关键数字、结论
    checkpoint: Mapped[str] = mapped_column(Text, default="{}")

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    task: Mapped[AgentTask] = relationship(back_populates="stages")

    @property
    def step_list(self) -> List[int]:
        try:
            return json.loads(self.step_seqs or "[]")
        except (TypeError, ValueError):
            return []

    @property
    def checkpoint_obj(self) -> Dict[str, Any]:
        try:
            v = json.loads(self.checkpoint or "{}")
            return v if isinstance(v, dict) else {}
        except (TypeError, ValueError):
            return {}


class TaskReview(Base):
    """任务复核记录（TASK-012 图谱 40-06 Review/Return）— 人机协作的复核留痕。

    任务进入 InReview 后，由有复核权限的人 approve / return；
    每条记录保留复核人、意见、决策时间，形成可审计的 Review 轨迹。
    """
    __tablename__ = "task_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id", ondelete="CASCADE"))
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("agent_stages.id", ondelete="SET NULL"))

    reviewer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewer_name: Mapped[str] = mapped_column(String(80), default="")
    decision: Mapped[str] = mapped_column(String(20), default="approve")  # approve / return
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))

    task: Mapped[AgentTask] = relationship(back_populates="reviews")


class AgentExecution(Base):
    """执行日志（TASK-008 工作过程可视化 / TASK-040 执行日志）。

    每一步都记录：做了什么、用了什么知识、查了什么数据、调了什么工具、
    耗时多久、成功与否。这是「AI 工作过程可解释」的唯一真相来源。
    """
    __tablename__ = "agent_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("agent_tasks.id", ondelete="CASCADE"))
    step_id: Mapped[int | None] = mapped_column(ForeignKey("agent_steps.id", ondelete="SET NULL"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"))

    action: Mapped[str] = mapped_column(String(80), default="")          # think / retrieve / query_data / call_tool
    label: Mapped[str] = mapped_column(String(200), default="")         # 展示文案：AI 正在查询 ERP 数据
    status: Mapped[str] = mapped_column(String(20), default="Running")  # Running/Completed/Failed

    input_data: Mapped[str] = mapped_column(Text, default="{}")
    output_data: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")

    # 溯源：用了哪些知识/数据/工具
    knowledge_refs: Mapped[str] = mapped_column(Text, default="[]")
    datasource_refs: Mapped[str] = mapped_column(Text, default="[]")
    tool_name: Mapped[str] = mapped_column(String(80), default="")

    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


# ==================== 知识域（TASK-012 ~ TASK-015） ====================

DOC_STATUS = ("草稿", "审核中", "已发布", "已过期", "已归档")


class KnowledgeBase(Base):
    """知识库（TASK-012）。"""
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="业务知识")
    # 企业制度/技术文档/产品资料/设备资料/项目案例/业务知识/客户知识
    description: Mapped[str] = mapped_column(Text, default="")
    # 可见范围：[] 表示企业内公开；否则为允许访问的部门 ID
    allowed_department_ids: Mapped[str] = mapped_column(Text, default="[]")
    authority_level: Mapped[int] = mapped_column(Integer, default=3)  # 权威等级 1(最高) ~ 5
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))

    documents: Mapped[List["KnowledgeDocument"]] = relationship(back_populates="kb", cascade="all, delete-orphan")


class KnowledgeDocument(Base):
    """知识文档（TASK-013/014）— 支持版本管理与审核状态。"""
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), default="txt")  # pdf/docx/xlsx/pptx/txt/md/image
    file_path: Mapped[str] = mapped_column(String(400), default="")
    source: Mapped[str] = mapped_column(String(200), default="")       # 来源记录
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="已发布")   # 草稿/审核中/已发布/已过期/已归档

    # 时效（TASK-014：知识必须有有效时间）
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    author: Mapped[str] = mapped_column(String(64), default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"), onupdate=_utcnow)

    kb: Mapped[KnowledgeBase] = relationship(back_populates="documents")
    chunks: Mapped[List["KnowledgeChunk"]] = relationship(back_populates="doc", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    """知识分片（TASK-013）— Embedding 与向量检索的最小单元。"""
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"))
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))

    seq: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    # 向量以 float32 二进制存储；无 API key 时由本地哈希引擎生成，维度与通义一致（1024）
    embedding: Mapped[bytes | None] = mapped_column(nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(60), default="")

    doc: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")


# ==================== 数据域（TASK-016 ~ TASK-018） ====================

CONN_STATUS = ("Connected", "Disconnected", "Error", "Syncing")


class DataSource(Base):
    """数据源类型（TASK-016）— MySQL / PostgreSQL / SQL Server / REST API / Excel / CSV。"""
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default="SQLite")  # MySQL/PostgreSQL/SQLServer/REST/Excel/CSV/SQLite
    category: Mapped[str] = mapped_column(String(40), default="业务系统")    # ERP/CRM/MES/OA/IoT/业务系统
    description: Mapped[str] = mapped_column(Text, default="")
    # 允许查询的表（TASK-018 SQL 白名单的数据基础）
    allowed_tables: Mapped[str] = mapped_column(Text, default="[]")
    # 敏感字段，查询时自动脱敏（TASK-018）
    sensitive_fields: Mapped[str] = mapped_column(Text, default="[]")
    read_only: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(20), default="Connected")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))

    connections: Mapped[List["DataConnection"]] = relationship(back_populates="source", cascade="all, delete-orphan")

    @property
    def tables(self) -> List[str]:
        return json.loads(self.allowed_tables or "[]")

    @property
    def sensitive(self) -> List[str]:
        return json.loads(self.sensitive_fields or "[]")


class DataConnection(Base):
    """数据连接（TASK-017）。"""
    __tablename__ = "data_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # 连接串不落明文：MVP 阶段存本地路径/DSN 引用，生产应接密钥管理
    dsn: Mapped[str] = mapped_column(String(400), default="")
    status: Mapped[str] = mapped_column(String(20), default="Connected")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))

    source: Mapped[DataSource] = relationship(back_populates="connections")


class DatasetAsset(Base):
    """数据资产（图谱 10-01 Source→Sync→Dataset→Lineage/Health 资产链）。

    Dataset 是"一个可被 AI/业务消费的数据产品"，挂在数据源之上：
    - source_id 引用数据源标识（store_data_sources 的 id，如 erp / crm / mes）
    - schema_json 存字段清单；lineage_json 存血缘（upstream/downstream，最小可用版）
    - health_status 由 sync 动作维护（healthy / warning / stale / error）
    """

    __tablename__ = "data_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, default=1, index=True,
                                            comment="租户键（图谱 60-02）；默认 1=单租户 MVP")
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True,
                                           comment="数据源标识（erp/crm/mes/...）")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default="table")  # table/api/stream/vector/file
    entity: Mapped[str] = mapped_column(String(120), default="", comment="来源表/实体，如 orders")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[str] = mapped_column(String(32), default="v1")
    schema_json: Mapped[str] = mapped_column(Text, default="[]", comment="字段清单 JSON")
    lineage_json: Mapped[str] = mapped_column(Text, default="{}", comment="血缘 JSON {upstream,downstream}")
    health_status: Mapped[str] = mapped_column(String(16), default="healthy")  # healthy/warning/stale/error
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    @property
    def schema_fields(self) -> list:
        try:
            return json.loads(self.schema_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def lineage(self) -> dict:
        try:
            return json.loads(self.lineage_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}


# ==================== 工具域（TASK-019 ~ TASK-020） ====================

TOOL_CATEGORY = ("查询工具", "分析工具", "执行工具", "通知工具", "文件工具")


class Tool(Base):
    """工具（TASK-019）— 统一工具定义，含输入/输出 Schema 与权限。"""
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80), nullable=False)      # 内部标识，如 query_erp_orders
    label: Mapped[str] = mapped_column(String(120), default="")        # 展示名
    category: Mapped[str] = mapped_column(String(30), default="查询工具")
    description: Mapped[str] = mapped_column(Text, default="")
    input_schema: Mapped[str] = mapped_column(Text, default="{}")
    output_schema: Mapped[str] = mapped_column(Text, default="{}")
    # 所需权限点，调用前校验（TASK-020）
    required_permission: Mapped[str] = mapped_column(String(80), default="")
    # 动作分级 1~4（TASK-021）
    action_level: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


class ToolExecution(Base):
    """工具调用日志（TASK-020）— 每次调用必须记录输入/输出/状态。"""
    __tablename__ = "tool_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    tool_id: Mapped[int | None] = mapped_column(ForeignKey("tools.id", ondelete="SET NULL"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("agent_tasks.id", ondelete="SET NULL"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    tool_name: Mapped[str] = mapped_column(String(80), default="")
    input_data: Mapped[str] = mapped_column(Text, default="{}")
    output_data: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="success")  # success/failed/blocked/pending_approval
    error: Mapped[str] = mapped_column(Text, default="")
    # 权限校验结果：pass / denied
    permission_check: Mapped[str] = mapped_column(String(20), default="pass")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


# ==================== 审批域（TASK-021 ~ TASK-022） ====================

APPROVAL_STATUS = ("Pending", "Approved", "Rejected", "Executed", "Cancelled")


class ApprovalRule(Base):
    """审批规则（TASK-021）— 动作分级 1 自动 / 2 通知后执行 / 3 必须审批 / 4 禁止。"""
    __tablename__ = "approval_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)   # 工具名或动作标识
    level: Mapped[int] = mapped_column(Integer, default=3)
    description: Mapped[str] = mapped_column(Text, default="")
    approver_role: Mapped[str] = mapped_column(String(40), default="owner")
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


class Approval(Base):
    """审批单（TASK-022）— 人工确认回路的载体。"""
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("agent_tasks.id", ondelete="SET NULL"))
    step_id: Mapped[int | None] = mapped_column(ForeignKey("agent_steps.id", ondelete="SET NULL"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"))

    title: Mapped[str] = mapped_column(String(200), default="")
    action: Mapped[str] = mapped_column(String(80), default="")     # 待执行的动作
    level: Mapped[int] = mapped_column(Integer, default=3)
    # AI 给出的理由 / 数据依据 / 执行计划（TASK-022 要求全部可查）
    ai_reason: Mapped[str] = mapped_column(Text, default="")
    data_evidence: Mapped[str] = mapped_column(Text, default="{}")
    plan: Mapped[str] = mapped_column(Text, default="{}")
    payload: Mapped[str] = mapped_column(Text, default="{}")        # 批准后的执行参数（可被人工修改）

    status: Mapped[str] = mapped_column(String(20), default="Pending")
    decided_by: Mapped[str] = mapped_column(String(64), default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    decision_lineage: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


class EvalContract(Base):
    """评估合同（图谱 EvalContract）— AI 决策质量的红线阈值。

    每条合同定义一项可观测指标（accuracy / fairness / latency）的阈值，
    由管理员经 admin 配置（默认 seed 三条基线）；Agent 决策链路
    按合同口径持续评估，超标即告警。Approval.decision_lineage 提供
    决策输入/输出哈希，供 EvalContract 事后复算核验。
    """

    __tablename__ = "eval_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, default=1, index=True)
    name: Mapped[str] = mapped_column(String(80), default="", comment="合同名，如 accuracy@agent")
    description: Mapped[str] = mapped_column(String(255), default="")
    metric: Mapped[str] = mapped_column(String(20), default="accuracy")
    operator: Mapped[str] = mapped_column(String(8), default="gte")   # gte / lte
    threshold: Mapped[float] = mapped_column(Float, default=0.9)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


# ==================== 通知与审计（TASK-039 ~ TASK-041） ====================

class Notification(Base):
    """通知（TASK-039）— 系统/Agent 任务/审批/异常/AI 洞察。"""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ntype: Mapped[str] = mapped_column(String(30), default="system")
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Unread")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


class ActionReceipt(Base):
    """动作执行凭证（图谱 Receipt / 20-05）— 不可变审计链。

    每次经网关真实执行（含审批批准后执行）都会写入一条 receipt：
    params/result 的 sha256 哈希保证「事后可核验、不可篡改」；
    重复执行生成新 receipt，旧的不变（可复算）。
    """
    __tablename__ = "action_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    approval_id: Mapped[int | None] = mapped_column(
        ForeignKey("approvals.id", ondelete="SET NULL"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(80), default="")
    params_hash: Mapped[str] = mapped_column(String(64), default="")
    result_hash: Mapped[str] = mapped_column(String(64), default="")
    actor_type: Mapped[str] = mapped_column(String(20), default="agent")
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


class AuditLog(Base):
    """审计日志（TASK-041）— 用户操作 / Agent 操作 / 工具调用 / 数据访问 / 审批 / 登录。"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="user")   # user / agent / system
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_name: Mapped[str] = mapped_column(String(80), default="")
    action: Mapped[str] = mapped_column(String(80), default="")
    target: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[str] = mapped_column(Text, default="{}")
    result: Mapped[str] = mapped_column(String(20), default="success")    # success / denied / failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


# ==================== 销售跟进任务（主线案例落点） ====================

class InspectionWorkOrder(Base):
    """核电巡检工单 — Agent 经人工审批后创建的巡检处置动作落点。

    与 SalesTask 同构但独立建表：业务语境不同（巡检处置 vs 销售跟进），
    生命周期、责任人、审批链路各自独立，避免跨领域概念污染。
    """
    __tablename__ = "inspection_work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    station_code: Mapped[str] = mapped_column(String(32), default="")   # MS-01 等
    station_name: Mapped[str] = mapped_column(String(120), default="")

    title: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(20), default="high")   # high/medium/low
    owner: Mapped[str] = mapped_column(String(64), default="")
    due_date: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(20), default="待处置")

    source: Mapped[str] = mapped_column(String(20), default="agent")    # agent / human
    agent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))


class SalesTask(Base):
    """销售跟进任务 — Agent 经人工审批后在 CRM 中创建的动作落点。

    单独建表而非复用 AgentTask：AgentTask 是「AI 的分析任务」，
    SalesTask 是「业务系统里的跟进事项」，二者生命周期与责任人不同。
    """
    __tablename__ = "sales_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    customer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer_name: Mapped[str] = mapped_column(String(120), default="")

    title: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(20), default="high")  # high/medium/low
    owner: Mapped[str] = mapped_column(String(64), default="")
    due_date: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(20), default="待跟进")

    source: Mapped[str] = mapped_column(String(20), default="agent")    # agent / human
    agent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))




# ---------------- SecretRef / Keychain（60-04 密钥引用） ----------------

class SecretEntry(Base):
    """密钥引用（60-04 SecretRef + Keychain）。

    告别 `.env` 明文：密钥以 SecretEntry 落库（按租户隔离 + RLS），
    对外只暴露脱敏视图，任何日志 / API 响应不回显明文。

    字段语义：
    - ref_key：稳定引用名（如 `llm:deepseek` / `ds:erp` / `webhook:alert`），
      业务代码通过 ref_key 解析，不直接接触明文。
    - kind：llm / datasource / webhook / custom（用途归类）。
    - pii_level：none / low / high（PII 敏感度标注）。
    - retention_days：保留期（天），治理与过期清理依据。
    - region：数据驻留区域标注（如 cn / us / eu）。
    """
    __tablename__ = "secret_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    ref_key: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="custom")      # llm/datasource/webhook/custom
    secret_value: Mapped[str] = mapped_column(Text, default="")
    pii_level: Mapped[str] = mapped_column(String(20), default="none")   # none/low/high
    retention_days: Mapped[int] = mapped_column(Integer, default=365)
    region: Mapped[str] = mapped_column(String(20), default="cn")
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))


# ---------------- 审计便捷方法 ----------------

def write_audit(
    db,
    *,
    action: str,
    actor_type: str = "user",
    actor_id: int | None = None,
    actor_name: str = "",
    company_id: int | None = None,
    target: str = "",
    detail: Any = None,
    result: str = "success",
) -> AuditLog:
    """统一写审计日志。任何关键动作都应调用它。"""
    log = AuditLog(
        company_id=company_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_name=actor_name,
        action=action,
        target=target,
        detail=_jd(detail if detail is not None else {}),
        result=result,
    )

    db.add(log)
    db.flush()
    return log


class LogicGraph(Base):
    """Logic 决策编排图（30-03）：一条业务链路的节点集合（服务端图，可查/可改/可激活）。"""
    __tablename__ = "logic_graphs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), default=1, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)          # sales-drop / inspection-anomaly
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="1.0")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")  # active|draft
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"),
                                                 onupdate=_utcnow)

    nodes: Mapped[List["LogicNode"]] = relationship(
        "LogicNode", back_populates="graph", cascade="all, delete-orphan",
        order_by="LogicNode.seq")

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_logic_graphs_company_code"),)


class LogicNode(Base):
    """Logic 图节点：一个可执行步骤（data/knowledge/tool/report/approval）。"""
    __tablename__ = "logic_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    graph_id: Mapped[int] = mapped_column(ForeignKey("logic_graphs.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), default=1, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")   # step_1 / 工具名
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)          # data|knowledge|tool|report|approval
    tool: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    label: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")  # 前端画布展示文案
    params_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    depends_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"),
                                                 onupdate=_utcnow)

    graph: Mapped["LogicGraph"] = relationship("LogicGraph", back_populates="nodes")

    __table_args__ = (UniqueConstraint("graph_id", "seq", name="uq_logic_nodes_graph_seq"),)


class AppPage(Base):
    """低代码页面定义（40-03）：Widget 列表（layout_json）+ 发布状态。"""
    __tablename__ = "app_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), default=1, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")  # draft|published
    version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="1.0")
    layout_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")  # [ {widget,title,params} ]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"),
                                                 onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_app_pages_company_code"),)


class AssetBundle(Base):
    """资产包（50-01 Bundle）：Manifest + 打包内容（pages/logic 资产定义）。

    系统级资产目录（RLS 豁免，类似 permissions/ontology_types 先例）：
    Bundle 由某企业作者创建（created_by_company_id），但目录本身跨租户只读共享；
    租户通过 install（派生优先）在自命名空间生成派生资产（asset_installations）。
    """
    __tablename__ = "asset_bundles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="1.0")
    kind: Mapped[str] = mapped_column(String(24), nullable=False, server_default="bundle")  # bundle|plugin
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    # {nav_entry:{href,icon,label,perm}, widget_types:[...], permissions:[...], requires:["pages","logic"]}
    content_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    # {pages:[{code,title,description,layout}], logic_graphs:[{code,name,description,nodes:[...]}]}
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")  # draft|published
    created_by_company_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"),
                                                 onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("code", name="uq_asset_bundles_code"),)


class AssetInstallation(Base):
    """租户安装记录（50-03 Installation，派生优先语义）。

    安装 = 把 Bundle 内容复制到租户命名空间生成派生资产（app_pages / logic_graphs），
    原 Bundle 只读；租户对同一 Bundle 只装一次（升级=更新 bundle_version 并可选重新派生）。
    """
    __tablename__ = "asset_installations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), default=1, index=True)
    bundle_id: Mapped[int] = mapped_column(ForeignKey("asset_bundles.id", ondelete="CASCADE"))
    bundle_code: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    bundle_version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="1.0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="installed")  # installed|uninstalled
    derived_pages_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")  # [{code,page_id,title}]
    derived_graphs_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")  # [{code,graph_id,name}]
    installed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                  server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"),
                                                 onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("company_id", "bundle_id", name="uq_asset_install_company_bundle"),)
