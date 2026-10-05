# -*- coding: utf-8 -*-
"""TASK-015 前端接线：api.ts pages 函数 + Sidebar 入口 + 构建页 + 运行时页"""
from pathlib import Path
import ast
root = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend")

# ---------- 1) api.ts 追加 pages API ----------
api_p = root / "lib" / "api.ts"
t = api_p.read_text(encoding="utf-8")
block = '''

// ---------------- 低代码页面 API（TASK-015 / 40-03）----------------

export interface PageWidget {
  widget: string;
  title: string;
  params: Record<string, any>;
}

export interface AppPageBrief {
  id: number;
  code: string;
  title: string;
  description: string;
  status: string;
  version: string;
  widget_count: number;
  updated_at: string;
}

export interface AppPage extends AppPageBrief {
  layout: PageWidget[];
  created_at: string;
}

export interface WidgetTypeInfo {
  type: string;
  label: string;
  desc: string;
  default_params: Record<string, any>;
}

export function fetchWidgetTypes() {
  return api.get<{ items: WidgetTypeInfo[] }>("/pages/widget-types");
}

export function fetchPages() {
  return api.get<{ items: AppPageBrief[] }>("/pages");
}

export function fetchPageByCode(code: string) {
  return api.get<AppPage>(`/pages/by-code/${encodeURIComponent(code)}`);
}

export function createPage(payload: {
  code: string;
  title: string;
  description?: string;
  layout?: PageWidget[];
}) {
  return api.post<AppPage>("/pages", payload);
}

export function updatePage(
  id: number,
  patch: { title?: string; description?: string; layout?: PageWidget[] },
) {
  return api.put<AppPage>(`/pages/${id}`, patch);
}

export function publishPage(id: number) {
  return api.post<AppPage>(`/pages/${id}/publish`);
}

export function draftPage(id: number) {
  return api.post<AppPage>(`/pages/${id}/draft`);
}

export function deletePage(id: number) {
  return api.del<{ ok: boolean }>(`/pages/${id}`);
}
'''
if "fetchWidgetTypes" not in t:
    t = t.rstrip() + "\n" + block
    api_p.write_text(t, encoding="utf-8")
    print("api.ts: appended pages API")
else:
    print("api.ts: already has pages API")

# ---------- 2) Sidebar 加入口 ----------
sb_p = root / "components" / "Sidebar.tsx"
t2 = sb_p.read_text(encoding="utf-8")
old_nav = '  { href: "/logic",        icon: "🔀", label: "Logic 编排", perm: "tool:config" },\n];'
new_nav = '  { href: "/logic",        icon: "🔀", label: "Logic 编排", perm: "tool:config" },\n  { href: "/pages",        icon: "🧱", label: "低代码构建", perm: "tool:config" },\n];'
if old_nav in t2 and "/pages" not in t2:
    t2 = t2.replace(old_nav, new_nav)
    sb_p.write_text(t2, encoding="utf-8")
    print("Sidebar: entry added")
else:
    print("Sidebar: skip (already or MISS)")

# ---------- 3) 构建页 ----------
build_p = root / "app" / "pages" / "page.tsx"
build_page = '''"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import DashboardShell from "../../components/DashboardShell";
import { useAuth } from "../../components/AuthProvider";
import {
  createPage,
  deletePage,
  draftPage,
  fetchPages,
  fetchWidgetTypes,
  publishPage,
  updatePage,
  type AppPage,
  type AppPageBrief,
  type PageWidget,
  type WidgetTypeInfo,
} from "../../lib/api";

const STATUS_META: Record<string, { label: string; cls: string }> = {
  published: { label: "已发布", cls: "bg-emerald-500/15 text-emerald-300" },
  draft: { label: "草稿", cls: "bg-amber-500/15 text-amber-300" },
};

export default function PagesPage() {
  const { user } = useAuth();
  const canEdit = !!user?.permissions?.includes("tool:config");

  const [pages, setPages] = useState<AppPageBrief[]>([]);
  const [widgetTypes, setWidgetTypes] = useState<WidgetTypeInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  // 新建弹层
  const [showNew, setShowNew] = useState(false);
  const [nCode, setNCode] = useState("");
  const [nTitle, setNTitle] = useState("");
  const [nDesc, setNDesc] = useState("");

  // 编辑态：选中页面 + layout 草稿
  const [editing, setEditing] = useState<AppPage | null>(null);
  const [draftLayout, setDraftLayout] = useState<PageWidget[]>([]);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, w] = await Promise.all([fetchPages(), fetchWidgetTypes()]);
      setPages(p.items);
      setWidgetTypes(w.items);
      setError("");
    } catch (e: any) {
      setError(e?.message || "加载页面列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function doCreate() {
    if (!nCode.trim() || !nTitle.trim()) { setError("code 与标题必填"); return; }
    setSaving(true); setError(""); setMsg("");
    try {
      const p = await createPage({
        code: nCode.trim(),
        title: nTitle.trim(),
        description: nDesc,
        layout: [{ widget: "text_note", title: "页面说明", params: { content: "在这里输入说明文字" } }],
      });
      setShowNew(false); setNCode(""); setNTitle(""); setNDesc("");
      setMsg(`页面已创建（草稿）：${p.code}`);
      await load();
      setEditing(p);
      setDraftLayout(p.layout);
    } catch (e: any) {
      setError(e?.message || "创建失败");
    } finally { setSaving(false); }
  }

  async function openEdit(p: AppPageBrief) {
    try {
      const detail = await (await import("../../lib/api")).fetchPageByCode(p.code);
      setEditing(detail);
      setDraftLayout(detail.layout);
      setError("");
    } catch (e: any) {
      setError(e?.message || "加载页面详情失败");
    }
  }

  function addWidget(type: string) {
    const w = widgetTypes.find((x) => x.type === type);
    setDraftLayout((ls) => [...ls, {
      widget: type,
      title: w?.label || type,
      params: { ...(w?.default_params || {}) },
    }]);
  }

  function patchWidget(idx: number, patch: Partial<PageWidget>) {
    setDraftLayout((ls) => ls.map((x, i) => (i === idx ? { ...x, ...patch } : x)));
  }

  function patchWidgetParam(idx: number, key: string, value: string) {
    setDraftLayout((ls) => ls.map((x, i) => {
      if (i !== idx) return x;
      const params = { ...x.params, [key]: value };
      return { ...x, params };
    }));
  }

  async function saveLayout() {
    if (!editing) return;
    setSaving(true); setMsg(""); setError("");
    try {
      const d = await updatePage(editing.id, { layout: draftLayout });
      setEditing(d);
      setMsg("布局已保存，版本 " + d.version);
      await load();
    } catch (e: any) {
      setError(e?.message || "保存失败");
    } finally { setSaving(false); }
  }

  async function doPublish(id: number) {
    setMsg(""); setError("");
    try { await publishPage(id); setMsg("已发布，可通过 URL 访问"); await load(); }
    catch (e: any) { setError(e?.message || "发布失败"); }
  }

  async function doDraft(id: number) {
    setMsg(""); setError("");
    try { await draftPage(id); setMsg("已转为草稿"); await load(); }
    catch (e: any) { setError(e?.message || "操作失败"); }
  }

  async function doDelete(id: number, code: string) {
    if (!window.confirm(`确认删除页面「${code}」？`)) return;
    setMsg(""); setError("");
    try { await deletePage(id); setMsg("页面已删除"); if (editing?.id === id) setEditing(null); await load(); }
    catch (e: any) { setError(e?.message || "删除失败"); }
  }

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white">低代码构建</h1>
            <p className="text-sm text-gray-400 mt-1">把对象 / 数据源 / 任务编排成可运行页面，发布后可挂到侧边栏直接访问（40-03 + 40-02）。</p>
          </div>
          {canEdit && (
            <button onClick={() => setShowNew(true)}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white text-sm font-medium hover:opacity-90">
              + 新建页面
            </button>
          )}
        </div>

        {msg && <div className="px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-400/30 text-emerald-300 text-sm">{msg}</div>}
        {error && <div className="px-4 py-2 rounded-xl bg-red-500/10 border border-red-400/30 text-red-300 text-sm">{error}</div>}

        {/* 页面列表 */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {pages.map((p) => {
            const st = STATUS_META[p.status] || STATUS_META.draft;
            return (
              <div key={p.id} className="rounded-2xl bg-white/[0.03] border border-white/10 p-5 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-white">{p.title}</div>
                    <div className="text-[11px] text-gray-500 mt-0.5 font-mono">/pages/{p.code}</div>
                  </div>
                  <span className={`px-2 py-0.5 rounded-md text-[11px] ${st.cls}`}>{st.label}</span>
                </div>
                {p.description && <p className="text-xs text-gray-400 line-clamp-2">{p.description}</p>}
                <div className="flex items-center gap-3 text-[11px] text-gray-500">
                  <span>v{p.version}</span>
                  <span>{p.widget_count} 个组件</span>
                  <span>{p.updated_at?.slice(0, 10)}</span>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  <Link href={`/pages/${p.code}`} className="px-2.5 py-1 rounded-lg bg-white/[0.06] text-gray-300 text-xs hover:bg-white/[0.1]">
                    预览
                  </Link>
                  {canEdit && (
                    <>
                      <button onClick={() => openEdit(p)} className="px-2.5 py-1 rounded-lg bg-violet-500/15 text-violet-300 text-xs hover:bg-violet-500/25">编辑</button>
                      {p.status === "draft"
                        ? <button onClick={() => doPublish(p.id)} className="px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-300 text-xs hover:bg-emerald-500/25">发布</button>
                        : <button onClick={() => doDraft(p.id)} className="px-2.5 py-1 rounded-lg bg-amber-500/15 text-amber-300 text-xs hover:bg-amber-500/25">转草稿</button>}
                      <button onClick={() => doDelete(p.id, p.code)} className="px-2.5 py-1 rounded-lg bg-red-500/15 text-red-300 text-xs hover:bg-red-500/25">删除</button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* 新建弹层 */}
        {showNew && (
          <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
            <div className="w-full max-w-lg rounded-2xl bg-ink-900 border border-white/10 p-6 space-y-4">
              <h2 className="text-base font-semibold text-white">新建页面</h2>
              <input value={nCode} onChange={(e) => setNCode(e.target.value)} placeholder="唯一 code（英文/数字/中划线，如 nuclear-overview）"
                className="w-full px-3 py-2 rounded-xl bg-white/[0.04] border border-white/10 text-sm text-white placeholder-gray-500 outline-none focus:border-violet-400/50" />
              <input value={nTitle} onChange={(e) => setNTitle(e.target.value)} placeholder="页面标题"
                className="w-full px-3 py-2 rounded-xl bg-white/[0.04] border border-white/10 text-sm text-white placeholder-gray-500 outline-none focus:border-violet-400/50" />
              <textarea value={nDesc} onChange={(e) => setNDesc(e.target.value)} placeholder="页面描述（可选）"
                className="w-full px-3 py-2 rounded-xl bg-white/[0.04] border border-white/10 text-sm text-white placeholder-gray-500 outline-none focus:border-violet-400/50" rows={2} />
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowNew(false)} className="px-4 py-2 rounded-xl bg-white/[0.06] text-gray-300 text-sm">取消</button>
                <button onClick={doCreate} disabled={saving} className="px-4 py-2 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white text-sm disabled:opacity-50">
                  {saving ? "创建中…" : "创建"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 编辑态：布局编排 */}
        {editing && (
          <div className="rounded-2xl bg-white/[0.03] border border-white/10 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold text-white">{editing.title}</div>
                <div className="text-[11px] text-gray-500 mt-0.5">布局编辑（保存后版本自动递增）· 当前 v{editing.version}</div>
              </div>
              <button onClick={() => setEditing(null)} className="text-xs text-gray-400 hover:text-gray-200">关闭编辑</button>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] text-gray-500">添加组件：</span>
              {widgetTypes.map((w) => (
                <button key={w.type} onClick={() => addWidget(w.type)}
                  className="px-3 py-1 rounded-lg bg-white/[0.06] text-gray-300 text-xs hover:bg-violet-500/20 hover:text-violet-200">
                  + {w.label}
                </button>
              ))}
            </div>

            <div className="space-y-3">
              {draftLayout.map((w, i) => (
                <div key={i} className="rounded-xl bg-white/[0.03] border border-white/10 p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] px-2 py-0.5 rounded-md bg-violet-500/15 text-violet-300">{widgetTypes.find((x) => x.type === w.widget)?.label || w.widget}</span>
                      <span className="text-[11px] text-gray-500 font-mono">{w.widget}</span>
                    </div>
                    <button onClick={() => setDraftLayout((ls) => ls.filter((_, j) => j !== i))}
                      className="text-[11px] text-red-400 hover:text-red-300">移除</button>
                  </div>
                  <input value={w.title} onChange={(e) => patchWidget(i, { title: e.target.value })}
                    placeholder="组件标题"
                    className="w-full px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/10 text-sm text-white placeholder-gray-500 outline-none focus:border-violet-400/50" />
                  {Object.entries(w.params || {}).map(([k, v]) => (
                    <div key={k} className="flex items-center gap-2">
                      <span className="text-[11px] text-gray-500 w-24 shrink-0">{k}</span>
                      <input value={String(v ?? "")} onChange={(e) => patchWidgetParam(i, k, e.target.value)}
                        className="flex-1 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/10 text-sm text-white outline-none focus:border-violet-400/50" />
                    </div>
                  ))}
                </div>
              ))}
              {draftLayout.length === 0 && (
                <div className="text-xs text-gray-500 py-6 text-center border border-dashed border-white/10 rounded-xl">还没有组件，点击上方「+ 添加组件」开始编排</div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2">
              <Link href={`/pages/${editing.code}`} className="px-4 py-2 rounded-xl bg-white/[0.06] text-gray-300 text-sm hover:bg-white/[0.1]">预览</Link>
              <button onClick={saveLayout} disabled={saving} className="px-4 py-2 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white text-sm disabled:opacity-50">
                {saving ? "保存中…" : "保存布局"}
              </button>
            </div>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
'''
build_p.parent.mkdir(parents=True, exist_ok=True)
build_p.write_text(build_page, encoding="utf-8")
print("pages/page.tsx written")

# ---------- 4) 运行时页 ----------
run_p = root / "app" / "pages" / "[code]" / "page.tsx"
run_page = '''"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import DashboardShell from "../../../components/DashboardShell";
import {
  authHeaders,
  fetchDataAssets,
  fetchOntologySnapshot,
  fetchPageByCode,
  fetchTasks,
  type AppPage,
  type PageWidget,
} from "../../../lib/api";

async function fetchOverviewKpis() {
  try {
    const res = await fetch("/api/backend/overview", { cache: "no-store", headers: authHeaders() });
    if (!res.ok) return [];
    const json = await res.json();
    const d = json?.data ?? json ?? {};
    return (d?.kpis ?? []).map((k: any) => ({
      label: k?.label || "",
      value: k?.value ?? "",
      unit: k?.unit || "",
    }));
  } catch {
    return [];
  }
}

/** 单个 Widget 渲染：运行时读取数据源并展示（40-02） */
function WidgetView({ w }: { w: PageWidget }) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let dead = false;
    (async () => {
      try {
        if (w.widget === "stat_cards") {
          setData({ kpis: await fetchOverviewKpis() });
        } else if (w.widget === "object_list") {
          const s = await fetchOntologySnapshot();
          const want = (w.params?.type as string) || "All";
          const nodes = want === "All" ? s.nodes : s.nodes.filter((n) => n.type === want);
          setData({ nodes });
        } else if (w.widget === "data_assets") {
          const r = await fetchDataAssets();
          setData({ items: r.items });
        } else if (w.widget === "tasks") {
          const limit = Number(w.params?.limit ?? 8) || 8;
          const r = await fetchTasks(undefined, limit);
          setData({ items: r.items });
        } else {
          setData({ note: (w.params?.content as string) || "" });
        }
      } catch (e: any) {
        if (!dead) setError(e?.message || "组件加载失败");
      }
    })();
    return () => { dead = true; };
  }, [w]);

  const card = "rounded-2xl bg-white/[0.03] border border-white/10 p-5";
  const th = "text-left text-[11px] text-gray-500 font-medium py-2 px-3";
  const td = "text-sm text-gray-200 py-2 px-3 border-t border-white/5";

  if (error) return <div className={`${card} text-red-300 text-sm`}>{error}</div>;

  if (w.widget === "stat_cards" && data?.kpis) {
    return (
      <div className="rounded-2xl bg-white/[0.03] border border-white/10 p-5">
        <div className="text-sm font-semibold text-white mb-4">{w.title || "核心指标"}</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {(data.kpis as any[]).map((k, i) => (
            <div key={i} className="rounded-xl bg-white/[0.03] border border-white/10 p-4">
              <div className="text-[11px] text-gray-500">{k.label}</div>
              <div className="text-xl font-semibold text-white mt-1">
                {k.value} <span className="text-xs text-gray-400 font-normal">{k.unit}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (w.widget === "object_list" && data?.nodes) {
    const nodes = data.nodes as { type: string; id: string }[];
    return (
      <div className={card}>
        <div className="text-sm font-semibold text-white mb-3">{w.title || "对象列表"}</div>
        {nodes.length === 0
          ? <div className="text-xs text-gray-500 py-4">暂无对象</div>
          : (
            <table className="w-full">
              <thead>
                <tr><th className={th}>类型</th><th className={th}>对象</th><th className={th}>操作</th></tr>
              </thead>
              <tbody>
                {nodes.slice(0, 30).map((n, i) => (
                  <tr key={i}>
                    <td className={td}>{n.type}</td>
                    <td className={td}>{n.id}</td>
                    <td className={td}>
                      <Link href={`/objects/${encodeURIComponent(n.type)}/${encodeURIComponent(n.id)}`}
                        className="text-violet-300 hover:text-violet-200 text-xs">查看详情 →</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    );
  }

  if (w.widget === "data_assets" && data?.items) {
    const items = data.items as any[];
    return (
      <div className={card}>
        <div className="text-sm font-semibold text-white mb-3">{w.title || "数据资产"}</div>
        {items.length === 0
          ? <div className="text-xs text-gray-500 py-4">暂无数据资产</div>
          : (
            <table className="w-full">
              <thead>
                <tr><th className={th}>名称</th><th className={th}>实体</th><th className={th}>行数</th><th className={th}>状态</th></tr>
              </thead>
              <tbody>
                {items.slice(0, 20).map((it) => (
                  <tr key={it.id}>
                    <td className={td}>{it.name}</td>
                    <td className={td}>{it.entity || "—"}</td>
                    <td className={td}>{it.row_count ?? "—"}</td>
                    <td className={td}>{it.status || it.source_status || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    );
  }

  if (w.widget === "tasks" && data?.items) {
    const items = data.items as any[];
    return (
      <div className={card}>
        <div className="text-sm font-semibold text-white mb-3">{w.title || "最近任务"}</div>
        {items.length === 0
          ? <div className="text-xs text-gray-500 py-4">暂无任务</div>
          : (
            <table className="w-full">
              <thead>
                <tr><th className={th}>任务</th><th className={th}>状态</th><th className={th}>Agent</th></tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.id}>
                    <td className={td}>{it.title}</td>
                    <td className={td}>{it.status}</td>
                    <td className={td}>{it.agent || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    );
  }

  if (w.widget === "text_note") {
    return (
      <div className={`${card} text-sm text-gray-300 leading-relaxed`}>
        {(w.params?.content as string) || w.title || ""}
      </div>
    );
  }

  return <div className={`${card} text-sm text-gray-400`}>组件加载中…</div>;
}

export default function PageRuntime({ params }: { params: Promise<{ code: string }> }) {
  const { code } = use(params);
  const [page, setPage] = useState<AppPage | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPageByCode(code)
      .then((p) => { setPage(p); setError(""); })
      .catch((e: any) => setError(e?.message || "页面不存在或未发布"));
      .finally(() => setLoading(false));
  }, [code]);

  if (loading) return <DashboardShell><div className="text-sm text-gray-400 py-10">加载中…</div></DashboardShell>;
  if (error || !page) {
    return (
      <DashboardShell>
        <div className="rounded-2xl bg-white/[0.03] border border-white/10 p-8 text-center space-y-3">
          <div className="text-lg text-white font-semibold">页面不可用</div>
          <div className="text-sm text-gray-400">{error || "页面不存在"}</div>
          <Link href="/pages" className="inline-block px-4 py-2 rounded-xl bg-white/[0.06] text-gray-300 text-sm hover:bg-white/[0.1]">返回低代码构建</Link>
        </div>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white">{page.title}</h1>
            {page.description && <p className="text-sm text-gray-400 mt-1">{page.description}</p>}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-gray-500">v{page.version}</span>
            <span className="text-[11px] px-2 py-0.5 rounded-md bg-white/[0.06] text-gray-400">{page.status === "published" ? "已发布" : "草稿预览"}</span>
            <Link href="/pages" className="px-3 py-1.5 rounded-lg bg-white/[0.06] text-gray-300 text-xs hover:bg-white/[0.1]">构建器</Link>
          </div>
        </div>
        {page.layout.length === 0
          ? <div className="rounded-2xl bg-white/[0.03] border border-dashed border-white/10 p-8 text-center text-sm text-gray-500">页面暂无组件，请到构建器添加</div>
          : (
            <div className="grid grid-cols-1 gap-4">
              {page.layout.map((w, i) => (
                <WidgetView key={i} w={w} />
              ))}
            </div>
          )}
      </div>
    </DashboardShell>
  );
}
'''
run_p.parent.mkdir(parents=True, exist_ok=True)
run_p.write_text(run_page, encoding="utf-8")
print("[code]/page.tsx written")