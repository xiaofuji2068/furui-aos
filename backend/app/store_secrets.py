# -*- coding: utf-8 -*-
"""SecretRef / Keychain 存储（60-04 密钥引用）。

职责：
- 密钥以 SecretEntry 落库（按租户 company_id 隔离 + RLS），对外只暴露脱敏视图。
- 提供 set / get / delete / list / migrate 幂等接口，业务代码通过 ref_key 解析。
- `resolve_llm_key`：LLM Provider Key 解析链 —— Keychain 优先，.env（settings）兜底，
  让「告别 .env 明文」可平滑落地（迁移后 Keychain 即权威，.env 仅为兼容回退）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .db import SessionLocal
from .models_ai import SecretEntry


# LLM Provider -> (ref_key, .env 键名, settings 字段名)（migrate 与 resolve 共用）
_LLM_REFS = {
    "deepseek": ("llm:deepseek", "DEEPSEEK_API_KEY", "deepseek_key"),
    "kimi": ("llm:kimi", "KIMI_API_KEY", "kimi_key"),
    "qwen": ("llm:qwen", "QWEN_API_KEY", "qwen_key"),
    "glm": ("llm:glm", "GLM_API_KEY", "glm_key"),
    "openai": ("llm:openai", "OPENAI_API_KEY", "openai_key"),
    "custom": ("llm:custom", "CUSTOM_API_KEY", "custom_key"),
    "dashscope": ("llm:dashscope", "DASHSCOPE_API_KEY", "dashscope_api_key"),
}


def mask_secret(value: str, keep: int = 4) -> str:
    """脱敏：保留前 keep 个字符，其余掩码为 *（短值整体掩码）。"""
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= keep + 4:
        return "*" * min(len(v), 8)
    return v[:keep] + "*" * min(len(v) - keep, 12) + f"({len(v)}位)"


# ---------------- 基础 CRUD（均按 company_id 隔离） ----------------

def set_secret(db, company_id: int, ref_key: str, value: str, *,
               kind: str = "custom", pii_level: str = "none",
               retention_days: int = 365, region: str = "cn",
               note: str = "", actor_name: str = "") -> SecretEntry:
    """幂等 upsert：同一租户同一 ref_key 覆盖旧值。写审计（不回显明文）。"""
    ref_key = ref_key.strip()
    if not ref_key:
        raise ValueError("ref_key 不能为空")
    if pii_level not in ("none", "low", "high"):
        raise ValueError("pii_level 仅支持 none/low/high")
    row = (db.query(SecretEntry)
           .filter(SecretEntry.company_id == company_id,
                   SecretEntry.ref_key == ref_key)
           .first())
    if row:
        row.secret_value = value
        row.kind = kind
        row.pii_level = pii_level
        row.retention_days = retention_days
        row.region = region
        row.note = note
    else:
        row = SecretEntry(company_id=company_id, ref_key=ref_key, secret_value=value,
                          kind=kind, pii_level=pii_level, retention_days=retention_days,
                          region=region, note=note)
        db.add(row)
    db.commit()
    db.refresh(row)

    from .models_ai import write_audit
    write_audit(db, action="secret.set", actor_type="user", actor_name=actor_name,
                company_id=company_id, target=ref_key,
                detail={"kind": kind, "pii_level": pii_level,
                        "retention_days": retention_days, "region": region},
                result="success")
    db.commit()
    return row


def get_secret(db, company_id: int, ref_key: str) -> Optional[str]:
    """按引用取明文（仅内部解析使用，严禁直接回传 API 响应）。"""
    row = (db.query(SecretEntry)
           .filter(SecretEntry.company_id == company_id,
                   SecretEntry.ref_key == ref_key.strip())
           .first())
    return row.secret_value if row else None


def delete_secret(db, company_id: int, ref_key: str, actor_name: str = "") -> bool:
    """删除密钥（幂等：不存在也返回 True）。写审计。"""
    row = (db.query(SecretEntry)
           .filter(SecretEntry.company_id == company_id,
                   SecretEntry.ref_key == ref_key.strip())
           .first())
    if row:
        db.delete(row)
        db.commit()
        from .models_ai import write_audit
        write_audit(db, action="secret.delete", actor_type="user", actor_name=actor_name,
                    company_id=company_id, target=ref_key.strip(), result="success")
        db.commit()
    return True


def list_secrets(db, company_id: int) -> List[Dict[str, Any]]:
    """脱敏视图：不返回明文，只返回 has_value + 掩码 + 治理标注。"""
    rows = (db.query(SecretEntry)
            .filter(SecretEntry.company_id == company_id)
            .order_by(SecretEntry.ref_key)
            .all())
    return [{
        "ref_key": r.ref_key,
        "kind": r.kind,
        "has_value": bool(r.secret_value),
        "masked": mask_secret(r.secret_value),
        "pii_level": r.pii_level,
        "retention_days": r.retention_days,
        "region": r.region,
        "note": r.note,
        "updated_at": r.updated_at.strftime("%Y-%m-%d %H:%M:%S") if r.updated_at else "",
    } for r in rows]


# ---------------- LLM Key 解析链（Keychain 优先，.env 兜底） ----------------

def resolve_llm_key(provider: str, db=None, company_id: int = 1) -> str:
    """解析某 LLM Provider 的 Key：Keychain 优先，settings（.env）兜底。

    company_id 为租户（多租户时传当前用户租户；默认 1 兼容演示/单租户）。
    返回明文给调用方（mainline/orchestrator/coordinator 构造 OpenAI 客户端），
    该返回值不得进入日志 / API 响应 / 审计 detail。
    """
    ref, _env_key, field = _LLM_REFS.get(provider, (f"llm:{provider}", "", ""))
    if db is not None:
        try:
            v = get_secret(db, company_id, ref)
            if v:
                return v
        except Exception:                 # noqa: BLE001
            pass
    if field:
        from .config import settings
        return getattr(settings, field, "") or ""
    return ""


# ---------------- .env -> Keychain 迁移（幂等） ----------------

def migrate_env_to_keychain(db, company_id: int, actor_name: str = "",
                            env_path: Optional[Path] = None) -> Dict[str, Any]:
    """把 backend/.env 中已配置的 LLM Key 幂等迁移进 Keychain。

    只迁移非空值；已存在且值不同的 ref_key 会更新（幂等）。
    返回迁移明细（不含明文）。
    """
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    env: Dict[str, str] = {}
    if env_path.exists():
        for ln in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = ln.strip()
            if s and not s.startswith("#") and "=" in s:
                k, _, v = s.partition("=")
                env[k.strip()] = v.strip()

    migrated: List[str] = []
    for provider, (ref, env_key, field) in _LLM_REFS.items():
        # 兼容两种写法：DEEPSEEK_API_KEY（.env 惯用）与 settings 字段名大写
        value = env.get(env_key, "") or env.get(field.upper(), "")
        value = value.strip()
        if not value:
            continue
        set_secret(db, company_id, ref, value, kind="llm",
                   pii_level="high", retention_days=365, region="cn",
                   note=f"migrated from .env {env_key}", actor_name=actor_name)
        migrated.append(ref)

    return {"migrated": migrated, "count": len(migrated),
            "note": "密钥已入 Keychain；.env 仍保留作为兼容回退，可手工清理"}


# ---------------- 便捷入口（无 db 时自建 session） ----------------

def _demo_company_id() -> int:
    """演示环境默认租户 1；真实多租户由请求上下文注入。"""
    return 1


def api_list_secrets() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        return list_secrets(db, _demo_company_id())
    finally:
        db.close()


def api_set_secret(ref_key: str, value: str, *, kind: str = "custom",
                   pii_level: str = "none", retention_days: int = 365,
                   region: str = "cn", note: str = "", actor_name: str = "") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        row = set_secret(db, _demo_company_id(), ref_key, value, kind=kind,
                         pii_level=pii_level, retention_days=retention_days,
                         region=region, note=note, actor_name=actor_name)
        return {"ok": True, "ref_key": row.ref_key,
                "masked": mask_secret(row.secret_value),
                "pii_level": row.pii_level, "retention_days": row.retention_days,
                "region": row.region}
    finally:
        db.close()


def api_delete_secret(ref_key: str, actor_name: str = "") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        delete_secret(db, _demo_company_id(), ref_key, actor_name=actor_name)
        return {"ok": True, "ref_key": ref_key}
    finally:
        db.close()


def api_migrate_env(actor_name: str = "") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        return migrate_env_to_keychain(db, _demo_company_id(), actor_name=actor_name)
    finally:
        db.close()
