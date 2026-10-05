"""资产装配 API（50 全系）：Bundle catalog / 安装 / 卸载 / 重新派生 / Resolver。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user, require_perm
from ..db import SessionLocal
from ..models import User
from ..assets import (
    list_bundles, get_bundle, create_bundle, publish_bundle,
    install_bundle, rederive_bundle, uninstall_bundle,
    installed_assets, installed_nav, resolve_bundle,
)

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/bundles")
def assets_list(user: User = Depends(get_current_user)):
    """资产目录（含当前租户已安装状态）。"""
    db = SessionLocal()
    try:
        return {"items": list_bundles(db, user.company_id)}
    finally:
        db.close()


@router.get("/bundles/{bundle_id}")
def assets_detail(bundle_id: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        b = get_bundle(db, bundle_id, user.company_id)
        if not b:
            raise HTTPException(status_code=404, detail="bundle not found")
        return b
    finally:
        db.close()


class BundleCreateReq(BaseModel):
    code: str
    name: str
    description: str = ""
    version: str = "1.0"
    kind: str = "bundle"
    manifest: Dict[str, Any] = {}
    content: Dict[str, Any] = {}


@router.post("/bundles")
def assets_create(req: BundleCreateReq, user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        try:
            b = create_bundle(db, req.dict(), created_by_company_id=user.company_id or 1)
            return get_bundle(db, b.id, user.company_id)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    finally:
        db.close()


@router.post("/bundles/{bundle_id}/publish")
def assets_publish(bundle_id: int, user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        b = publish_bundle(db, bundle_id)
        if not b:
            raise HTTPException(status_code=404, detail="bundle not found")
        return get_bundle(db, b.id, user.company_id)
    finally:
        db.close()


class InstallReq(BaseModel):
    bundle_id: int


@router.post("/install")
def assets_install(req: InstallReq, user: User = Depends(require_perm("tool:config"))):
    """派生安装（幂等）：把 Bundle 内容复制到租户命名空间。"""
    db = SessionLocal()
    try:
        try:
            return install_bundle(db, user.company_id, req.bundle_id)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    finally:
        db.close()


@router.post("/installations/{installation_id}/rederive")
def assets_rederive(installation_id: int, user: User = Depends(require_perm("tool:config"))):
    """显式重新派生：补齐缺失派生资产（存在则保留，不覆盖定制）。"""
    db = SessionLocal()
    try:
        try:
            return rederive_bundle(db, user.company_id, installation_id)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    finally:
        db.close()


@router.post("/installations/{installation_id}/uninstall")
def assets_uninstall(installation_id: int, user: User = Depends(require_perm("tool:config"))):
    """卸载：删除本租户派生资产 + 安装记录。"""
    db = SessionLocal()
    try:
        try:
            return uninstall_bundle(db, user.company_id, installation_id)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    finally:
        db.close()


@router.get("/installed")
def assets_installed(user: User = Depends(get_current_user)):
    """当前租户已安装 Bundle 列表（含派生引用）。"""
    db = SessionLocal()
    try:
        return {"items": installed_assets(db, user.company_id)}
    finally:
        db.close()


@router.get("/installed-nav")
def assets_installed_nav(user: User = Depends(get_current_user)):
    """侧边栏动态入口（Plugin 轻量落地）。"""
    db = SessionLocal()
    try:
        return {"items": installed_nav(db, user.company_id)}
    finally:
        db.close()


@router.get("/resolve/{bundle_code}")
def assets_resolve(bundle_code: str, user: User = Depends(get_current_user)):
    """Resolver：按 code 解析租户已装 Bundle 的派生资产。"""
    db = SessionLocal()
    try:
        r = resolve_bundle(db, user.company_id, bundle_code)
        if not r:
            raise HTTPException(status_code=404, detail="bundle not installed")
        return r
    finally:
        db.close()
