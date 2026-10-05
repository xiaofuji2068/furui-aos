"""企业 AI 核心对象 — ORM 模型（TASK-004 的组织域部分）。

覆盖：
- TASK-002 用户与企业体系：Company / Department / User
- TASK-003 权限系统 RBAC：Role / Permission + 多对多关联

权限设计原则（对应清单验收标准）：
AI Agent 不能直接拥有无限权限 —— 后续 Agent 模型将绑定
「允许访问的数据 / 知识 / 工具 / 操作」四类白名单，见后续迁移。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Table, Column, Text, text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from .db import Base, SessionLocal, engine
from .security import hash_password


def _utcnow() -> datetime:
    return datetime.utcnow()


# ---------------- 关联表 ----------------

user_roles = Table(
    "user_roles", Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions", Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


# ---------------- 组织域 ----------------

class Company(Base):
    """企业 — 数据隔离的第一道边界。"""
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")   # active / disabled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))

    departments: Mapped[list["Department"]] = relationship(back_populates="company")
    users: Mapped[list["User"]] = relationship(back_populates="company")


class Department(Base):
    """部门 — 数据隔离的第二道边界。"""
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))

    company: Mapped[Company] = relationship(back_populates="departments")
    users: Mapped[list["User"]] = relationship(back_populates="department")


class User(Base):
    """用户 — 登录主体，绑定企业与部门。"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(120), default="")
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="active")   # active / disabled
    # 系统超管：唯一能跨企业查看数据的主体。
    # 数据隔离边界由 company_id 强制决定；权限点只控制"能否增删改"，
    # 不控制"能否跨企业看"——否则 admin 角色会变成全局通行证。
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))

    company: Mapped[Company | None] = relationship(back_populates="users")
    department: Mapped[Department | None] = relationship(back_populates="users")
    roles: Mapped[list["Role"]] = relationship(secondary=user_roles, back_populates="users")

    # ---- 权限 ----

    @property
    def permissions(self) -> set[str]:
        """该用户拥有的全部权限 code（经角色展开）。"""
        codes: set[str] = set()
        for role in self.roles:
            for perm in role.permissions:
                codes.add(perm.code)
        return codes

    def has_perm(self, code: str) -> bool:
        return code in self.permissions


class Role(Base):
    """角色 — 权限的载体。"""
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[list["Permission"]] = relationship(secondary=role_permissions, back_populates="roles")


class Permission(Base):
    """权限点 — 覆盖页面/菜单/数据/Agent/知识/数据源/工具/执行/审批。"""
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    scope: Mapped[str] = mapped_column(String(40), default="page")  # page/data/agent/knowledge/datasource/tool/exec/approval

    roles: Mapped[list[Role]] = relationship(secondary=role_permissions, back_populates="permissions")


# ---------------- 权限清单 ----------------
# scope 对应清单「权限范围」，动作对应「查看/使用/创建/编辑/删除/审批/执行」

PERMISSION_CATALOG: list[tuple[str, str, str]] = [
    # (code, 名称, 范围)
    ("company:view",     "查看企业信息",   "page"),
    ("company:manage",   "管理企业信息",   "page"),
    ("department:view",  "查看部门",       "page"),
    ("department:manage", "管理部门",      "page"),
    ("user:view",        "查看用户",       "page"),
    ("user:manage",      "管理用户",       "page"),
    ("role:view",        "查看角色",       "page"),
    ("role:manage",      "管理角色权限",   "page"),

    ("employee:view",    "查看 AI 员工",   "agent"),
    ("employee:use",     "使用 AI 员工",   "agent"),
    ("employee:create",  "创建 AI 员工",   "agent"),
    ("employee:edit",    "编辑 AI 员工",   "agent"),
    ("employee:delete",  "删除 AI 员工",   "agent"),
    ("employee:execute", "执行 Agent 任务", "exec"),

    ("knowledge:view",   "查看知识",       "knowledge"),
    ("knowledge:use",    "检索知识",       "knowledge"),
    ("knowledge:write",  "写入/上传知识",  "knowledge"),
    ("knowledge:manage", "管理知识库",     "knowledge"),

    ("datasource:view",  "查看数据源",     "datasource"),
    ("datasource:config", "配置数据源连接", "datasource"),

    ("tool:view",        "查看工具",       "tool"),
    ("tool:use",         "调用工具",       "tool"),
    ("tool:config",      "配置工具",       "tool"),

    ("approval:view",    "查看审批",       "approval"),
    ("approval:approve", "审批/确认执行",  "approval"),

    ("log:view",         "查看日志审计",   "page"),
    ("scene:view",       "查看业务场景",   "page"),
    ("scene:manage",     "管理业务场景",   "page"),
]

# 角色 → 权限白名单（对齐清单中"不同角色不同功能权限"的验收要求）
ROLE_PERMISSION_MAP: dict[str, list[str]] = {
    "admin":   [c for c, _, _ in PERMISSION_CATALOG],                      # 管理员：全部
    "owner":   [                                                            # 业务负责人
        "company:view", "department:view", "user:view",
        "employee:view", "employee:use", "employee:execute",
        "knowledge:view", "knowledge:use", "knowledge:write",
        "datasource:view", "tool:view", "tool:use",
        "approval:view", "approval:approve",
        "scene:view", "scene:manage",
    ],
    "analyst": [                                                            # 数据分析师
        "company:view", "department:view",
        "employee:view", "employee:use", "employee:execute",
        "knowledge:view", "knowledge:use",
        "datasource:view", "datasource:config",
        "tool:view", "tool:use",
        "approval:view", "log:view", "scene:view",
    ],
    "ops":     [                                                            # 运维工程师
        "company:view", "department:view",
        "employee:view", "employee:use", "employee:execute",
        "knowledge:view", "knowledge:use",
        "datasource:view", "datasource:config",
        "tool:view", "tool:use",
        "approval:approve", "log:view", "scene:view",
    ],
}

ROLE_NAMES = {
    "admin": "管理员",
    "owner": "业务负责人",
    "analyst": "数据分析师",
    "ops": "运维工程师",
}


# ---------------- 初始化 & 种子数据 ----------------

def _seed(db: Session) -> None:
    """幂等种子：权限目录、两个企业、部门、四个角色、五个用户（含跨企业账号）。"""
    if db.query(Company).count() > 0:
        return

    # 1. 权限目录
    perms: dict[str, Permission] = {}
    for code, name, scope in PERMISSION_CATALOG:
        p = Permission(code=code, name=name, scope=scope)
        db.add(p)
        perms[code] = p
    db.flush()

    # 2. 企业（两家，用于验证"不同用户看到不同企业数据"）
    furui = Company(name="傅瑞科技", code="FURUI", status="active")
    demo = Company(name="演示企业A", code="DEMO-A", status="active")
    db.add_all([furui, demo])
    db.flush()

    # 3. 部门
    hq = Department(company_id=furui.id, name="总部")
    sales = Department(company_id=furui.id, name="销售部")
    finance = Department(company_id=furui.id, name="财务部")
    ops_dept = Department(company_id=furui.id, name="设备运维部")
    demo_hq = Department(company_id=demo.id, name="演示总部")
    db.add_all([hq, sales, finance, ops_dept, demo_hq])
    db.flush()

    # 4. 角色（每家企业一套）
    roles: dict[str, dict[str, Role]] = {}
    for comp in (furui, demo):
        bucket: dict[str, Role] = {}
        for code, name in ROLE_NAMES.items():
            r = Role(company_id=comp.id, code=f"{comp.code.lower()}:{code}", name=name)
            for pc in ROLE_PERMISSION_MAP[code]:
                r.permissions.append(perms[pc])
            db.add(r)
            bucket[code] = r
        roles[comp.code] = bucket
    db.flush()

    # 5. 用户（密码统一 123456，便于验收；生产请改）
    pwd = hash_password("123456")
    users = [
        User(username="admin",   password_hash=pwd, name="王欢",   email="admin@furui.com",
             company_id=furui.id, department_id=hq.id,       status="active", is_superuser=True),
        User(username="sales",   password_hash=pwd, name="李明",   email="sales@furui.com",
             company_id=furui.id, department_id=sales.id,    status="active"),
        User(username="analyst", password_hash=pwd, name="张数据分析", email="analyst@furui.com",
             company_id=furui.id, department_id=finance.id,  status="active"),
        User(username="ops",     password_hash=pwd, name="赵运维", email="ops@furui.com",
             company_id=furui.id, department_id=ops_dept.id, status="active"),
        User(username="guest",   password_hash=pwd, name="外部访客", email="guest@demo-a.com",
             company_id=demo.id,  department_id=demo_hq.id,  status="active"),
    ]
    users[0].roles.append(roles[furui.code]["admin"])
    users[1].roles.append(roles[furui.code]["owner"])
    users[2].roles.append(roles[furui.code]["analyst"])
    users[3].roles.append(roles[furui.code]["ops"])
    users[4].roles.append(roles[demo.code]["admin"])
    db.add_all(users)

    db.commit()


class SystemSetting(Base):
    """系统设置（按租户持久化；TASK-021 替代内存暂存，保存重启不丢）。"""
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), default=1, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (UniqueConstraint("company_id", "key", name="uq_system_settings_company_key"),)



def init_db() -> None:
    """建表 + 灌入种子数据（幂等，可重复调用）。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed(db)
    finally:
        db.close()
