"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import DashboardShell from "../../components/DashboardShell";
import { useAuth } from "../../components/AuthProvider";
import {
  activateLogicGraph,
  fetchLogicGraph,
  fetchLogicGraphs,
  updateLogicNode,
  type LogicGraphBrief,
  type LogicGraphDetail,
  type LogicNode,
} from "../../lib/api";

/** 节点类型 → 展示样式 */
const KIND_META: Record<string, { label: string; color: string; badge: string }> = {
  data:      { label: "数据",      color: "#8BC8EA", badge: "bg-cyan-500/15 text-cyan-300" },
  knowledge: { label: "知识",      color: "#F4B393", badge: "bg-amber-500/15 text-amber-300" },
  tool:      { label: "工具",      color: "#C9A7E8", badge: "bg-violet-500/15 text-violet-300" },
  report:    { label: "报告",      color: "#A2DDAA", badge: "bg-emerald-500/15 text-emerald-300" },
  approval:  { label: "审批",      color: "#EA6668", badge: "bg-red-500/15 text-red-300" },
};

const KIND_OPTIONS = ["data", "knowledge", "tool", "report", "approval"];

export default function LogicPage() {
  const { user } = useAuth();
  const canEdit = !!user?.permissions?.includes("tool:config");

  const [graphs, setGraphs] = useState<LogicGraphBrief[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<LogicGraphDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const loadGraphs = useCallback(async () => {
    try {
      const data = await fetchLogicGraphs();
      setGraphs(data.items);
      setError("");
    } catch (e: any) {
      setError(e?.message || "加载图列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGraphs();
  }, [loadGraphs]);

  useEffect(() => {
    if (selectedId == null) { setDetail(null); return; }
    fetchLogicGraph(selectedId)
      .then((d) => { setDetail(d); setError(""); })
      .catch((e: any) => setError(e?.message || "加载图详情失败"));
  }, [selectedId]);

  /** 编辑态：nodeId -> 草稿字段 */
  const [editing, setEditing] = useState<Record<number, { title: string; label: string; kind: string; tool: string }>>({});

  const activeGraph = useMemo(() => graphs.find((g) => g.id === selectedId), [graphs, selectedId]);

  async function saveNode(node: LogicNode) {
    if (!detail) return;
    const draft = editing[node.id];
    if (!draft) return;
    setSaving(true);
    setMsg("");
    try {
      const d = await updateLogicNode(detail.id, node.id, {
        title: draft.title,
        label: draft.label,
        kind: draft.kind,
        tool: draft.tool,
      });
      setDetail(d);
      setEditing((m) => { const n = { ...m }; delete n[node.id]; return n; });
      setMsg("节点已保存，执行引擎将按新配置运行");
      loadGraphs();
    } catch (e: any) {
      setError(e?.message || "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function activate(id: number) {
    setMsg("");
    try {
      const d = await activateLogicGraph(id);
      setDetail(d);
      setMsg("已激活：主链路将按该图执行");
      loadGraphs();
    } catch (e: any) {
      setError(e?.message || "激活失败");
    }
  }

  return (
    <DashboardShell>
      <div className="space-y-6">
        {/* 头部 */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <span className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-blue-500 flex items-center justify-center text-lg shadow-glow">🔀</span>
            Logic 决策编排画布
          </h1>
          <p className="mt-2 text-sm text-gray-400 max-w-3xl">
            业务主链路的执行步骤以「图」的形式存在服务端：可查看、可编辑节点、可切换激活。
            执行引擎读取 active 图运行 —— 图结构是数据，不是硬编码。
          </p>
          {msg && <div className="mt-3 px-4 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm">{msg}</div>}
          {error && <div className="mt-3 px-4 py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm">{error}</div>}
        </div>

        {/* 图列表 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {graphs.map((g) => {
            const sel = g.id === selectedId;
            return (
              <button key={g.id} onClick={() => setSelectedId(g.id)}
                className={`text-left p-5 rounded-2xl border transition-all ${
                  sel ? "border-violet-400/50 bg-violet-500/[0.07] shadow-glow"
                      : "border-white/10 bg-white/[0.03] hover:bg-white/[0.05]"}`}>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-gray-500">{g.code}</span>
                  {g.status === "active"
                    ? <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 text-xs">已激活</span>
                    : <span className="px-2 py-0.5 rounded-full bg-gray-500/15 text-gray-400 text-xs">草稿</span>}
                </div>
                <div className="mt-2 text-lg font-semibold text-white">{g.name}</div>
                <div className="mt-1 text-xs text-gray-400">{g.description}</div>
                <div className="mt-3 flex items-center gap-3 text-xs text-gray-500">
                  <span>v{g.version}</span>
                  <span>·</span>
                  <span>{g.node_count} 个节点</span>
                  <span>·</span>
                  <span>更新 {g.updated_at?.slice(0, 10) || "-"}</span>
                </div>
              </button>
            );
          })}
          {!loading && graphs.length === 0 && (
            <div className="col-span-full p-8 text-center text-sm text-gray-500 border border-dashed border-white/10 rounded-2xl">
              暂无编排图 —— 首次访问会自动从系统默认链路生成两张图（销售 / 核电巡检）。
            </div>
          )}
        </div>

        {/* 画布 */}
        {detail && (
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <div className="text-lg font-semibold text-white">{detail.name}</div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {detail.code} · v{detail.version} · {detail.nodes.length} 步
                </div>
              </div>
              {activeGraph?.status !== "active" && canEdit && (
                <button onClick={() => activate(detail.id)}
                  className="px-4 py-2 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-sm hover:bg-emerald-500/25 transition">
                  激活此图
                </button>
              )}
              {activeGraph?.status === "active" && (
                <span className="px-3 py-1.5 rounded-xl bg-emerald-500/15 text-emerald-300 text-sm">执行中链路</span>
              )}
            </div>

            {/* 节点流 */}
            <div className="mt-5 flex flex-wrap gap-3">
              {detail.nodes.map((n, i) => {
                const km = KIND_META[n.kind] || KIND_META.data;
                const draft = editing[n.id];
                return (
                  <div key={n.id} className="relative flex-1 min-w-[220px] max-w-[260px]">
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="flex items-center justify-between">
                        <span className="w-6 h-6 rounded-md flex items-center justify-center text-[11px] font-bold text-black"
                              style={{ background: km.color }}>{n.seq}</span>
                        <span className={`px-2 py-0.5 rounded-full text-[11px] ${km.badge}`}>{km.label}</span>
                      </div>
                      {draft ? (
                        <div className="mt-3 space-y-2">
                          <input value={draft.title} onChange={(e) => setEditing({ ...editing, [n.id]: { ...draft, title: e.target.value } })}
                            className="w-full px-2 py-1.5 rounded-lg bg-black/30 border border-white/10 text-sm text-white outline-none focus:border-violet-400/50" />
                          <input value={draft.label} onChange={(e) => setEditing({ ...editing, [n.id]: { ...draft, label: e.target.value } })}
                            className="w-full px-2 py-1.5 rounded-lg bg-black/30 border border-white/10 text-xs text-gray-200 outline-none focus:border-violet-400/50" />
                          <div className="flex gap-2">
                            <select value={draft.kind} onChange={(e) => setEditing({ ...editing, [n.id]: { ...draft, kind: e.target.value } })}
                              className="px-2 py-1.5 rounded-lg bg-black/30 border border-white/10 text-xs text-white outline-none">
                              {KIND_OPTIONS.map((k) => <option key={k} value={k}>{KIND_META[k].label}</option>)}
                            </select>
                            <input value={draft.tool} onChange={(e) => setEditing({ ...editing, [n.id]: { ...draft, tool: e.target.value } })}
                              placeholder="tool 标识"
                              className="flex-1 px-2 py-1.5 rounded-lg bg-black/30 border border-white/10 text-xs text-gray-200 outline-none focus:border-violet-400/50" />
                          </div>
                          <div className="flex gap-2">
                            <button onClick={() => saveNode(n)} disabled={saving}
                              className="flex-1 px-3 py-1.5 rounded-lg bg-violet-500/20 border border-violet-400/40 text-violet-200 text-xs hover:bg-violet-500/30">
                              {saving ? "保存中…" : "保存"}
                            </button>
                            <button onClick={() => setEditing((m) => { const x = { ...m }; delete x[n.id]; return x; })}
                              className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-gray-400 text-xs hover:bg-white/10">
                              取消
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="mt-2 text-sm font-medium text-white">{n.title}</div>
                          <div className="mt-1 text-xs text-gray-400">{n.label}</div>
                          {n.tool && (
                            <div className="mt-2 inline-block px-2 py-0.5 rounded-md bg-black/30 font-mono text-[11px] text-violet-300">{n.tool}</div>
                          )}
                          {canEdit && (
                            <button onClick={() => setEditing({ ...editing, [n.id]: { title: n.title, label: n.label, kind: n.kind, tool: n.tool } })}
                              className="mt-3 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-gray-300 text-xs hover:bg-white/10 transition">
                              编辑节点
                            </button>
                          )}
                        </>
                      )}
                    </div>
                    {i < detail.nodes.length - 1 && (
                      <div className="hidden md:block absolute top-1/2 -right-3 translate-x-full text-gray-600">→</div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* 依赖说明 */}
            <div className="mt-4 text-xs text-gray-500">
              依赖关系：{detail.nodes.map((n) => `#${n.seq}${n.depends?.length ? " ← " + n.depends.join(",") : ""}`).join(" · ")}
            </div>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
