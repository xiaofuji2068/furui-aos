# -*- coding: utf-8 -*-
"""TASK-014 前端补丁：api.ts Logic API + Sidebar 入口 + logic 画布页。"""
from pathlib import Path

FE = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend")

# ---------- 1) api.ts 追加 ----------
p = FE / "lib" / "api.ts"
s = p.read_text(encoding="utf-8")
tail = """

// ---------------- Logic 决策编排画布（TASK-014 / 30-03）----------------

export interface LogicNode {
  id: number;
  seq: number;
  key: string;
  title: string;
  kind: string;
  tool: string;
  label: string;
  params: Record<string, unknown>;
  depends: number[];
}

export interface LogicGraphBrief {
  id: number;
  code: string;
  name: string;
  version: string;
  description: string;
  status: string;
  node_count: number;
  updated_at: string;
}

export interface LogicGraphDetail {
  id: number;
  code: string;
  name: string;
  version: string;
  description: string;
  status: string;
  nodes: LogicNode[];
}

export function fetchLogicGraphs() {
  return api.get<{ items: LogicGraphBrief[] }>("/logic/graphs");
}

export function fetchLogicGraph(id: number) {
  return api.get<LogicGraphDetail>(`/logic/graphs/${id}`);
}

export function updateLogicNode(
  graphId: number,
  nodeId: number,
  patch: Partial<Pick<LogicNode, "title" | "kind" | "tool" | "label" | "params" | "depends">>,
) {
  return api.post<LogicGraphDetail>(`/logic/graphs/${graphId}/nodes`, { node_id: nodeId, ...patch });
}

export function activateLogicGraph(id: number) {
  return api.post<LogicGraphDetail>(`/logic/graphs/${id}/activate`);
}
"""
p.write_text(s.rstrip() + "\n" + tail, encoding="utf-8")
print("OK api.ts")

# ---------- 2) Sidebar 入口 ----------
p = FE / "components" / "Sidebar.tsx"
s = p.read_text(encoding="utf-8")
old = '''  { href: "/intelligence", icon: "◇", label: "智能化中心", perm: "datasource:view" },'''
new = '''  { href: "/intelligence", icon: "◇", label: "智能化中心", perm: "datasource:view" },
  { href: "/logic",        icon: "🔀", label: "Logic 编排", perm: "tool:config" },'''
assert old in s, "Sidebar anchor"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK Sidebar.tsx")