# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend\app\pages\page.tsx")
t = p.read_text(encoding="utf-8")
old = '''  async function openEdit(p: AppPageBrief) {
    try {
      const detail = await (await import("../../lib/api")).fetchPageByCode(p.code);
      setEditing(detail);
      setDraftLayout(detail.layout);
      setError("");
    } catch (e: any) {
      setError(e?.message || "加载页面详情失败");
    }
  }'''
new = '''  async function openEdit(p: AppPageBrief) {
    try {
      const detail = await fetchPageByCode(p.code);
      setEditing(detail);
      setDraftLayout(detail.layout);
      setError("");
    } catch (e: any) {
      setError(e?.message || "加载页面详情失败");
    }
  }'''
assert old in t, "openEdit block not found"
t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
print("openEdit uses static import")