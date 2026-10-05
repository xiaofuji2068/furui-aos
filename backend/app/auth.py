"""认证与授权依赖（TASK-002 登录 / TASK-003 RBAC）。

使用方式：
    @router.get("/xxx")
    def handler(user: User = Depends(get_current_user)):        # 只要登录
    def handler(user: User = Depends(require_perm("tool:use"))): # 需要具体权限
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import create_token, decode_token, verify_password

bearer_scheme = HTTPBearer(auto_error=False)

_CRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="未登录或登录已过期",
    headers={"WWW-Authenticate": "Bearer"},
)


def authenticate(db: Session, username: str, password: str) -> User | None:
    """校验账号密码；账号被禁用时一律失败。"""
    user = db.query(User).filter(User.username == username).first()
    if not user or user.status != "active":
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def issue_token(user: User) -> str:
    return create_token({
        "sub": user.id,
        "username": user.username,
        "company_id": user.company_id,
        "department_id": user.department_id,
    })


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _CRED_ERROR
    payload = decode_token(credentials.credentials)
    if not payload:
        raise _CRED_ERROR
    user = db.get(User, int(payload.get("sub", 0)))
    if not user or user.status != "active":
        raise _CRED_ERROR
    return user


def require_perm(code: str):
    """权限点守卫：用户所属角色的权限集合中必须包含该 code。"""

    def _guard(user: User = Depends(get_current_user)) -> User:
        if not user.has_perm(code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限：{code}",
            )
        return user

    return _guard


def require_any_perm(*codes: str):
    """满足任意一个权限点即可。"""

    def _guard(user: User = Depends(get_current_user)) -> User:
        perms = user.permissions
        if not any(c in perms for c in codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限：{' / '.join(codes)}",
            )
        return user

    return _guard
