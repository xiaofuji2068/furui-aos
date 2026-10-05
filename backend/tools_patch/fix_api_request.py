# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend\lib\api.ts")
t = p.read_text(encoding="utf-8")
old = '''  // 统一返回格式 { code, message, data }
  if (!res.ok || (json && json.code !== 0)) {
    const message = json?.message || `请求失败 (${res.status})`;
    if (res.status === 401) clearSession();
    throw new ApiError(message, json?.code ?? res.status, res.status);
  }
  return (json?.data ?? json) as T;'''
new = '''  // 统一返回格式 { code, message, data }
  // 宽松兼容：响应无 code 字段视为裸对象（如低代码 pages API），仅在有 code 且非 0 时判失败
  if (!res.ok || (json && typeof json.code === "number" && json.code !== 0)) {
    const message = json?.message || `请求失败 (${res.status})`;
    if (res.status === 401) clearSession();
    throw new ApiError(message, json?.code ?? res.status, res.status);
  }
  return (json?.data ?? json) as T;'''
assert old in t, "request block not found"
t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
print("api.ts request loosened (bare-object compatible)")