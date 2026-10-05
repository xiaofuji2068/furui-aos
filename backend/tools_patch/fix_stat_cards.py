# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend\app\pages\[code]\page.tsx")
t = p.read_text(encoding="utf-8")
old = '''    const json = await res.json();
    const d = json?.data ?? json ?? {};
    return (d?.kpis ?? []).map((k: any) => ({
      label: k?.label || "",
      value: k?.value ?? "",
      unit: k?.unit || "",
    }));'''
new = '''    const json = await res.json();
    const d = json?.data ?? json ?? {};
    // overview 的 kpis 为 { key: {label,value,delta} } 对象 → 转数组
    const kpis = d?.kpis ?? {};
    return Object.entries(kpis).map(([k, v]: [string, any]) => ({
      label: v?.label || k,
      value: v?.value ?? "",
      unit: v?.unit || "",
      delta: v?.delta,
    }));'''
assert old in t, "stat_cards block not found"
t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
print("stat_cards kpis parser fixed")