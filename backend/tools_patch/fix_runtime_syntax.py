# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend\app\pages\[code]\page.tsx")
t = p.read_text(encoding="utf-8")
old = '''    fetchPageByCode(code)
      .then((p) => { setPage(p); setError(""); })
      .catch((e: any) => setError(e?.message || "页面不存在或未发布"));
      .finally(() => setLoading(false));'''
new = '''    fetchPageByCode(code)
      .then((p) => { setPage(p); setError(""); })
      .catch((e: any) => setError(e?.message || "页面不存在或未发布"))
      .finally(() => setLoading(false));'''
if old in t:
    t = t.replace(old, new)
    p.write_text(t, encoding="utf-8")
    print("runtime syntax fixed")
else:
    print("MISS runtime syntax block")