"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import DashboardShell from "../../components/DashboardShell";
import { useAuth } from "../../components/AuthProvider";
import {
  createPage,
  deletePage,
  draftPage,
  fetchPageByCode,
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
      const detail = await fetchPageByCode(p.code);
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
