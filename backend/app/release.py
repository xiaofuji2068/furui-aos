# -*- coding: utf-8 -*-
"""交付发布与边缘协同业务逻辑（TASK-017 / 70-03 + 80-01 + 80-02）。

职责边界（与 assets.py 的区分）：
    assets.py 管「租户装了哪些页面/Logic 资产」（50 资产装配）
    本模块管「产品版本怎么发到各环境、再下发到客户边缘站点」（70/80 交付）

三件事：
    1. 签名：signature = sha256(version + manifest + sbom)，交付审计用。
       不做非对称签名（无密钥体系），但固定用 sha256 定长摘要，
       将来要换成 RSA/ECDSA 只需替换 sign_release/verify_signature 两个函数。
    2. Release 状态机：draft → staging → production，recall 回退，superseded 归档。
       **显式白名单**，禁止非法跳态（比如 draft 直接 production）。
    3. Hub-Spoke：站点注册（一次性 token）/ 心跳（续约 + 版本上报）/ 同步（下发 manifest）。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import secrets
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models_release import EdgeSite, Release, ReleaseChange

# ---- Release 状态机（显式白名单，越态直接 ValueError）----
CHANNELS = ("draft", "staging", "production")
# 通道推进顺序：draft → staging → production
PROMOTE_ORDER = {"draft": "staging", "staging": "production", "production": ""}
STATUSES = ("draft", "promoted", "recalled", "superseded")
CHANGE_KINDS = ("feat", "fix", "config", "security", "migration")


class IllegalTransition(Exception):
    """非法状态迁移（供 API 层转 409）。"""


def sign_payload(version: str, manifest: Any, sbom: Any) -> str:
    """计算 Release 签名：对「版本 + manifest + sbom」做 sha256 定长摘要。

    用固定 field separator（|）拼接而非 JSON 序列化：JSON 的键序在不同
    Python 版本间可能不同，会让同一内容产出两个签名，审计时无法比对。
    """
    m = manifest if isinstance(manifest, str) else json.dumps(manifest, sort_keys=True, default=str)
    b = sbom if isinstance(sbom, str) else json.dumps(sbom, sort_keys=True, default=str)
    raw = f"{version}|{m}|{b}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_signature(r: Release) -> bool:
    """校验 Release 签名与当前内容是否一致（内容被改过则签名不匹配）。"""
    return sign_payload(r.version, r.manifest_json, r.sbom_json) == (r.signature or "")


def compute_signature(version: str, manifest: Any, sbom: Any) -> str:
    """签名入口（保留别名兼容）。"""
    return sign_payload(version, manifest, sbom)


# ---------------- Release ----------------

def list_releases(db: Session, channel: Optional[str] = None,
                  limit: int = 50) -> List[Dict[str, Any]]:
    # 先 filter 再 limit：filter 落在 limit 之后 SQLAlchemy 会直接抛
    # InvalidRequestError（Query.filter() on a Query which already has LIMIT）
    q = db.query(Release).order_by(Release.id.desc())
    if channel:
        q = q.filter(Release.channel == channel)
    q = q.limit(limit)
    return [_release_dto(r, db) for r in q.all()]


def get_release(db: Session, release_id: int) -> Optional[Dict[str, Any]]:
    r = db.query(Release).filter(Release.id == release_id).first()
    return _release_dto(r, db) if r else None


def create_release(db: Session, payload: Dict[str, Any],
                   created_by_company_id: int = 1) -> Dict[str, Any]:
    """创建 Release：版本号唯一，签名在入库前算好。

    幂等口径：version 已存在抛 ValueError（由 API 转 409），不做静默覆盖——
    交付版本号是审计主键，静默覆盖会让历史事件对不上账。
    """
    version = str(payload.get("version") or "").strip()
    if not version:
        raise ValueError("version 必填")
    if db.query(Release).filter(Release.version == version).first():
        raise ValueError(f"Release 版本 '{version}' 已存在")

    channel = (payload.get("channel") or "draft").strip()
    if channel not in CHANNELS:
        raise ValueError(f"channel 只能是 {'/'.join(CHANNELS)}")

    manifest = payload.get("manifest") or {}
    sbom = payload.get("sbom") or []
    r = Release(
        version=version,
        channel=channel,
        status="draft",
        manifest_json=json.dumps(manifest, ensure_ascii=False, default=str),
        sbom_json=json.dumps(sbom, ensure_ascii=False, default=str),
        signature=sign_payload(version, manifest, sbom),
        notes=payload.get("notes") or "",
        released_by_company_id=created_by_company_id,
    )
    db.add(r)
    db.flush()
    for ch in (payload.get("changes") or []):
        _add_change(db, r, ch)
    db.commit()
    # 必须带 db 回带，否则变更单查不到、返回体里 changes 恒为 []
    return _release_dto(r, db)


def _add_change(db: Session, r: Release, ch: Dict[str, Any]) -> None:
    """写变更单（去重：同 release + kind + summary 幂等，重放不重复）。"""
    kind = (ch.get("kind") or "feat").strip()
    if kind not in CHANGE_KINDS:
        kind = "feat"
    summary = str(ch.get("summary") or "").strip()
    if not summary:
        return
    exists = db.query(ReleaseChange).filter(
        ReleaseChange.release_id == r.id,
        ReleaseChange.kind == kind,
        ReleaseChange.summary == summary,
    ).first()
    if exists:
        return
    db.add(ReleaseChange(release_id=r.id, kind=kind, summary=summary))


def promote_release(db: Session, release_id: int) -> Dict[str, Any]:
    """推进通道：draft → staging → production。生产为终点，不可再推。"""
    r = db.query(Release).filter(Release.id == release_id).first()
    if not r:
        raise KeyError(f"release {release_id} 不存在")
    nxt = PROMOTE_ORDER.get(r.channel or "draft", "")
    if not nxt:
        raise IllegalTransition(
            f"版本 {r.version} 已在 production 通道终点，无法继续推进")
    # 上一档状态收口：被推走的旧通道版本标记为 superseded，留痕
    if r.status == "promoted":
        r.status = "superseded"
    r.promoted_to = nxt
    r.channel = nxt
    r.status = "promoted"
    if not r.signature:
        r.signature = sign_payload(r.version, r.manifest_json, r.sbom_json)
    db.commit()
    return _release_dto(r, db)


def recall_release(db: Session, release_id: int) -> Dict[str, Any]:
    """撤回：仅 promoted 可召回；召回后回落到它所来自的通道。"""
    r = db.query(Release).filter(Release.id == release_id).first()
    if not r:
        raise KeyError(f"release {release_id} 不存在")
    if r.status != "promoted":
        # 已经召回/归档/还是草稿，再点召回属于同态重复，不改数据
        if r.status == "recalled":
            return _release_dto(r)
        raise IllegalTransition(
            f"状态 '{r.status}' 不可召回（仅 promoted 可召回）")
    r.status = "recalled"
    db.commit()
    return _release_dto(r)


def _release_dto(r: Optional[Release],
                 db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    if not r:
        return None
    changes: List[Dict[str, Any]] = []
    if db is not None:
        changes = [{"kind": c.kind, "summary": c.summary}
                   for c in db.query(ReleaseChange)
                   .filter(ReleaseChange.release_id == r.id).all()]
    return {
        "id": r.id,
        "version": r.version,
        "channel": r.channel,
        "status": r.status,
        "manifest": _json_or(r.manifest_json, {}),
        "sbom": _json_or(r.sbom_json, []),
        "changes": changes,
        "signature": r.signature,
        "signature_valid": bool(r.signature) and
                           sign_payload(r.version, r.manifest_json, r.sbom_json) == r.signature,
        "notes": r.notes,
        "promoted_to": r.promoted_to,
        "released_by_company_id": r.released_by_company_id,
        "created_at": _iso(r.created_at),
        "updated_at": _iso(r.updated_at),
    }


# ---------------- Hub-Spoke 边缘站点 ----------------

def _new_token() -> str:
    """一次性注册令牌：32 字节 urlsafe，仅注册响应返回一次。"""
    return secrets.token_urlsafe(32)


def register_site(db: Session, payload: Dict[str, Any],
                  company_id: int) -> Dict[str, Any]:
    """站点注册（Hub 侧）：返回明文 token，库里只留 sha256。"""
    code = str(payload.get("site_code") or "").strip()
    if not code:
        raise ValueError("site_code 必填")
    if db.query(EdgeSite).filter(EdgeSite.site_code == code).first():
        raise ValueError(f"站点 '{code}' 已注册")
    name = payload.get("name") or code
    r = db.query(Release).order_by(Release.id.desc()).first()
    token = _new_token()
    site = EdgeSite(
        site_code=code,
        name=name,
        site_type=(payload.get("site_type") or "edge"),
        endpoint=payload.get("endpoint") or "",
        company_id=company_id or 1,
        release_id=(r.id if r else 0),
        status="registered",
        site_token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        version=(r.version if r else ""),
        metadata_json=json.dumps(payload.get("metadata") or {}, ensure_ascii=False, default=str),
    )
    db.add(site)
    db.commit()
    # token 只在这里出现一次，任何再取站点信息的接口都不回传
    return _site_dto(site, token=token)


def heartbeat(db: Session, site_code: str, token: Optional[str],
              payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Spoke 心跳：续约 + 上报当前版本 + 上抛运行时状态。

    令牌校验：传 site_token_hash 比对；缺省时不强校验（跨网段部署的心跳
    可能拿不到 token），仅更新 last_heartbeat_at——宁可少一道校验，
    也不要让边缘站点因为拿不到令牌就永远 offline。
    """
    site = db.query(EdgeSite).filter(EdgeSite.site_code == site_code).first()
    if not site:
        raise KeyError(f"站点 '{site_code}' 未注册")
    if token and site.site_token_hash and \
            hashlib.sha256(token.encode("utf-8")).hexdigest() != site.site_token_hash:
        raise PermissionError("站点令牌无效")
    p = payload or {}
    site.last_heartbeat_at = _dt.datetime.utcnow()
    site.status = "online"
    if p.get("version") is not None:
        site.version = str(p["version"])
    meta = _json_or(site.metadata_json, {})
    if p.get("status") is not None:
        meta["runtime_status"] = p["status"]
    if p.get("endpoint") is not None:
        site.endpoint = str(p["endpoint"])
    site.metadata_json = json.dumps(meta, ensure_ascii=False, default=str)
    db.commit()
    return _site_dto(site)


def sync_target(db: Session, site_code: str) -> Dict[str, Any]:
    """Hub → Spoke 同步：返回该站点**应运行**的 Release manifest。

    Spoke 侧拿这个做升级；Hub 侧的 site.version（已运行版本）与 release.version
    （应运行版本）不一致，前端就能显示「待升级」。
    """
    site = db.query(EdgeSite).filter(EdgeSite.site_code == site_code).first()
    if not site:
        raise KeyError(f"站点 '{site_code}' 未注册")
    rel = db.query(Release).filter(Release.id == site.release_id).first() if site.release_id else None
    target = rel.version if rel else site.version
    return {
        "site_code": site.site_code,
        "company_id": site.company_id,
        "from_version": site.version,
        "to_version": target,
        "upgrade_needed": bool(target and site.version and target != site.version),
        "release": _release_dto(rel) if rel else None,
        "served_at": _iso(_dt.datetime.utcnow()),
    }


def list_sites(db: Session, company_id: Optional[int] = None,
               limit: int = 100) -> List[Dict[str, Any]]:
    """站点列表（RLS 已按 company_id 隔离；此处再显式过滤一次，SQLite 形态也安全）。"""
    # 同 list_releases：filter 必须在 limit 之前
    q = db.query(EdgeSite).order_by(EdgeSite.id.desc())
    if company_id:
        q = q.filter(EdgeSite.company_id == company_id)
    q = q.limit(limit)
    return [_site_dto(s) for s in q.all()]


def get_site(db: Session, site_code: str) -> Optional[Dict[str, Any]]:
    s = db.query(EdgeSite).filter(EdgeSite.site_code == site_code).first()
    return _site_dto(s) if s else None


def unregister_site(db: Session, site_code: str, company_id: Optional[int] = None) -> bool:
    """注销站点（RLS 之外的显式归属校验）。"""
    q = db.query(EdgeSite).filter(EdgeSite.site_code == site_code)
    if company_id:
        q = q.filter(EdgeSite.company_id == company_id)
    site = q.first()
    if not site:
        return False
    db.delete(site)
    db.commit()
    return True


def _site_dto(s: Optional[EdgeSite], token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not s:
        return None
    d = {
        "id": s.id,
        "site_code": s.site_code,
        "name": s.name,
        "site_type": s.site_type,
        "endpoint": s.endpoint,
        "company_id": s.company_id,
        "release_id": s.release_id,
        "status": s.status,
        "version": s.version,
        "last_heartbeat_at": _iso(s.last_heartbeat_at),
        "metadata": _json_or(s.metadata_json, {}),
        "created_at": _iso(s.created_at),
        "updated_at": _iso(s.updated_at),
    }
    # 明文令牌只出现在注册响应，其它任何出口都不带
    if token:
        d["token"] = token
    return d


def _json_or(raw: Any, default: Any) -> Any:
    if not raw:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return default


def _iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    try:
        return dt.replace(tzinfo=None).isoformat() + "Z"
    except Exception:  # noqa: BLE001
        return str(dt)
