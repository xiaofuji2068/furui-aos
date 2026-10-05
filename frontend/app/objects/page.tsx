"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import DashboardShell from "../../components/DashboardShell";
import { useAuth } from "../../components/AuthProvider";
import {
  fetchObjectView,
  fetchOntologySnapshot,
  fetchRelated,
  runObjectAction,
  searchKnowledge,
  type ObjectAction,
  type ObjectView,
  type OntologyNode,
  type RelatedGraph,
} from "../../lib/api";

/** 对象类型 → 展示信息 */
const TYPE_META: Record<string, { label: string; color: string; icon: string }> = {
  Customer: { label: "客户", color: "#8BC8EA", icon: "🏢" },
  Order: { label: "订单", color: "#9BBBF4", icon: "🧾" },
  Device: { label: "设备", color: "#94D4D0", icon: "🖥" },
  Product: { label: "产品", color: "#A2DDAA", icon: "📦" },
  WorkOrder: { label: "工单", color: "#F4B393", icon: "🔧" },
  Ticket: { label: "风险事件", color: "#EA6668", icon: "⚠️" },
  Area: { label: "区域", color: "#8BC8EA", icon: "🧭" },
  MonitoringStation: { label: "监测站", color: "#94D4D0", icon: "📡" },
  MetricRecord: { label: "监测指标", color: "#9BBBF4", icon: "📈" },
  InspectionRecord: { label: "巡检记录", color: "#F4B393", icon: "📋" },
};

const LEVEL_TEXT: Record<number, string> = {
  1: "Level 1 · 自动执行",
  2: "Level 2 · 通知后执行",
  3: "Level 3 · 必须审批",
  4: "Level 4 · 禁止执行",
};

const LEVEL_STYLE: Record<number, string> = {
  1: "bg-emerald-500/15 text-emerald-300",
  2: "bg-cyan-500/15 text-cyan-300",
  3: "bg-amber-500/15 text-amber-300",
  4: "bg-red-500/15 text-red-300",
};

/** 简单 BFS 分层，供关联图 SVG 布局 */
function layoutGraph(root: OntologyNode, nodes: OntologyNode[], edges: RelatedGraph["edges"]) {
  const levelMap = new Map<string, number>();
  levelMap.set(`${root.type}:${root.id}`, 0);
  const byId = new Map<string, OntologyNode>();
  nodes.forEach((n) => byId.set(`${n.type}:${n.id}`, n));

  // BFS 分层
  let frontier = [`${root.type}:${root.id}`];
  let lv = 0;
  while (frontier.length && lv < 3) {
    lv += 1;
    const next: string[] = [];
    for (const k of frontier) {
      const node = byId.get(k);
      if (!node) continue;
      for (const e of edges) {
        if (e.source === node.id) {
          const target = nodes.find((n) => n.id === e.target && n.type !== node.type);
          if (target) {
            const tk = `${target.type}:${target.id}`;
            if (!levelMap.has(tk)) { levelMap.set(tk, lv); next.push(tk); }
          }
        }
        if (e.target === node.id) {
          const target = nodes.find((n) => n.id === e.source && n.type !== node.type);
          if (target) {
            const tk = `${target.type}:${target.id}`;
            if (!levelMap.has(tk)) { levelMap.set(tk, lv); next.push(tk); }
          }
        }
      }
    }
    frontier = next;
  }

  // 层 1 均分一圈；层 2 挂到其 parent 角度附近
  const pos = new Map<string, { x: number; y: number }>();
  const cx = 230, cy = 150;
  const l1 = nodes.filter((n) => levelMap.get(`${n.type}:${n.id}`) === 1);
  const l2 = nodes.filter((n) => levelMap.get(`${n.type}:${n.id}`) >= 2);
  pos.set(`${root.type}:${root.id}`, { x: cx, y: cy });
  const R1 = 92, R2 = 165;
  l1.forEach((n, i) => {
    const ang = (i / Math.max(l1.length, 1)) * Math.PI * 2 - Math.PI / 2;
    pos.set(`${n.type}:${n.id}`, { x: cx + R1 * Math.cos(ang), y: cy + R1 * Math.sin(ang) });
  });
  l2.forEach((n, i) => {
    // 找 parent（在 l1 中相连的节点）
    let parent = l1[0];
    let parentAng = -Math.PI / 2;
    for (const e of edges) {
      const cand = (e.source === n.id ? e.target : e.target === n.id ? e.source : null);
      if (!cand) continue;
      const pk = l1.find((x) => x.id === cand);
      if (pk) {
        parent = pk;
        const ppos = pos.get(`${pk.type}:${pk.id}`);
        if (ppos) parentAng = Math.atan2(ppos.y - cy, ppos.x - cx);
        break;
      }
    }
    const spread = 0.5;
    const off = (i % 2 === 0 ? -1 : 1) * spread * (Math.floor(i / 2) + 1) * 0.35;
    const ang = parentAng + off;
    pos.set(`${n.type}:${n.id}`, { x: cx + R2 * Math.cos(ang), y: cy + R2 * Math.sin(ang) });
  });
  return { pos, levelMap };
}

export default function ObjectsPage() {
  const { user } = useAuth();
  const canView = !!user?.permissions?.includes("datasource:view");
  const canAct = !!user?.permissions?.includes("tool:use");

  const [snapshot, setSnapshot] = useState<OntologyNode[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [filter, setFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<OntologyNode | null>(null);

  const [view, setView] = useState<ObjectView | null>(null);
  const [graph, setGraph] = useState<RelatedGraph | null>(null);
  const [loading, setLoading] = useState(false);

  const [formValues, setFormValues] = useState<Record<string, Record<string, string>>>({});
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [result, setResult] = useState<{ action: string; kind: "ok" | "blocked" | "error"; text: string; approvalId?: number } | null>(null);
  const [relatedDocs, setRelatedDocs] = useState<{ doc_title: string; score: number; content: string }[]>([]);

  const loadSnapshot = useCallback(() => {
    fetchOntologySnapshot()
      .then((s) => {
        setSnapshot(s.nodes || []);
        setTypes((s.nodes || []).map((n) => n.type).filter((v, i, a) => a.indexOf(v) === i));
      })
      .catch(() => setSnapshot([]));
  }, []);

  useEffect(() => {
    if (canView) loadSnapshot();
  }, [canView, loadSnapshot]);

  // 选中对象 → 加载详情 + 关联图
  // 从 URL query 恢复选中（P1：审批中心 / 工作台跳转入口）
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const t = q.get("type");
    const id = q.get("id");
    if (t && id) setSelected({ type: t, id });
  }, []);

  useEffect(() => {
    if (!selected) { setView(null); setGraph(null); return; }
    setLoading(true);
    setResult(null);
    setFormValues({});
    Promise.all([
      fetchObjectView(selected.type, selected.id).catch(() => null),
      fetchRelated(selected.type, selected.id, 2).catch(() => null),
    ]).then(([v, g]) => {
      setView(v);
      setGraph(g);
      setLoading(false);
      // 相关知识：按对象 id 与名称（语义化）检索知识库
      const kw = (v?.object?.properties?.name as string) || selected.id;
      Promise.all([
        searchKnowledge(selected.id, 3).catch(() => ({ hits: [] })),
        searchKnowledge(kw, 3).catch(() => ({ hits: [] })),
      ]).then(([a, b]) => {
        const seen = new Set<string>();
        const merged = [...(a.hits || []), ...(b.hits || [])].filter((h) => {
          if (!h.doc_title || seen.has(h.doc_title)) return false;
          seen.add(h.doc_title);
          return true;
        });
        setRelatedDocs(merged.slice(0, 5));
      });
    });
  }, [selected]);

  const list = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return snapshot.filter((n) => {
      if (filter && n.type !== filter) return false;
      if (kw && !(n.id.toLowerCase().includes(kw) || n.type.toLowerCase().includes(kw))) return false;
      return true;
    });
  }, [snapshot, filter, search]);

  async function submitAction(a: ObjectAction) {
    if (!selected || !view) return;
    const values = formValues[a.action] || {};
    const missing = a.params.filter((p) => p.required && !(values[p.name] || "").trim());
    if (missing.length) {
      setResult({ action: a.action, kind: "error", text: `请填写必填项：${missing.map((p) => p.label).join("、")}` });
      return;
    }
    setBusyAction(a.action);
    setResult(null);
    try {
      const res = await runObjectAction(selected.type, selected.id, a.action, values);
      if (res && res.blocked) {
        setResult({
          action: a.action,
          kind: "blocked",
          text: `该操作需人工审批（审批单 #${res.approval_id}），批准后自动执行。`,
          approvalId: res.approval_id,
        });
      } else if (res && res.ok) {
        setResult({
          action: a.action,
          kind: "ok",
          text: `执行成功${res.receipt_id ? `，已留执行凭证（Receipt #${res.receipt_id}）` : ""}${res.result?.summary ? `：${res.result.summary}` : ""}`,
        });
      } else {
        setResult({ action: a.action, kind: "error", text: res?.error || "执行失败" });
      }
    } catch (e: any) {
      setResult({ action: a.action, kind: "error", text: e?.message || "请求失败" });
    } finally {
      setBusyAction(null);
    }
  }

  if (!canView) {
    return (
      <DashboardShell>
        <div className="text-sm text-gray-400 py-20 text-center">无权限查看对象中心（需要 datasource:view）</div>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <div className="flex items-end justify-between mb-5">
        <div>
          <h1 className="text-2xl font-semibold">对象中心</h1>
          <p className="text-sm text-gray-400 mt-1">业务对象（本体图）浏览 · 关联探索 · 对象动作执行</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] px-2 py-1 rounded-md bg-white/5 text-gray-400">
            {snapshot.length} 个对象 · 本体版本 {view ? "" : "—"}
          </span>
        </div>
      </div>

      {/* 类型筛选 + 搜索 */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button
          onClick={() => setFilter("")}
          className={`text-xs px-3 py-1.5 rounded-lg border transition ${!filter ? "bg-violet-500/20 border-violet-400/30 text-violet-200" : "border-white/10 text-gray-400 hover:text-gray-200"}`}
        >
          全部
        </button>
        {types.map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t === filter ? "" : t)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition ${filter === t ? "bg-violet-500/20 border-violet-400/30 text-violet-200" : "border-white/10 text-gray-400 hover:text-gray-200"}`}
          >
            {TYPE_META[t]?.icon} {TYPE_META[t]?.label || t}
          </button>
        ))}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索对象 id / 类型…"
          className="ml-auto w-56 text-xs bg-white/[0.04] border border-white/10 rounded-lg px-3 py-1.5 outline-none focus:border-violet-400/40 placeholder:text-gray-600"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4 items-start">
        {/* 左：对象列表 */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] overflow-hidden">
          <div className="px-4 py-2.5 text-xs font-medium text-gray-300 border-b border-white/5">对象列表</div>
          <div className="max-h-[640px] overflow-auto divide-y divide-white/[0.04]">
            {list.length === 0 && (
              <div className="text-xs text-gray-500 px-4 py-8 text-center">无匹配对象</div>
            )}
            {list.map((n) => {
              const meta = TYPE_META[n.type] || { label: n.type, color: "#9EACEA", icon: "▪" };
              const active = selected?.type === n.type && selected?.id === n.id;
              return (
                <button
                  key={`${n.type}:${n.id}`}
                  onClick={() => {
                    setSelected(n);
                    window.history.replaceState(null, "", `/objects?type=${encodeURIComponent(n.type)}&id=${encodeURIComponent(n.id)}`);
                  }}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition ${active ? "bg-violet-500/10" : "hover:bg-white/[0.03]"}`}
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: meta.color, boxShadow: `0 0 8px ${meta.color}66` }}
                  />
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm text-gray-200 truncate">{n.id}</span>
                    <span className="block text-[11px] text-gray-500">{meta.icon} {meta.label}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 右：详情 */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] min-h-[400px]">
          {!selected && (
            <div className="py-24 text-center text-sm text-gray-500">
              从左侧选择一个对象，查看详情、关联关系与可执行动作
            </div>
          )}

          {selected && loading && (
            <div className="py-24 text-center text-sm text-gray-500">
              <div className="h-8 w-8 border-2 border-violet-400/40 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              加载对象…
            </div>
          )}

          {selected && !loading && (
            <div className="p-5 space-y-5">
              {/* 对象头 */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span
                    className="w-10 h-10 rounded-xl flex items-center justify-center text-lg"
                    style={{ background: `${(TYPE_META[selected.type]?.color || "#9EACEA")}22`, border: `1px solid ${(TYPE_META[selected.type]?.color || "#9EACEA")}55` }}
                  >
                    {TYPE_META[selected.type]?.icon || "▪"}
                  </span>
                  <div>
                    <div className="text-lg font-semibold">{view?.object?.name || selected.id}</div>
                    <div className="text-xs text-gray-500">
                      {selected.type} · {selected.id}
                      {view && !view.actions.length && " · 无可执行动作"}
                    </div>
                  </div>
                </div>
                <Link
                  href={`/approvals`}
                  className="text-xs px-3 py-1.5 rounded-lg border border-white/10 text-gray-300 hover:text-white hover:bg-white/5 transition"
                >
                  去审批中心 →
                </Link>
              </div>

              {/* 属性 + 关联图 */}
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <div className="rounded-xl border border-white/5 bg-black/20 p-4">
                  <div className="text-xs font-medium text-gray-300 mb-3">对象属性</div>
                  {view && Object.keys(view.object.properties || {}).length > 0 ? (
                    <div className="space-y-1.5">
                      {Object.entries(view.object.properties).map(([k, v]) => (
                        <div key={k} className="flex items-center justify-between text-xs">
                          <span className="text-gray-500">{k}</span>
                          <span className="text-gray-200 font-mono">{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-gray-600">无属性数据</div>
                  )}
                </div>

                <div className="rounded-xl border border-white/5 bg-black/20 p-4">
                  <div className="text-xs font-medium text-gray-300 mb-2 flex items-center justify-between">
                    <span>关联关系（depth 2）</span>
                    {graph && <span className="text-[10px] text-gray-600">{graph.nodes.length} 节点 · {graph.edges.length} 条关系</span>}
                  </div>
                  {graph && graph.nodes.length > 1 ? (
                    <RelationGraph graph={graph} root={selected} />
                  ) : (
                    <div className="text-xs text-gray-600 py-10 text-center">无关联对象</div>
                  )}
                </div>
              </div>

              {/* 相关知识（P1：对象 ↔ 知识库关联） */}
              {relatedDocs.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-gray-300 mb-2 flex items-center justify-between">
                    <span>相关知识</span>
                    <Link href="/knowledge" className="text-[10px] text-gray-500 hover:text-gray-300 transition">去知识库检索 →</Link>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {relatedDocs.map((d, i) => (
                      <Link
                        key={i}
                        href="/knowledge"
                        className="rounded-xl border border-white/5 bg-black/20 p-3 hover:border-violet-400/20 transition block"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[13px] text-gray-100 font-medium truncate">{d.doc_title}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-300 ml-auto shrink-0">{(d.score * 100).toFixed(0)}%</span>
                        </div>
                        <div className="text-[11px] text-gray-500 leading-relaxed line-clamp-2">{d.content}</div>
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {/* 动作表单 */}
              {view && view.actions.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-gray-300 mb-2">对象动作</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {view.actions.map((a) => (
                      <div key={a.action} className="rounded-xl border border-white/5 bg-black/20 p-4">
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-sm font-medium text-gray-100">{a.label}</span>
                          <span className={`text-[10px] px-2 py-0.5 rounded-md ${LEVEL_STYLE[a.level] || "bg-white/5 text-gray-400"}`}>
                            {LEVEL_TEXT[a.level] || `Level ${a.level}`}
                          </span>
                        </div>
                        <div className="space-y-2">
                          {a.params.map((p) => (
                            <div key={p.name}>
                              <label className="block text-[11px] text-gray-500 mb-1">
                                {p.label} {p.required && <span className="text-rose-400">*</span>}
                              </label>
                              <input
                                value={(formValues[a.action] || {})[p.name] || ""}
                                onChange={(e) =>
                                  setFormValues((f) => ({
                                    ...f,
                                    [a.action]: { ...(f[a.action] || {}), [p.name]: e.target.value },
                                  }))
                                }
                                placeholder={p.label}
                                className="w-full text-xs bg-white/[0.04] border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-violet-400/40 placeholder:text-gray-600"
                              />
                            </div>
                          ))}
                        </div>
                        {result?.action === a.action && (
                          <div
                            className={`mt-3 text-[11px] rounded-lg px-3 py-2 border ${
                              result.kind === "ok"
                                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                                : result.kind === "blocked"
                                  ? "border-amber-500/20 bg-amber-500/10 text-amber-300"
                                  : "border-rose-500/20 bg-rose-500/10 text-rose-300"
                            }`}
                          >
                            {result.kind === "ok" ? "✓ " : result.kind === "blocked" ? "⏳ " : "✗ "}
                            {result.text}
                            {result.kind === "blocked" && result.approvalId && (
                              <Link href="/approvals" className="underline ml-1 hover:text-amber-200">
                                去审批
                              </Link>
                            )}
                          </div>
                        )}
                        <button
                          disabled={busyAction === a.action || !canAct}
                          onClick={() => submitAction(a)}
                          className="mt-3 w-full text-xs px-3 py-2 rounded-lg bg-gradient-to-r from-violet-500 to-blue-500 text-white disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition"
                          title={canAct ? undefined : "无 tool:use 权限"}
                        >
                          {busyAction === a.action ? "执行中…" : canAct ? `执行「${a.label}」` : "无执行权限"}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </DashboardShell>
  );
}

/** 关联关系图（SVG，确定性布局） */
function RelationGraph({ graph, root }: { graph: RelatedGraph; root: OntologyNode }) {
  const { pos } = layoutGraph(root, graph.nodes, graph.edges);

  // 边的端点：节点圆边缘（r=26）
  const line = (e: { source: string; target: string }) => {
    const src = graph.nodes.find((n) => n.id === e.source);
    const tgt = graph.nodes.find((n) => n.id === e.target);
    const sk = src ? `${src.type}:${src.id}` : "";
    const tk = tgt ? `${tgt.type}:${tgt.id}` : "";
    const sp = pos.get(sk);
    const tp = pos.get(tk);
    if (!sp || !tp) return null;
    const dx = tp.x - sp.x, dy = tp.y - sp.y;
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len;
    return {
      x1: sp.x + ux * 26,
      y1: sp.y + uy * 26,
      x2: tp.x - ux * 26,
      y2: tp.y - uy * 26,
      src,
      tgt,
    };
  };

  return (
    <svg viewBox="0 0 460 300" className="w-full h-auto">
      {graph.edges.map((e, i) => {
        const l = line(e);
        if (!l) return null;
        return (
          <g key={i}>
            <line
              x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
              stroke={e.direction === "in" ? "#F4B39388" : "#8BC8EA88"}
              strokeWidth={1.2}
              strokeDasharray={e.direction === "in" ? "3 3" : undefined}
            />
            <text
              x={(l.x1 + l.x2) / 2} y={(l.y1 + l.y2) / 2 - 4}
              textAnchor="middle" fontSize={8} fill="#6B7280"
            >
              {e.type}
              {e.direction ? (e.direction === "in" ? " ←" : " →") : ""}
            </text>
          </g>
        );
      })}
      {graph.nodes.map((n) => {
        const key = `${n.type}:${n.id}`;
        const p = pos.get(key);
        if (!p) return null;
        const meta = TYPE_META[n.type] || { label: n.type, color: "#9EACEA", icon: "▪" };
        const isRoot = n.id === root.id && n.type === root.type;
          return (
          <g key={key}>
            <circle
              cx={p.x} cy={p.y} r={26}
              fill={`${meta.color}${isRoot ? "33" : "1e"}`}
              stroke={meta.color}
              strokeWidth={isRoot ? 2.5 : 1.2}
            />
            <text x={p.x} y={p.y - 1} textAnchor="middle" fontSize={8.5} fontWeight={600} fill="#E5E7EB">
              {n.id.length > 11 ? `${n.id.slice(0, 10)}…` : n.id}
            </text>
            <text x={p.x} y={p.y + 10} textAnchor="middle" fontSize={7.5} fill="#9CA3AF">
              {meta.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
