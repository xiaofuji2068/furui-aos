"""组织与权限 API（TASK-002 用户与企业体系 / TASK-003 RBAC 权限体系）。

数据隔离规则（验收标准）：
- 非超级管理员只能看到「自己所在企业」的数据；
- 部门负责人只能看到「自己所在部门及下级」的数据；
- 所有写操作走 require_perm 守卫，Agent 不参与此路由（Agent 权限另由 Agent 白名单约束）。

GET   /api/org/companies            企业列表
POST  /api/org/companies            创建企业
PUT   /api/org/companies/{id}       编辑企业
DELETE /api/org/companies/{id}      删除企业
GET   /api/org/departments          部门列表（按企业/可见范围过滤）
POST  /api/org/departments          创建部门
PUT   /api/org/departments/{id}     编辑部门
DELETE /api/org/departments/{id}    删除部门
GET   /api/org/users                用户列表
POST  /api/org/users                创建用户
PUT   /api/org/users/{id}           编辑用户（含角色分配、状态）
DELETE /api/org/users/{id}          删除用户
GET   /api/org/roles                角色列表（含权限）
POST  /api/org/roles                创建角色
PUT   /api/org/roles/{id}           编辑角色权限
GET   /api/org/permissions          权限目录
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_perm
from ..db import get_db
from ..models import (
    PERMISSION_CATALOG, Company, Department, Permission, Role, User,
)
from ..response import ok
from ..security import hash_password

# 注意：外层汇总路由已带 /api 前缀，此处只用相对前缀，避免 /api/api/org
router = APIRouter(prefix="/org", tags=["组织与权限"])


# ---------------- 数据范围（TASK-003 数据权限） ----------------

def visible_company_ids(db: Session, user: User) -> List[int]:
    """用户可见的企业 ID 列表。

    隔离原则：数据「可见范围」由组织边界决定，不由权限点决定。
    - 系统超管：可见全部企业
    - 其余用户：只能看见自己所属企业
    """
    if user.is_superuser:
        return [c.id for c in db.query(Company).all()]
    return [user.company_id] if user.company_id else []


def visible_department_ids(db: Session, user: User) -> List[int]:
    """用户可见的部门 ID 列表。

    - 部门管理权只在「本企业内」放大可见范围，绝不跨企业
    - 普通用户：直属部门及其所有下级（支持多级 parent_id）
    """
    if not user.company_id:
        return []
    depts = db.query(Department).filter(Department.company_id == user.company_id).all()

    if user.has_perm("department:manage"):
        return [d.id for d in depts]

    if user.department_id:
        allowed = set()
        pending = [user.department_id]
        while pending:
            cur = pending.pop()
            allowed.add(cur)
            pending.extend(d.id for d in depts if d.parent_id == cur)
        return [d.id for d in depts if d.id in allowed]
    return [d.id for d in depts]


def _assert_company_access(db: Session, user: User, company_id: int):
    if company_id not in visible_company_ids(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 403, "message": "无权限访问该企业数据"},
        )


def _get_or_404(db: Session, model, obj_id: int):
    obj = db.get(model, obj_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 404, "message": f"{model.__name__} {obj_id} 不存在"},
        )
    return obj


# ---------------- Schemas ----------------

class CompanyIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    code: str = Field(..., min_length=1, max_length=64)
    status: str = "active"


class DepartmentIn(BaseModel):
    company_id: int
    name: str = Field(..., min_length=1, max_length=120)
    parent_id: Optional[int] = None


class UserIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field("123456", min_length=6, max_length=128)
    name: str = ""
    email: str = ""
    company_id: Optional[int] = None
    department_id: Optional[int] = None
    status: str = "active"
    role_ids: List[int] = []


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    company_id: Optional[int] = None
    department_id: Optional[int] = None
    status: Optional[str] = None
    password: Optional[str] = None
    role_ids: Optional[List[int]] = None


class RoleIn(BaseModel):
    company_id: Optional[int] = None
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=64)
    description: str = ""
    permission_codes: List[str] = []


# ---------------- 企业 ----------------

@router.get("/companies")
def list_companies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ids = visible_company_ids(db, user)
    rows = db.query(Company).filter(Company.id.in_(ids)).all() if ids else []
    return ok({
        "items": [
            {
                "id": c.id, "name": c.name, "code": c.code, "status": c.status,
                "created_at": str(c.created_at),
                "department_count": len(c.departments),
                "user_count": len(c.users),
            }
            for c in rows
        ]
    })


@router.post("/companies")
def create_company(
    req: CompanyIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("company:manage")),
):
    if db.query(Company).filter(Company.code == req.code).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 409, "message": f"企业编码 {req.code} 已存在"},
        )
    c = Company(name=req.name, code=req.code, status=req.status)
    db.add(c)
    db.commit()
    db.refresh(c)
    return ok({"id": c.id, "name": c.name, "code": c.code}, message="企业已创建")


@router.put("/companies/{company_id}")
def update_company(
    company_id: int,
    req: CompanyIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("company:manage")),
):
    _assert_company_access(db, user, company_id)
    c = _get_or_404(db, Company, company_id)
    c.name, c.code, c.status = req.name, req.code, req.status
    db.commit()
    return ok({"id": c.id}, message="企业已更新")


@router.delete("/companies/{company_id}")
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("company:manage")),
):
    _assert_company_access(db, user, company_id)
    c = _get_or_404(db, Company, company_id)
    db.delete(c)
    db.commit()
    return ok({"id": company_id}, message="企业已删除")


# ---------------- 部门 ----------------

@router.get("/departments")
def list_departments(
    company_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Department)
    if company_id:
        _assert_company_access(db, user, company_id)
        q = q.filter(Department.company_id == company_id)
    else:
        ids = visible_department_ids(db, user)
        q = q.filter(Department.id.in_(ids)) if ids else q.filter(Department.id == -1)
    rows = q.order_by(Department.id).all()
    return ok({
        "items": [
            {
                "id": d.id, "company_id": d.company_id, "name": d.name,
                "parent_id": d.parent_id, "user_count": len(d.users),
            }
            for d in rows
        ]
    })


@router.post("/departments")
def create_department(
    req: DepartmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("department:manage")),
):
    _assert_company_access(db, user, req.company_id)
    d = Department(company_id=req.company_id, name=req.name, parent_id=req.parent_id)
    db.add(d)
    db.commit()
    db.refresh(d)
    return ok({"id": d.id, "name": d.name}, message="部门已创建")


@router.put("/departments/{dept_id}")
def update_department(
    dept_id: int,
    req: DepartmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("department:manage")),
):
    d = _get_or_404(db, Department, dept_id)
    _assert_company_access(db, user, d.company_id)
    d.name, d.parent_id = req.name, req.parent_id
    db.commit()
    return ok({"id": d.id}, message="部门已更新")


@router.delete("/departments/{dept_id}")
def delete_department(
    dept_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("department:manage")),
):
    d = _get_or_404(db, Department, dept_id)
    _assert_company_access(db, user, d.company_id)
    if d.users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 409, "message": "部门下仍有用户，请先转移或删除"},
        )
    db.delete(d)
    db.commit()
    return ok({"id": dept_id}, message="部门已删除")


# ---------------- 用户 ----------------

@router.get("/users")
def list_users(
    company_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """数据隔离核心：不同用户看到不同企业 / 部门的用户。"""
    q = db.query(User)
    if company_id:
        _assert_company_access(db, user, company_id)
        q = q.filter(User.company_id == company_id)
    else:
        cids = visible_company_ids(db, user)
        dids = visible_department_ids(db, user)
        q = q.filter(User.company_id.in_(cids) if cids else User.id == -1)
        if not user.has_perm("user:manage") and dids:
            q = q.filter(User.department_id.in_(dids))
    if department_id:
        q = q.filter(User.department_id == department_id)

    rows = q.order_by(User.id).all()
    return ok({
        "items": [
            {
                "id": u.id, "username": u.username, "name": u.name, "email": u.email,
                "status": u.status,
                "company": u.company.name if u.company else None,
                "department": u.department.name if u.department else None,
                "roles": [{"id": r.id, "code": r.code, "name": r.name} for r in u.roles],
                "permission_count": len(u.permissions),
            }
            for u in rows
        ]
    })


@router.post("/users")
def create_user(
    req: UserIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("user:manage")),
):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 409, "message": f"用户名 {req.username} 已存在"},
        )
    cid = req.company_id or user.company_id
    if cid:
        _assert_company_access(db, user, cid)
    u = User(
        username=req.username,
        password_hash=hash_password(req.password),
        name=req.name, email=req.email,
        company_id=cid, department_id=req.department_id,
        status=req.status,
    )
    for rid in req.role_ids:
        r = db.get(Role, rid)
        if r:
            u.roles.append(r)
    db.add(u)
    db.commit()
    db.refresh(u)
    return ok({"id": u.id, "username": u.username}, message="用户已创建")


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    req: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("user:manage")),
):
    u = _get_or_404(db, User, user_id)
    if u.company_id:
        _assert_company_access(db, user, u.company_id)

    for field in ("name", "email", "status"):
        val = getattr(req, field)
        if val is not None:
            setattr(u, field, val)
    if req.company_id is not None:
        _assert_company_access(db, user, req.company_id)
        u.company_id = req.company_id
    if req.department_id is not None:
        u.department_id = req.department_id
    if req.password:
        u.password_hash = hash_password(req.password)
    if req.role_ids is not None:
        u.roles = [db.get(Role, rid) for rid in req.role_ids if db.get(Role, rid)]

    db.commit()
    return ok({"id": u.id, "username": u.username}, message="用户已更新")


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("user:manage")),
):
    if user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 400, "message": "不能删除当前登录用户"},
        )
    u = _get_or_404(db, User, user_id)
    db.delete(u)
    db.commit()
    return ok({"id": user_id}, message="用户已删除")


# ---------------- 角色与权限 ----------------

@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cid = user.company_id
    rows = db.query(Role).filter((Role.company_id == cid) | (Role.company_id.is_(None))).all()
    return ok({
        "items": [
            {
                "id": r.id, "code": r.code, "name": r.name,
                "description": r.description,
                "user_count": len(r.users),
                "permissions": [{"code": p.code, "name": p.name, "scope": p.scope} for p in r.permissions],
            }
            for r in rows
        ]
    })


@router.post("/roles")
def create_role(
    req: RoleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("role:manage")),
):
    if db.query(Role).filter(Role.code == req.code).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 409, "message": f"角色编码 {req.code} 已存在"},
        )
    valid = {c for c, _, _ in PERMISSION_CATALOG}
    r = Role(
        company_id=req.company_id or user.company_id,
        code=req.code, name=req.name, description=req.description,
    )
    for pc in req.permission_codes:
        if pc in valid:
            p = db.query(Permission).filter(Permission.code == pc).first()
            if p:
                r.permissions.append(p)
    db.add(r)
    db.commit()
    db.refresh(r)
    return ok({"id": r.id, "code": r.code}, message="角色已创建")


@router.put("/roles/{role_id}")
def update_role(
    role_id: int,
    req: RoleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("role:manage")),
):
    r = _get_or_404(db, Role, role_id)
    r.name, r.description = req.name, req.description
    valid = {c for c, _, _ in PERMISSION_CATALOG}
    r.permissions = [
        p for pc in req.permission_codes if pc in valid
        for p in [db.query(Permission).filter(Permission.code == pc).first()] if p
    ]
    db.commit()
    return ok({
        "id": r.id,
        "permission_count": len(r.permissions),
    }, message="角色权限已更新")


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """权限目录（页面/菜单/数据/Agent/知识/数据源/工具/执行/审批）。"""
    rows = db.query(Permission).order_by(Permission.scope, Permission.code).all()
    grouped: dict[str, list] = {}
    for p in rows:
        grouped.setdefault(p.scope, []).append({"code": p.code, "name": p.name})
    return ok({
        "catalog": grouped,
        "items": [{"code": p.code, "name": p.name, "scope": p.scope} for p in rows],
        "mine": sorted(user.permissions),
    })
