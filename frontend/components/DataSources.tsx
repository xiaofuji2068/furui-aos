"use client";

import { useState } from "react";
import { api } from "../lib/api";

/**
 * 数据连接状态（首页 + 可交互），匹配参考图样式：
 *   横向 5 真实卡片 + 1 个"+"添加占位卡，简洁紧凑。
 * - 真实卡：图标 + 系统名 + 状态文字 + "● 数据正常"
 * - 占位卡：仅一个 + 图标 + 点状边框
 * - 点击真实卡 → 详情抽屉（同步/记录/延迟/健康度 + 连接/断开）
 * - 点击占位卡 → 目录模态新增
 * 写操作回调 onChanged，让父级刷新总览。
 */

type SrcStatus = "connected" | "warning" | "error" | "disconnected" | "add";

const TONE: Record<string, string> = {
  blue: "bg-blue-500/15 text-blue-300",
  violet: "bg-violet-500/15 text-violet-300",
  emerald: "bg-emerald-500/15 text-emerald-300",
  sky: "bg-sky-500/15 text-sky-300",
  amber: "bg-amber-500/15 text-amber-300",
  rose: "bg-rose-500/15 text-rose-300",
  cyan: "bg-cyan-500/15 text-cyan-300",
  gray: "bg-white/[0.04] text-gray-400 border-dashed border-white/10",
};

const STATUS_META: Record<string, { label: string; dot: string; text: string; bar: string }> = {
  connected:    { label: "数据正常",     dot: "bg-emerald-400", text: "text-emerald-300", bar: "bg-emerald-400" },
  warning:      { label: "数据正常",     dot: "bg-emerald-400", text: "text-emerald-300", bar: "bg-emerald-400" }, // 警告也展示"数据正常"绿色文案，保持视觉一致
  error:        { label: "连接异常",     dot: "bg-rose-400",    text: "text-rose-300",    bar: "bg-rose-400" },
  disconnected: { label: "未连接",       dot: "bg-gray-500",    text: "text-gray-400",    bar: "bg-gray-500" },
};

export default function DataSources({ items, onChanged }: { items: any[]; onChanged?: () => void }) {
  const [detail, setDetail] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const [showAdd, setShowAdd] = useState(false);
  const [catalog, setCatalog] = useState<any[]>([]);
  const [picked, setPicked] = useState<any | null>(null);
  const [addName, setAddName] = useState("");
  const [addErr, setAddErr] = useState("");

  async function openDetail(id: string) {
    setDetailLoading(true);
    setDetail({ id });
    try {
      setDetail(await api.get<any>(`/data-sources/${encodeURIComponent(id)}`));
    } finally {
      setDetailLoading(false);
    }
  }

  async function toggle(id: string) {
    setBusy(true);
    try {
      await api.post(`/data-sources/${encodeURIComponent(id)}/toggle`);
      setDetail(await api.get<any>(`/data-sources/${encodeURIComponent(id)}`));
      onChanged?.();
    } finally {
      setBusy(false);
    }
  }

  async function openAdd() {
    setShowAdd(true);
    setPicked(null);
    setAddName("");
    setAddErr("");
    if (catalog.length === 0) {
      const data = await api.get<{ items: any[] }>("/data-sources/catalog");
      setCatalog(data.items || []);
    }
  }

  async function submitAdd() {
    if (!picked) return setAddErr("请选择一个数据源类型");
    setBusy(true);
    setAddErr("");
    try {
      await api.post("/data-sources", {
          id: picked.type + "_" + Date.now().toString().slice(-5),
          name: addName.trim() || picked.name,
          icon: picked.icon,
          tone: picked.tone,
          category: picked.category,
          type: picked.type,
          desc: picked.desc,
        });
      setShowAdd(false);
      onChanged?.();
    } catch (e: any) {
      setAddErr(e.message || "添加失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {/* 横向 5+1 卡片，匹配参考图紧凑样式 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {items.map((it, i) => {
          const isAdd = it.status === "add";
          const toneCls = TONE[it.tone || "gray"] || TONE.gray;
          const meta = STATUS_META[it.status] || STATUS_META.disconnected;
          const showOk = !isAdd && (it.status === "connected" || it.status === "warning");

          if (isAdd) {
            return (
              <button
                key={i}
                onClick={openAdd}
                className="flex items-center justify-center h-[88px] rounded-xl border border-dashed border-white/10 bg-white/[0.02] text-gray-500 hover:border-white/25 hover:text-gray-300 hover:bg-white/[0.05] transition"
                title="添加数据源"
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </button>
            );
          }

          return (
            <button
              key={i}
              onClick={() => openDetail(it.id)}
              className="h-[88px] rounded-xl border border-white/5 bg-white/[0.03] hover:border-white/15 hover:bg-white/[0.05] transition text-left px-3.5 py-2.5 flex flex-col justify-between"
            >
              <div className="flex items-center justify-between">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm ${toneCls}`}>
                  {it.icon}
                </div>
              </div>
              <div className="text-sm font-medium text-gray-100 truncate leading-tight">{it.name}</div>
              <div className="flex items-center gap-1.5 text-[11px]">
                {showOk ? (
                  <>
                    <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                    <span className={meta.text}>数据正常</span>
                  </>
                ) : (
                  <>
                    <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                    <span className={meta.text}>{meta.label}</span>
                  </>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* 详情抽屉 */}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setDetail(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-md rounded-2xl border border-white/10 glass-strong p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {detailLoading ? (
              <div className="py-10 text-center text-gray-400 text-sm">加载中…</div>
            ) : (
              <>
                <div className="flex items-center gap-3 mb-4">
                  <div className={`w-11 h-11 rounded-xl flex items-center justify-center text-xl ${TONE[detail.tone] || TONE.gray}`}>
                    {detail.icon}
                  </div>
                  <div>
                    <div className="text-base font-semibold">{detail.name}</div>
                    <div className="text-xs text-gray-400">{detail.category} · {detail.type}</div>
                  </div>
                  <span className={`ml-auto text-xs px-2 py-1 rounded-full ${STATUS_META[detail.status]?.text} bg-white/5`}>
                    {STATUS_META[detail.status]?.label}
                  </span>
                </div>

                <p className="text-sm text-gray-400 mb-4">{detail.desc}</p>

                <div className="grid grid-cols-3 gap-3 mb-4">
                  <Stat label="最后同步" value={detail.last_sync} />
                  <Stat label="记录数" value={detail.records} />
                  <Stat label="延迟" value={detail.latency_ms ? detail.latency_ms + " ms" : "—"} />
                </div>

                <div className="mb-5">
                  <div className="flex items-center justify-between text-xs text-gray-400 mb-1.5">
                    <span>数据健康度</span>
                    <span className={STATUS_META[detail.status]?.text}>{detail.health}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                    <div className={`h-full rounded-full ${STATUS_META[detail.status]?.bar}`} style={{ width: `${detail.health || 0}%` }} />
                  </div>
                </div>

                {detail.config && Object.keys(detail.config).length > 0 && (
                  <div className="mb-5 rounded-lg border border-white/5 bg-black/20 p-3 text-xs text-gray-400 space-y-1">
                    {Object.entries(detail.config).map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-gray-500">{k}</span>
                        <span className="text-gray-300">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex gap-2">
                  <button
                    disabled={busy}
                    onClick={() => toggle(detail.id)}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50 ${
                      detail.status === "disconnected" || detail.status === "error"
                        ? "bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30"
                        : "bg-rose-500/20 text-rose-300 hover:bg-rose-500/30"
                    }`}
                  >
                    {busy ? "处理中…" : detail.status === "disconnected" || detail.status === "error" ? "连接" : "断开连接"}
                  </button>
                  <button onClick={() => setDetail(null)} className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:bg-white/5">
                    关闭
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* 添加数据源 */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowAdd(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-lg rounded-2xl border border-white/10 glass-strong p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="text-base font-semibold mb-1">添加数据源</div>
            <div className="text-xs text-gray-400 mb-4">从目录选择一个类型，接入企业数据</div>

            <div className="grid grid-cols-4 gap-2 max-h-56 overflow-y-auto mb-4">
              {catalog.map((c, i) => (
                <button
                  key={i}
                  onClick={() => { setPicked(c); setAddName(c.name); }}
                  className={`rounded-xl border p-3 text-left transition ${
                    picked === c ? "border-violet-400/40 bg-violet-500/10" : "border-white/5 hover:border-white/15 bg-white/[0.02]"
                  }`}
                >
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-base mb-2 ${TONE[c.tone] || TONE.gray}`}>{c.icon}</div>
                  <div className="text-xs font-medium truncate">{c.name}</div>
                  <div className="text-[10px] text-gray-500 truncate">{c.category}</div>
                </button>
              ))}
            </div>

            {picked && (
              <div className="mb-4">
                <label className="text-xs text-gray-400">显示名称</label>
                <input
                  value={addName}
                  onChange={(e) => setAddName(e.target.value)}
                  className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm text-gray-100 outline-none focus:border-violet-400/40"
                  placeholder="数据源名称"
                />
                <p className="text-[11px] text-gray-500 mt-1.5">{picked.desc}</p>
              </div>
            )}

            {addErr && <div className="text-xs text-rose-300 mb-3">{addErr}</div>}

            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowAdd(false)} className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:bg-white/5">取消</button>
              <button
                disabled={busy}
                onClick={submitAdd}
                className="px-4 py-2 rounded-lg text-sm font-medium bg-violet-500/20 text-violet-200 hover:bg-violet-500/30 disabled:opacity-50"
              >
                {busy ? "接入中…" : "确认接入"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-lg border border-white/5 bg-black/20 p-2.5">
      <div className="text-[10px] text-gray-500 mb-1">{label}</div>
      <div className="text-sm font-medium text-gray-200 truncate">{value}</div>
    </div>
  );
}
