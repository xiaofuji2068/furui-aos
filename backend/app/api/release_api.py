"""交付发布与边缘协同 API（TASK-017 / 70-03 + 80-01 + 80-02）。

Release（5 端点，对标 Apollo 的 Release/Channel/Signature）：
    GET    /api/releases                列表（?channel=）
    POST   /api/releases                建版本（含变更单 + SBOM 摘要 → 自动签名）
    GET    /api/releases/{id}           详情（回带签名校验结果）
    POST   /api/releases/{id}/promote   通道推进 draft → staging → production
    POST   /api/releases/{id}/recall    撤回（仅 promoted 可召回）

EdgeSite（4 端点，Hub-Spoke）：
    POST   /api/edge-sites/register     注册（明文 token 只在此返回一次）
    POST   /api/edge-sites/{code}/heartbeat   心跳续约 + 版本上报
    GET    /api/edge-sites              本企业站点列表
    GET    /api/edge-sites/{code}/sync  下发目标版本 manifest（Spoke 拉取）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user, require_perm
from ..db import SessionLocal
from ..models import User
from ..release import (
    IllegalTransition, create_release, get_release, heartbeat, list_releases,
    list_sites, promote_release, recall_release, register_site, sync_target,
    unregister_site,
)

router = APIRouter()


class ReleaseCreateReq(BaseModel):
    version: str
    channel: str = "draft"
    notes: str = ""
    manifest: Dict[str, Any] = {}
    sbom: List[Any] = []
    changes: List[Dict[str, Any]] = []


@router.get("/releases")
def releases_list(channel: Optional[str] = None, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        return {"items": list_releases(db, channel=channel)}
    finally:
        db.close()


@router.post("/releases")
def releases_create(req: ReleaseCreateReq,
                    user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        try:
            d = create_release(db, req.dict(), created_by_company_id=user.company_id or 1)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return d
    finally:
        db.close()


@router.get("/releases/{release_id}")
def releases_detail(release_id: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        d = get_release(db, release_id)
        if not d:
            raise HTTPException(status_code=404, detail="release not found")
        return d
    finally:
        db.close()


@router.post("/releases/{release_id}/promote")
def releases_promote(release_id: int, user: User = Depends(require_perm("tool:config"))):
    """推进通道。非法跳态（如 draft 直冲 production）返回 409 + 明确原因。"""
    db = SessionLocal()
    try:
        try:
            return promote_release(db, release_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="release not found")
        except IllegalTransition as e:
            raise HTTPException(status_code=409, detail=str(e))
    finally:
        db.close()


@router.post("/releases/{release_id}/recall")
def releases_recall(release_id: int, user: User = Depends(require_perm("tool:config"))):
    db = SessionLocal()
    try:
        try:
            return recall_release(db, release_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="release not found")
        except IllegalTransition as e:
            raise HTTPException(status_code=409, detail=str(e))
    finally:
        db.close()


class SiteRegisterReq(BaseModel):
    site_code: str
    name: str = ""
    site_type: str = "edge"
    endpoint: str = ""
    metadata: Dict[str, Any] = {}


@router.post("/edge-sites/register")
def sites_register(req: SiteRegisterReq, user: User = Depends(require_perm("tool:config"))):
    """注册边缘站点。响应里的 token 只出现这一次，请立即落自身密钥体系。"""
    db = SessionLocal()
    try:
        try:
            return register_site(db, req.dict(), company_id=user.company_id or 1)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    finally:
        db.close()


class HeartbeatReq(BaseModel):
    token: str = ""
    version: str = ""
    status: str = ""
    endpoint: str = ""


@router.post("/edge-sites/{site_code}/heartbeat")
def sites_heartbeat(site_code: str, req: HeartbeatReq,
                    user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        try:
            return heartbeat(db, site_code, req.token or None, req.dict())
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
    finally:
        db.close()


@router.delete("/edge-sites/{site_code}")
def sites_unregister(site_code: str, user: User = Depends(require_perm("tool:config"))):
    """注销站点（RLS 之外的显式归属校验）。"""
    db = SessionLocal()
    try:
        if not unregister_site(db, site_code, company_id=user.company_id):
            raise HTTPException(status_code=404, detail="site not found")
        return {"ok": True}
    finally:
        db.close()


@router.get("/edge-sites")
def sites_list(user: User = Depends(get_current_user)):
    """本企业站点列表（RLS 已隔离，再按 company_id 显式过滤一次）。"""
    db = SessionLocal()
    try:
        return {"items": list_sites(db, company_id=user.company_id)}
    finally:
        db.close()


@router.get("/edge-sites/{site_code}/sync")
def sites_sync(site_code: str, user: User = Depends(get_current_user)):
    """Spoke 拉取：返回「应运行版本」与 manifest，from/to 版本不一致即待升级。"""
    db = SessionLocal()
    try:
        try:
            return sync_target(db, site_code)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()
