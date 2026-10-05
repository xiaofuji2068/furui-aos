# -*- coding: utf-8 -*-
"""TASK-021 前端补丁 B：核电对象语境统一。

1) admin/[slug]/page.tsx：保存文案 演示暂存 -> 已落库
2) objects/page.tsx：TYPE_META 补 Area/MonitoringStation/MetricRecord/InspectionRecord
3) workbench/page.tsx：objectLinkOf 补核电对象前缀（MS/INSP/MET/AREA -> 对象中心跳转）
"""
from pathlib import Path

FE = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend\app")

# ---- 1) admin 文案 ----
p = FE / "admin" / "[slug]" / "page.tsx"
s = p.read_text(encoding="utf-8")
old = "已保存（演示，重启即丢失）"
new = "已保存至数据库"
assert old in s, "admin copy anchor"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK: admin copy")

# ---- 2) objects TYPE_META ----
p = FE / "objects" / "page.tsx"
s = p.read_text(encoding="utf-8")
old = '''  Ticket: { label: "风险事件", color: "#EA6668", icon: "⚠️" },
};'''
new = '''  Ticket: { label: "风险事件", color: "#EA6668", icon: "⚠️" },
  Area: { label: "区域", color: "#8BC8EA", icon: "🧭" },
  MonitoringStation: { label: "监测站", color: "#94D4D0", icon: "📡" },
  MetricRecord: { label: "监测指标", color: "#9BBBF4", icon: "📈" },
  InspectionRecord: { label: "巡检记录", color: "#F4B393", icon: "📋" },
};'''
assert old in s, "TYPE_META anchor"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK: objects TYPE_META")

# ---- 3) workbench objectLinkOf ----
p = FE / "workbench" / "page.tsx"
s = p.read_text(encoding="utf-8")
old = '''  const m = v.match(/^(CUS-\\d{3}|ORD-\\d{4}-\\d{4}|DEV-SKU-[A-Z]\\d{2}|SKU-[A-Z]\\d{2}|WO-\\d{3}|T-\\d{3})$/);
  if (!m) return null;
  const id = m[1];
  const prefix = id.split("-")[0];
  const OBJ_TYPE: Record<string, string> = { CUS: "Customer", ORD: "Order", DEV: "Device", SKU: "Product", WO: "WorkOrder", T: "Ticket" };
  const type = prefix === "SKU" ? "Product" : OBJ_TYPE[prefix];
  return type ? { type, id } : null;'''
new = '''  const m = v.match(/^(CUS-\\d{3}|ORD-\\d{4}-\\d{4}|DEV-SKU-[A-Z]\\d{2}|SKU-[A-Z]\\d{2}|WO-\\d{3}|T-\\d{3}|MS-\\d{2}|INSP-\\d{3}|MET-\\d{3}|AREA-[A-Z]{2})$/);
  if (!m) return null;
  const id = m[1];
  const prefix = id.split("-")[0];
  const OBJ_TYPE: Record<string, string> = {
    CUS: "Customer", ORD: "Order", DEV: "Device", SKU: "Product",
    WO: "WorkOrder", T: "Ticket", MS: "MonitoringStation",
    INSP: "InspectionRecord", MET: "MetricRecord", AREA: "Area",
  };
  const type = prefix === "SKU" ? "Product" : OBJ_TYPE[prefix];
  return type ? { type, id } : null;'''
assert old in s, "objectLinkOf anchor"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK: workbench objectLinkOf")
