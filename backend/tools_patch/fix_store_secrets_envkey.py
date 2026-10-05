# -*- coding: utf-8 -*-
"""TASK-013：修正 _LLM_REFS 增加 .env 键名，migrate 按真实 .env 键读取。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\store_secrets.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

old = '''# LLM Provider -> (ref_key, settings 字段名)（migrate 与 resolve 共用）
_LLM_REFS = {
    "deepseek": ("llm:deepseek", "deepseek_key"),
    "kimi": ("llm:kimi", "kimi_key"),
    "qwen": ("llm:qwen", "qwen_key"),
    "glm": ("llm:glm", "glm_key"),
    "openai": ("llm:openai", "openai_key"),
    "custom": ("llm:custom", "custom_key"),
    "dashscope": ("llm:dashscope", "dashscope_api_key"),
}'''
new = '''# LLM Provider -> (ref_key, .env 键名, settings 字段名)（migrate 与 resolve 共用）
_LLM_REFS = {
    "deepseek": ("llm:deepseek", "DEEPSEEK_API_KEY", "deepseek_key"),
    "kimi": ("llm:kimi", "KIMI_API_KEY", "kimi_key"),
    "qwen": ("llm:qwen", "QWEN_API_KEY", "qwen_key"),
    "glm": ("llm:glm", "GLM_API_KEY", "glm_key"),
    "openai": ("llm:openai", "OPENAI_API_KEY", "openai_key"),
    "custom": ("llm:custom", "CUSTOM_API_KEY", "custom_key"),
    "dashscope": ("llm:dashscope", "DASHSCOPE_API_KEY", "dashscope_api_key"),
}'''
if old not in src:
    print("WARN: _LLM_REFS anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)

# resolve_llm_key 解包改为 3 元组
old_res = '''    ref, field = _LLM_REFS.get(provider, (f"llm:{provider}", ""))
    if db is not None:'''
new_res = '''    ref, _env_key, field = _LLM_REFS.get(provider, (f"llm:{provider}", "", ""))
    if db is not None:'''
if old_res not in src:
    print("WARN: resolve anchor not found")
    raise SystemExit(1)
src = src.replace(old_res, new_res, 1)

# migrate 循环解包改为 3 元组 + 按 .env 键名读取
old_mig = '''    migrated: List[str] = []
    for provider, (ref, field) in _LLM_REFS.items():
        value = env.get(field.upper(), "").strip()
        if not value:
            continue
        set_secret(db, company_id, ref, value, kind="llm",
                   pii_level="high", retention_days=365, region="cn",
                   note=f"migrated from .env {field.upper()}", actor_name=actor_name)
        migrated.append(ref)'''
new_mig = '''    migrated: List[str] = []
    for provider, (ref, env_key, field) in _LLM_REFS.items():
        # 兼容两种写法：DEEPSEEK_API_KEY（.env 惯用）与 settings 字段名大写
        value = env.get(env_key, "") or env.get(field.upper(), "")
        value = value.strip()
        if not value:
            continue
        set_secret(db, company_id, ref, value, kind="llm",
                   pii_level="high", retention_days=365, region="cn",
                   note=f"migrated from .env {env_key}", actor_name=actor_name)
        migrated.append(ref)'''
if old_mig not in src:
    print("WARN: migrate anchor not found")
    raise SystemExit(1)
src = src.replace(old_mig, new_mig, 1)

with io.open(p, "w", encoding="utf-8") as f:
    f.write(src)
print("OK: store_secrets fixed")
