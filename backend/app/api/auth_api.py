"""认证 API（TASK-002 用户登录 / 退出 / 用户信息 / 状态管理）。

POST /api/auth/login      登录，返回 JWT
POST /api/auth/logout     退出（服务端无状态，客户端丢弃 token）
GET  /api/auth/me         当前用户信息 + 企业/部门 + 权限清单
POST /api/auth/password   修改密码
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import authenticate, get_current_user, issue_token
from ..db import get_db
from ..models import User
from ..response import ok
from ..security import hash_password, verify_password

# 注意：外层汇总路由已带 /api 前缀，此处只用相对前缀，避免 /api/api/auth
router = APIRouter(prefix="/auth", tags=["认证"])


class LoginReq(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class PasswordReq(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


def _user_profile(user: User) -> dict:
    """用户信息 + 企业/部门 + 权限清单（供前端做菜单与按钮级控制）。"""
    perms = sorted(user.permissions)
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "status": user.status,
        "is_superuser": user.is_superuser,
        "company": (
            {"id": user.company.id, "name": user.company.name, "code": user.company.code}
            if user.company else None
        ),
        "department": (
            {"id": user.department.id, "name": user.department.name}
            if user.department else None
        ),
        "roles": [{"id": r.id, "code": r.code, "name": r.name} for r in user.roles],
        "permissions": perms,
        # 菜单/页面级权限：前端按 scope=page 过滤
        "scopes": {
            "page": [p for p in perms if p.startswith(("company:", "department:", "user:", "role:", "log:", "scene:"))],
            "agent": [p for p in perms if p.startswith("employee:")],
            "knowledge": [p for p in perms if p.startswith("knowledge:")],
            "datasource": [p for p in perms if p.startswith("datasource:")],
            "tool": [p for p in perms if p.startswith("tool:")],
            "exec": [p for p in perms if p.startswith("employee:execute")],
            "approval": [p for p in perms if p.startswith("approval:")],
        },
    }


@router.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = authenticate(db, req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "message": "用户名或密码错误"},
        )
    return ok({
        "token": issue_token(user),
        "token_type": "bearer",
        "expires_in": 60 * 60 * 12,
        "user": _user_profile(user),
    })


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    """JWT 无状态，退出即客户端丢弃 token；此处仅做一次审计占位。"""
    return ok({"username": user.username}, message="已退出登录")


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return ok(_user_profile(user))


@router.post("/password")
def change_password(
    req: PasswordReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 400, "message": "原密码不正确"},
        )
    user.password_hash = hash_password(req.new_password)
    db.commit()
    return ok({"username": user.username}, message="密码已更新")
