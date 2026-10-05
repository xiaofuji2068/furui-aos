# -*- coding: utf-8 -*-
"""TASK-013：admin.py 追加 SecretRef 路由 + save_model_keys 同步写 Keychain。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\api\admin.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

# ---------- 1) save_model_keys 里同步写 Keychain（幂等，失败不阻断 .env 主流程） ----------
old = """    if req.api_key.strip():
        env_key = _LLM_ENV_KEY[provider]
        field = _LLM_SETTINGS_FIELD[provider]
        _write_env_key(env_key, req.api_key.strip())
        setattr(settings, field, req.api_key.strip())   # 热更新，无需重启
        saved.append(provider)"""
new = """    if req.api_key.strip():
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
            pass"""
if old in src:
    src = src.replace(old, new, 1)
    print("OK: save_model_keys sync to Keychain")
else:
    print("WARN: save_model_keys anchor not found")

# ---------- 2) 检查 save_model_keys 是否有 user 参数 ----------
old_sig = "def save_model_keys(req: KeysReq, _auth: User = Depends(require_perm(\"tool:config\"))):"
if old_sig in src:
    new_sig = "def save_model_keys(req: KeysReq, user: User = Depends(require_perm(\"tool:config\"))):"
    src = src.replace(old_sig, new_sig, 1)
    print("OK: save_model_keys user param")
else:
    print("WARN: save_model_keys signature not found")

# ---------- 3) 文件末尾追加 SecretRef 路由 ----------
block = '''

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
'''

# 追加到文件末尾（最后一个 } 之后）
tail = src.rstrip()
if "/admin/secrets" in tail:
    print("SKIP: secrets routes already exist")
else:
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(tail + "\n" + block)
    print("OK: secrets routes appended")
