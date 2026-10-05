# -*- coding: utf-8 -*-
"""TASK-013：resolve_llm_key 支持传入 company_id（默认 1 兼容演示）。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\store_secrets.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

old = '''def resolve_llm_key(provider: str, db=None) -> str:
    """解析某 LLM Provider 的 Key：Keychain 优先，settings（.env）兜底。

    返回明文给调用方（mainline/orchestrator/coordinator 构造 OpenAI 客户端），
    该返回值不得进入日志 / API 响应 / 审计 detail。
    """
    ref, _env_key, field = _LLM_REFS.get(provider, (f"llm:{provider}", "", ""))
    if db is not None:
        try:
            v = get_secret(db, 1, ref)   # 演示租户 company_id=1；多租户时按当前用户租户传入
            if v:
                return v
        except Exception:                 # noqa: BLE001
            pass
    if field:
        from .config import settings
        return getattr(settings, field, "") or ""
    return ""'''

new = '''def resolve_llm_key(provider: str, db=None, company_id: int = 1) -> str:
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
    return ""'''

if old not in src:
    print("WARN: resolve anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
with io.open(p, "w", encoding="utf-8") as f:
    f.write(src)
print("OK: resolve_llm_key company_id param")
