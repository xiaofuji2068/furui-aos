"""管理后台数据接口：数据管理 / 系统集成 / 权限管理 / 模型管理 / 日志中心 / 设置中心。

返回统一的"渲染指令"结构（kind: table/cards/matrix/settings），前端 AdminPage 据此渲染，
避免为 6 个页各写一套组件。业务数据目前为内存 mock，结构与真实系统对齐。

鉴权（60-03 治理）：本模块全部端点要求登录 + 对应权限点；
未带 token 一律 401，权限不足 403（前端路由守卫只是体验层，后端为权威）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user, require_perm
from ..config import LLM_PROVIDERS, settings
from ..models import User
from ..store_data_sources import list_sources


router = APIRouter()

SLUGS = ["data", "integration", "permission", "model", "logs", "settings"]

# admin 各页所需权限点（与前端 Sidebar 菜单守卫一致，后端权威校验）
_SLUG_PERM = {
    "data": "datasource:view",
    "integration": "datasource:view",
    "permission": "role:view",
    "model": "tool:view",
    "logs": "log:view",
    "settings": "company:manage",
}

# 设置项内存暂存（演示用，重启即丢）
_SETTINGS: Dict[str, Any] = {}

# ---------------- 模型 API Key 配置（页面可配置，写 .env + 热更新） ----------------

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent   # backend/
_ENV_FILE = _BACKEND_DIR / ".env"


# ---------------- 各页 payload ----------------

def _data_payload() -> Dict[str, Any]:
    rows = []
    for s in list_sources():
        rows.append({
            "id": s["id"],
            "name": s["name"],
            "category": s.get("category", ""),
            "type": s.get("type", ""),
            "status": s.get("status", ""),
            "last_sync": s.get("last_sync", ""),
            "records": s.get("records", ""),
        })
    return {
        "slug": "data",
        "title": "数据管理",
        "desc": "管理接入企业 AI 操作系统的数据源与连接状态。",
        "kind": "table",
        "actions": True,
        "columns": [
            {"key": "name", "label": "数据源"},
            {"key": "category", "label": "类别"},
            {"key": "type", "label": "类型"},
            {"key": "status", "label": "状态"},
            {"key": "last_sync", "label": "最后同步"},
            {"key": "records", "label": "记录数"},
        ],
        "rows": rows,
    }


def _integration_payload() -> Dict[str, Any]:
    cards = []
    for s in list_sources():
        cards.append({
            "name": s["name"],
            "icon": s.get("icon", "🗄"),
            "status": s.get("status", ""),
            "desc": s.get("desc", ""),
            "health": s.get("health", 0),
            "type": s.get("type", ""),
        })
    return {
        "slug": "integration",
        "title": "系统集成",
        "desc": "已与下列企业系统集成，AI 员工可调用其数据与能力。",
        "kind": "cards",
        "cards": cards,
    }


def _permission_payload() -> Dict[str, Any]:
    roles = ["管理员", "业务负责人", "数据分析师", "运维工程师"]
    perms = ["员工管理", "数据源配置", "权限变更", "知识写入", "工单创建", "模型调用", "日志查看"]
    matrix = {
        "员工管理":   {"管理员": True,  "业务负责人": False, "数据分析师": False, "运维工程师": False},
        "数据源配置": {"管理员": True,  "业务负责人": False, "数据分析师": True,  "运维工程师": True},
        "权限变更":   {"管理员": True,  "业务负责人": False, "数据分析师": False, "运维工程师": False},
        "知识写入":   {"管理员": True,  "业务负责人": True,  "数据分析师": True,  "运维工程师": False},
        "工单创建":   {"管理员": True,  "业务负责人": True,  "数据分析师": False, "运维工程师": True},
        "模型调用":   {"管理员": True,  "业务负责人": True,  "数据分析师": True,  "运维工程师": True},
        "日志查看":   {"管理员": True,  "业务负责人": False, "数据分析师": True,  "运维工程师": True},
    }
    return {
        "slug": "permission",
        "title": "权限管理",
        "desc": "基于角色的访问控制（RBAC）矩阵。",
        "kind": "matrix",
        "roles": roles,
        "perms": perms,
        "matrix": matrix,
    }


def _model_payload() -> Dict[str, Any]:
    active = LLM_PROVIDERS.get(settings.active_provider, {})
    cards = []
    for pid in LLM_PROVIDERS:
        meta = LLM_PROVIDERS[pid]
        cards.append({
            "name": meta["label"],
            "provider": f"{meta['base_url'] or '自定义接入点'}",
            "status": "connected" if settings.active_provider == pid else
                      ("ready" if getattr(settings, f"{pid}_key", "") else "disconnected"),
            "desc": f"模型 {meta['model_name'] or '（待填）'} · "
                    f"{'当前对话模型' if settings.active_provider == pid else ('已配置 Key' if getattr(settings, f'{pid}_key', '') else '未配置 Key')}",
        })
    cards.append({
        "name": "DashScope 语义模型",
        "provider": settings.dashscope_base_url,
        "status": "connected" if settings.embedding_enabled else "disconnected",
        "desc": f"模型 {settings.embedding_model} · "
                f"{'语义检索已启用' if settings.embedding_enabled else '未配置 Key（本地哈希兜底）'}",
    })
    return {
        "slug": "model",
        "title": "模型管理",
        "desc": f"当前 LLM 状态：{settings.llm_enabled and settings.model_name or 'Mock 模式（未配置 API Key）'}",
        "kind": "cards",
        "note": f"当前对话模型：{settings.model_name}（{settings.active_provider}）" if settings.llm_enabled
               else "未启用真实模型（可在下方配置任一提供方 Key 并启用）",
        "cards": cards,
    }


def _logs_payload(limit: int = 50) -> Dict[str, Any]:
    """日志中心：读取 audit_logs 真实审计记录（空表时给出引导提示）。"""
    from ..db import SessionLocal
    from ..models_ai import AuditLog

    db = SessionLocal()
    try:
        rows_raw = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    finally:
        db.close()

    _LEVEL = {"success": "info", "denied": "warn", "failed": "error"}
    rows = []
    for a in rows_raw:
        event = a.action + (f"「{a.target}」" if a.target else "")
        if a.detail and a.detail not in ("{}", ""):
            try:
                import json as _json
                detail = _json.loads(a.detail)
                extra = detail.get("summary") or detail.get("note") or ""
                if extra:
                    event = f"{event} · {extra}"
            except Exception:  # noqa: BLE001
                pass
        rows.append({
            "time": a.created_at.strftime("%m-%d %H:%M") if a.created_at else "",
            "level": _LEVEL.get(a.result, "info"),
            "actor": a.actor_name or {"user": "用户", "agent": "AI 员工", "system": "系统"}.get(a.actor_type, a.actor_type),
            "event": event,
        })
    return {
        "slug": "logs",
        "title": "日志中心",
        "desc": "操作与调用审计日志（来自 audit_logs 真实记录）。",
        "kind": "table",
        "columns": [
            {"key": "time", "label": "时间"},
            {"key": "level", "label": "级别"},
            {"key": "actor", "label": "操作方"},
            {"key": "event", "label": "事件"},
        ],
        "rows": rows,
        "note": f"共显示最近 {len(rows)} 条" if rows else "暂无审计记录：触发一次 Agent 调用 / 审批 / 知识发布后这里会出现真实日志",
    }


def _load_settings_db(company_id: int | None) -> Dict[str, Any]:
    """从 system_settings 表读取该租户已保存的设置（无则空）。"""
    if company_id is None:
        return {}
    try:
        from ..db import SessionLocal
        from ..models import SystemSetting
        db = SessionLocal()
        try:
            rows = db.query(SystemSetting).filter(SystemSetting.company_id == company_id).all()
            return {r.key: r.value for r in rows}
        finally:
            db.close()
    except Exception:  # noqa: BLE001 表未就绪/迁移未跑时回退空
        return {}


def _settings_payload(company_id: int | None = None) -> Dict[str, Any]:
    defaults = [
        {"key": "system_name", "label": "系统名称", "value": settings.system_name, "type": "text"},
        {"key": "org_name", "label": "所属组织", "value": "傅瑞科技", "type": "text"},
        {"key": "llm_enabled", "label": "启用真实大模型", "value": settings.llm_enabled, "type": "toggle"},
        {"key": "model_name", "label": "模型名称", "value": settings.model_name, "type": "text"},
        {"key": "auto_confirm", "label": "允许 AI 自动执行写入", "value": False, "type": "toggle"},
    ]
    saved = _load_settings_db(company_id)
    for f in defaults:
        if f["key"] in saved:
            v = saved[f["key"]]
            if f["type"] == "toggle":
                f["value"] = str(v).lower() in ("1", "true", "yes", "on")
            else:
                f["value"] = v
    return {
        "slug": "settings",
        "title": "设置中心",
        "desc": "系统基础配置。",
        "kind": "settings",
        "fields": defaults,
    }


_BUILDERS = {
    "data": _data_payload,
    "integration": _integration_payload,
    "permission": _permission_payload,
    "model": _model_payload,
    "logs": _logs_payload,
    "settings": _settings_payload,
}


# ---------------- 审计查询（60-03 治理 / 90-01 可观测） ----------------
# 注意：必须在 GET /admin/{slug} 之前注册，避免被动态路由抢占

@router.get("/admin/audit")
def admin_audit(actor: str = "", action: str = "",
                from_: str = "", to: str = "", limit: int = 50,
                _auth: User = Depends(require_perm("log:view"))):
    """审计日志查询：按 操作方 / 动作 / 时间窗 过滤（图谱 60-03 审计查询 API）。"""
    from datetime import datetime

    from ..db import SessionLocal
    from ..models_ai import AuditLog

    _LEVEL = {"success": "info", "denied": "warn", "failed": "error"}
    db = SessionLocal()
    try:
        q = db.query(AuditLog)
        if actor.strip():
            q = q.filter(AuditLog.actor_name.like(f"%{actor.strip()}%"))
        if action.strip():
            q = q.filter(AuditLog.action.like(f"%{action.strip()}%"))
        if from_.strip():
            try:
                q = q.filter(AuditLog.created_at >= datetime.strptime(from_.strip(), "%Y-%m-%d"))
            except ValueError:
                raise HTTPException(status_code=400, detail="from 需为 YYYY-MM-DD")
        if to.strip():
            try:
                q = q.filter(AuditLog.created_at < datetime.strptime(to.strip(), "%Y-%m-%d"))
            except ValueError:
                raise HTTPException(status_code=400, detail="to 需为 YYYY-MM-DD")
        total = q.count()
        rows = q.order_by(AuditLog.id.desc()).limit(min(max(limit, 1), 200)).all()
    finally:
        db.close()

    items = [{
        "id": a.id,
        "time": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
        "level": _LEVEL.get(a.result, "info"),
        "actor": a.actor_name or a.actor_type,
        "action": a.action,
        "target": a.target,
        "result": a.result,
        "detail": a.detail,
    } for a in rows]
    return {"total": total, "items": items, "filters": {
        "actor": actor, "action": action, "from": from_, "to": to}}


@router.get("/admin/receipts")
def admin_receipts(tool: str = "", limit: int = 50,
                   _auth: User = Depends(require_perm("log:view"))):
    """动作凭证查询（图谱 Receipt / 20-05）：全部 Agent 真实执行的留痕（哈希可复算）。"""
    from ..db import SessionLocal
    from ..models_ai import ActionReceipt

    db = SessionLocal()
    try:
        q = db.query(ActionReceipt)
        if tool.strip():
            q = q.filter(ActionReceipt.tool_name.like(f"%{tool.strip()}%"))
        total = q.count()
        rows = q.order_by(ActionReceipt.id.desc()).limit(min(max(limit, 1), 200)).all()
    finally:
        db.close()
    return {"total": total, "items": [{
        "id": r.id,
        "time": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
        "tool": r.tool_name,
        "approval_id": r.approval_id,
        "params_hash": r.params_hash,
        "result_hash": r.result_hash,
        "actor_type": r.actor_type,
        "actor_id": r.actor_id,
    } for r in rows]}


# ---------------- EvalContract 评估合同（图谱 #5：admin 配置生效） ----------------

class EvalContractReq(BaseModel):
    """评估合同配置（新增/更新按 name 幂等 upsert）。"""
    name: str
    description: str = ""
    metric: str = "accuracy"          # accuracy / fairness / latency
    operator: str = "gte"             # gte / lte
    threshold: float = 0.9
    enabled: bool = True


@router.get("/admin/eval-contracts")
def list_eval_contracts(_auth: User = Depends(require_perm("log:view"))):
    """评估合同一览（图谱 #5）。"""
    from ..db import SessionLocal
    from ..models_ai import EvalContract

    db = SessionLocal()
    try:
        rows = (db.query(EvalContract)
                .order_by(EvalContract.metric, EvalContract.id)
                .all())
    finally:
        db.close()
    return {"items": [{
        "id": r.id, "name": r.name, "description": r.description,
        "metric": r.metric, "operator": r.operator,
        "threshold": r.threshold, "enabled": bool(r.enabled),
    } for r in rows]}


@router.post("/admin/eval-contracts")
def upsert_eval_contract(req: EvalContractReq,
                         _auth: User = Depends(require_perm("tool:config"))):
    """创建/更新评估合同（按 name 幂等）；enabled=false 即停用该红线。"""
    from ..db import SessionLocal
    from ..models_ai import EvalContract

    if req.metric not in {"accuracy", "fairness", "latency"}:
        raise HTTPException(status_code=400, detail="metric 仅支持 accuracy/fairness/latency")
    if req.operator not in {"gte", "lte"}:
        raise HTTPException(status_code=400, detail="operator 仅支持 gte/lte")
    if not (0 <= req.threshold <= 1000):
        raise HTTPException(status_code=400, detail="threshold 需在 0~1000 之间")

    db = SessionLocal()
    try:
        row = db.query(EvalContract).filter(EvalContract.name == req.name).first()
        if row:
            row.description = req.description
            row.metric = req.metric
            row.operator = req.operator
            row.threshold = req.threshold
            row.enabled = req.enabled
        else:
            row = EvalContract(company_id=_auth.company_id or 1, name=req.name,
                               description=req.description,
                               metric=req.metric, operator=req.operator,
                               threshold=req.threshold, enabled=req.enabled)
            db.add(row)
        db.commit()
        db.refresh(row)
    finally:
        db.close()
    return {"ok": True, "contract": {
        "id": row.id, "name": row.name, "description": row.description,
        "metric": row.metric, "operator": row.operator,
        "threshold": row.threshold, "enabled": bool(row.enabled),
    }}


# ---------------- SecretRef / Keychain 密钥引用（60-04） ----------------

class SecretUpsertReq(BaseModel):
    """写入/更新一个密钥引用（脱敏存储，不回显明文）。"""
    ref_key: str
    value: str
    kind: str = "custom"          # llm / datasource / webhook / custom
    pii_level: str = "none"       # none / low / high
    retention_days: int = 365
    region: str = "cn"
    note: str = ""


@router.get("/admin/secrets")
def admin_secrets(_auth: User = Depends(require_perm("tool:config"))):
    """密钥引用一览（60-04）：只返回脱敏视图，绝不返回明文。"""
    from ..db import SessionLocal
    from ..store_secrets import list_secrets

    db = SessionLocal()
    try:
        items = list_secrets(db, _auth.company_id)
    finally:
        db.close()
    return {"items": items, "count": len(items),
            "note": "密钥只写不读：列表仅显示是否已配置与脱敏前缀；明文绝不进入任何响应/日志"}


@router.post("/admin/secrets")
def upsert_secret(req: SecretUpsertReq,
                  user: User = Depends(require_perm("tool:config"))):
    """写入/更新密钥引用（按 ref_key 幂等）。PII/Retention/Region 一并标注。"""
    from ..db import SessionLocal
    from ..store_secrets import set_secret

    db = SessionLocal()
    try:
        row = set_secret(db, user.company_id, req.ref_key, req.value, kind=req.kind,
                         pii_level=req.pii_level, retention_days=req.retention_days,
                         region=req.region, note=req.note, actor_name=user.name)
        return {"ok": True, "ref_key": row.ref_key,
                "masked": (row.secret_value[:4] + "****") if row.secret_value else "",
                "pii_level": row.pii_level, "retention_days": row.retention_days,
                "region": row.region}
    finally:
        db.close()


@router.delete("/admin/secrets/{ref_key}")
def remove_secret(ref_key: str,
                  user: User = Depends(require_perm("tool:config"))):
    """删除密钥引用（幂等）。"""
    from ..db import SessionLocal
    from ..store_secrets import delete_secret

    db = SessionLocal()
    try:
        delete_secret(db, user.company_id, ref_key, actor_name=user.name)
    finally:
        db.close()
    return {"ok": True, "ref_key": ref_key}


@router.post("/admin/secrets/migrate")
def migrate_secrets(user: User = Depends(require_perm("tool:config"))):
    """把 backend/.env 中已配置的 LLM Key 幂等迁移进 Keychain。"""
    from ..db import SessionLocal
    from ..store_secrets import migrate_env_to_keychain

    db = SessionLocal()
    try:
        return migrate_env_to_keychain(db, user.company_id, actor_name=user.name)
    finally:
        db.close()

# ---------------- 路由 ----------------

@router.get("/admin/{slug}")
def admin_page(slug: str, user: User = Depends(get_current_user)):
    if slug not in _BUILDERS:
        raise HTTPException(status_code=404, detail=f"unknown admin page: {slug}")
    need = _SLUG_PERM[slug]
    if not user.has_perm(need):
        raise HTTPException(status_code=403, detail=f"缺少权限：{need}")
    if slug == "settings":
        return _settings_payload(user.company_id)
    return _BUILDERS[slug]()


class SettingsReq(BaseModel):
    fields: List[dict] = []


@router.post("/admin/settings")
def save_settings(req: SettingsReq, user: User = Depends(require_perm("company:manage"))):
    """保存设置到 system_settings 表（按租户幂等 upsert，重启不丢）。"""
    from ..db import SessionLocal
    from ..models import SystemSetting

    db = SessionLocal()
    try:
        for f in req.fields:
            key = str(f.get("key", ""))
            if not key:
                continue
            value = "" if f.get("value") is None else str(f.get("value"))
            row = db.query(SystemSetting).filter(
                SystemSetting.company_id == user.company_id,
                SystemSetting.key == key).first()
            if row:
                row.value = value
            else:
                db.add(SystemSetting(company_id=user.company_id, key=key, value=value))
        db.commit()
    finally:
        db.close()
    return {"ok": True, "persisted": True}


# ---------------- 模型 API Key 配置（多提供方：DeepSeek / Kimi / 通义 / GLM / OpenAI / 自定义 + DashScope embedding） ----------------

# provider id -> .env 键名 / settings 字段名
_LLM_ENV_KEY = {
    "deepseek": "DEEPSEEK_API_KEY",
    "kimi": "KIMI_API_KEY",
    "qwen": "QWEN_API_KEY",
    "glm": "GLM_API_KEY",
    "openai": "OPENAI_API_KEY",
    "custom": "CUSTOM_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
}
_LLM_SETTINGS_FIELD = {
    "deepseek": "deepseek_key",
    "kimi": "kimi_key",
    "qwen": "qwen_key",
    "glm": "glm_key",
    "openai": "openai_key",
    "custom": "custom_key",
    "dashscope": "dashscope_api_key",
}


class KeysReq(BaseModel):
    provider: str                    # deepseek|kimi|qwen|glm|openai|custom|dashscope
    api_key: str = ""                # 留空 = 不修改
    set_active: bool = False         # 设为当前对话模型（仅对话提供方生效）
    custom_base_url: str = ""        # provider=custom 时填写
    custom_model_name: str = ""      # provider=custom 时填写


class TestReq(BaseModel):
    provider: str
    api_key: str = ""                # 留空 = 用已保存的 key 测试


def _read_env_file() -> str:
    if _ENV_FILE.exists():
        return _ENV_FILE.read_text(encoding="utf-8", errors="replace")
    return ""


def _write_env_key(key_name: str, value: str) -> None:
    """写入或替换 .env 中的 KEY=VALUE 行（UTF-8 无 BOM，保留其他行与注释）。"""
    lines = _read_env_file().splitlines()
    prefix = f"{key_name}="
    found = False
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped.startswith(prefix) or stripped.startswith(f"{key_name} ="):
            lines[i] = f"{key_name}={value}"
            found = True
            break
    if not found:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"{key_name}={value}")
    _ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _provider_payload(pid: str) -> Dict[str, Any]:
    meta = LLM_PROVIDERS[pid]
    field = _LLM_SETTINGS_FIELD[pid]
    has = bool(getattr(settings, field, "") or "")
    if pid == "custom":
        model_name = settings.custom_model_name or "（待填）"
        base_url = settings.custom_base_url or "（待填）"
    else:
        model_name = meta["model_name"]
        base_url = meta["base_url"]
    return {
        "id": pid,
        "label": meta["label"],
        "model_name": model_name,
        "base_url": base_url,
        "has_key": has,
        "active": settings.active_provider == pid,
    }


def _keys_state() -> Dict[str, Any]:
    providers = [_provider_payload(pid) for pid in LLM_PROVIDERS]
    return {
        "active": settings.active_provider,
        "providers": providers,
        "llm_enabled": settings.llm_enabled,
        "active_model": f"{settings.model_name}（{settings.active_provider}）" if settings.llm_enabled else "未启用（Mock）",
        "embedding": {
            "model": settings.embedding_model,
            "has_key": bool(settings.dashscope_api_key),
            "enabled": settings.embedding_enabled,
        },
        "note": "密钥只写不读，仅返回配置状态；保存后立即生效，无需重启。",
    }


@router.get("/admin/model/keys")
def model_keys(_auth: User = Depends(require_perm("tool:config"))):
    """查询各模型提供方配置状态（不返回任何明文）。"""
    return _keys_state()


@router.post("/admin/model/keys")
def save_model_keys(req: KeysReq, user: User = Depends(require_perm("tool:config"))):
    """保存某提供方 API Key：写入 backend/.env 并热更新；留空 key 不覆盖；可顺带设为当前对话模型。"""
    provider = req.provider.lower().strip()
    if provider not in _LLM_ENV_KEY:
        raise HTTPException(status_code=400, detail=f"未知提供方：{provider}")

    saved: List[str] = []
    if req.api_key.strip():
        env_key = _LLM_ENV_KEY[provider]
        field = _LLM_SETTINGS_FIELD[provider]
        _write_env_key(env_key, req.api_key.strip())
        setattr(settings, field, req.api_key.strip())   # 热更新，无需重启
        saved.append(provider)
        # TASK-013 SecretRef：同步写入 Keychain（幂等；失败不阻断 .env 主流程）
        try:
            from ..db import SessionLocal
            from ..store_secrets import set_secret
            _db = SessionLocal()
            try:
                set_secret(_db, user.company_id, f"llm:{provider}",
                           req.api_key.strip(), kind="llm",
                           pii_level="high", retention_days=365, region="cn",
                           note="synced from admin model keys", actor_name=user.name)
            finally:
                _db.close()
        except Exception:  # noqa: BLE001  Keychain 写入失败不阻断配置保存
            pass

    if provider == "custom":
        if req.custom_base_url.strip():
            _write_env_key("CUSTOM_BASE_URL", req.custom_base_url.strip())
            settings.custom_base_url = req.custom_base_url.strip()
            saved.append("custom_base_url")
        if req.custom_model_name.strip():
            _write_env_key("CUSTOM_MODEL_NAME", req.custom_model_name.strip())
            settings.custom_model_name = req.custom_model_name.strip()
            saved.append("custom_model_name")

    if req.set_active and provider != "dashscope":
        _write_env_key("ACTIVE_LLM_PROVIDER", provider)
        settings.active_llm_provider = provider
        saved.append("active")

    return {"ok": True, "saved": saved, **_keys_state()}


@router.post("/admin/model/keys/test")
async def test_model_key(req: TestReq, _auth: User = Depends(require_perm("tool:config"))):
    """测试模型 API 连通性：优先用请求里传入的 key，留空用已保存的 key。"""
    provider = req.provider.lower().strip()
    if provider not in _LLM_ENV_KEY:
        raise HTTPException(status_code=400, detail=f"未知提供方：{provider}")

    field = _LLM_SETTINGS_FIELD[provider]
    api_key = req.api_key.strip() or getattr(settings, field, "") or ""
    if not api_key:
        raise HTTPException(status_code=400, detail="未提供 API Key，请先填写或保存")

    if provider == "dashscope":
        url = settings.dashscope_base_url.rstrip("/") + "/embeddings"
        payload = {"model": settings.embedding_model, "input": "ping"}
    else:
        if provider == "custom":
            base_url = settings.custom_base_url
            model = settings.custom_model_name
            if not base_url or not model:
                raise HTTPException(status_code=400, detail="自定义提供方需先填写 base_url 与模型名")
        else:
            base_url = LLM_PROVIDERS[provider]["base_url"]
            model = LLM_PROVIDERS[provider]["model_name"]
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            return {"ok": True, "provider": provider, "status": resp.status_code}
        return {"ok": False, "provider": provider, "status": resp.status_code,
                "error": resp.text[:200]}
    except httpx.HTTPError as e:  # noqa: BLE001
        return {"ok": False, "provider": provider, "error": f"网络错误：{e.__class__.__name__}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "provider": provider, "error": f"测试异常：{e}"}


# ---------------- 模型 Catalog（30-02 模型纳管：展示元数据 + 切换默认模型） ----------------

@router.get("/admin/models/catalog")
def models_catalog(_auth: User = Depends(require_perm("tool:view"))):
    """模型 Catalog：各提供方接入点 / 模型 / 上下文 / 价格 / 配置状态（30-02 Catalog + Route）。"""
    providers = []
    for pid in LLM_PROVIDERS:
        meta = LLM_PROVIDERS[pid]
        has_key = bool(getattr(settings, _LLM_SETTINGS_FIELD.get(pid, ""), "") or "")
        if pid == "custom":
            model_name = settings.custom_model_name or "（待填）"
            base_url = settings.custom_base_url or "（待填）"
        else:
            model_name = meta["model_name"]
            base_url = meta["base_url"]
        providers.append({
            "id": pid,
            "label": meta["label"],
            "base_url": base_url,
            "model_name": model_name,
            "context_window": meta.get("context_window", "—"),
            "price_per_1k": meta.get("price_per_1k", "—"),
            "has_key": has_key,
            "active": settings.active_provider == pid,
        })
    return {
        "active_provider": settings.active_provider,
        "active_model": f"{settings.model_name}（{settings.active_provider}）" if settings.llm_enabled else "未启用（Mock）",
        "llm_enabled": settings.llm_enabled,
        "providers": providers,
        "embedding": {
            "model": settings.embedding_model,
            "base_url": settings.dashscope_base_url,
            "has_key": bool(settings.dashscope_api_key),
            "enabled": settings.embedding_enabled,
        },
    }
