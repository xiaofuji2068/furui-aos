"use client";

import { useEffect, useState } from "react";
import DashboardShell from "../../../components/DashboardShell";
import ModelKeysCard from "../../../components/ModelKeysCard";
import { authHeaders } from "../../../lib/api";

const API = "/api/backend";

const STATUS_BADGE: Record<string, { text: string; cls: string }> = {
  connected:    { text: "已连接", cls: "bg-emerald-500/15 text-emerald-300" },
  warning:      { text: "告警",   cls: "bg-amber-500/15 text-amber-300" },
  error:        { text: "异常",   cls: "bg-rose-500/15 text-rose-300" },
  disconnected: { text: "未连接", cls: "bg-gray-500/15 text-gray-400" },
};

const TONE: Record<string, string> = {
  blue: "bg-blue-500/15 text-blue-300",
  violet: "bg-violet-500/15 text-violet-300",
  emerald: "bg-emerald-500/15 text-emerald-300",
  sky: "bg-sky-500/15 text-sky-300",
  amber: "bg-amber-500/15 text-amber-300",
  rose: "bg-rose-500/15 text-rose-300",
  cyan: "bg-cyan-500/15 text-cyan-300",
};

export default function AdminPage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // data 页需要目录用于"新增"
  const [catalog, setCatalog] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [picked, setPicked] = useState<any | null>(null);
  const [addName, setAddName] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    fetch(`${API}/admin/${slug}`, { headers: authHeaders() })
      .then(r => r.json())
      .then(d => { setData(d?.data ?? d); setLoading(false); })
      .catch(() => setLoading(false));
  }

  useEffect(() => {
    load();
    if (slug === "data") {
      fetch(`${API}/data-sources/catalog`, { headers: authHeaders() }).then(r => r.json()).then(d => setCatalog(d?.data?.items || [])).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  async function toggleRow(id: string) {
    setBusy(true);
    try {
      await fetch(`${API}/data-sources/${encodeURIComponent(id)}/toggle`, { method: "POST", headers: authHeaders() });
      load();
    } finally { setBusy(false); }
  }

  async function deleteRow(id: string) {
    setBusy(true);
    try {
      await fetch(`${API}/data-sources/${encodeURIComponent(id)}`, { method: "DELETE", headers: authHeaders() });
      load();
    } finally { setBusy(false); }
  }

  async function submitAdd() {
    if (!picked) return;
    setBusy(true);
    try {
      await fetch(`${API}/data-sources`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          id: picked.type + "_" + Date.now().toString().slice(-5),
          name: addName.trim() || picked.name,
          icon: picked.icon, tone: picked.tone, category: picked.category,
          type: picked.type, desc: picked.desc,
        }),
      });
      setShowAdd(false); setPicked(null); setAddName("");
      load();
    } finally { setBusy(false); }
  }

  if (loading) return <DashboardShell><div className="h-40 rounded-2xl bg-white/[0.03] animate-pulse2" /></DashboardShell>;
  if (!data) return <DashboardShell><div className="text-gray-400 text-sm">页面不存在</div></DashboardShell>;

  return (
    <DashboardShell>
      <div className="flex items-end justify-between mb-5">
        <div>
          <h1 className="text-2xl font-semibold">{data.title}</h1>
          <p className="text-sm text-gray-400 mt-1">{data.desc}</p>
        </div>
        {slug === "data" && (
          <button onClick={() => setShowAdd(true)}
            className="text-sm px-4 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white shadow-glow hover:opacity-90">
            + 新增数据源
          </button>
        )}
      </div>

      {data.kind === "table" && <TableView data={data} onToggle={toggleRow} onDelete={deleteRow} busy={busy} />}
      {data.kind === "cards" && <CardsView data={data} />}
      {data.kind === "matrix" && <MatrixView data={data} />}
      {data.kind === "settings" && <SettingsView data={data} />}
      {slug === "model" && <ModelKeysCard />}

      {/* 新增数据源 modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowAdd(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-lg rounded-2xl border border-white/10 glass-strong p-5 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="text-base font-semibold mb-1">新增数据源</div>
            <div className="text-xs text-gray-400 mb-4">从目录选择一个类型接入企业数据</div>
            <div className="grid grid-cols-4 gap-2 max-h-56 overflow-y-auto mb-4">
              {catalog.map((c, i) => (
                <button key={i} onClick={() => { setPicked(c); setAddName(c.name); }}
                  className={`rounded-xl border p-3 text-left transition ${
                    picked === c ? "border-violet-400/40 bg-violet-500/10" : "border-white/5 hover:border-white/15 bg-white/[0.02]"
                  }`}>
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-base mb-2 ${TONE[c.tone] || TONE.blue}`}>{c.icon}</div>
                  <div className="text-xs font-medium truncate">{c.name}</div>
                </button>
              ))}
            </div>
            {picked && (
              <div className="mb-4">
                <label className="text-xs text-gray-400">显示名称</label>
                <input value={addName} onChange={e => setAddName(e.target.value)}
                  className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm outline-none focus:border-violet-400/40" />
              </div>
            )}
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowAdd(false)} className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:bg-white/5">取消</button>
              <button disabled={busy} onClick={submitAdd}
                className="px-4 py-2 rounded-lg text-sm font-medium bg-violet-500/20 text-violet-200 hover:bg-violet-500/30 disabled:opacity-50">
                {busy ? "接入中…" : "确认接入"}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardShell>
  );
}

function TableView({ data, onToggle, onDelete, busy }: any) {
  const isData = data.actions;
  const levelCls: Record<string, string> = {
    info: "text-sky-300", warn: "text-amber-300", error: "text-rose-300",
  };
  return (
    <div>
      {data.note && <div className="text-xs text-gray-500 mb-3">{data.note}</div>}
      <div className="glass-strong rounded-2xl border border-white/5 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-400 border-b border-white/5">
            {data.columns.map((c: any) => <th key={c.key} className="px-4 py-3 font-medium">{c.label}</th>)}
            {isData && <th className="px-4 py-3 font-medium text-right">操作</th>}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r: any, i: number) => {
            const badge = STATUS_BADGE[r.status];
            return (
              <tr key={i} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02]">
                {data.columns.map((c: any) => (
                  <td key={c.key} className="px-4 py-3">
                    {c.key === "status" && badge ? (
                      <span className={`text-[11px] px-2 py-0.5 rounded-full ${badge.cls}`}>{badge.text}</span>
                    ) : c.key === "level" ? (
                      <span className={levelCls[r.level] || "text-gray-300"}>{r.level}</span>
                    ) : (
                      <span className="text-gray-200">{r[c.key]}</span>
                    )}
                  </td>
                ))}
                {isData && (
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    <button disabled={busy} onClick={() => onToggle(r.id)}
                      className="text-xs px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/5 mr-1">
                      {r.status === "connected" ? "断开" : "连接"}
                    </button>
                    <button disabled={busy} onClick={() => onDelete(r.id)}
                      className="text-xs px-2.5 py-1 rounded-lg bg-rose-500/15 text-rose-300 hover:bg-rose-500/25 border border-rose-400/20">
                      删除
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </div>
  );
}

function CardsView({ data }: any) {
  return (
    <div>
      {data.note && <div className="text-xs text-gray-500 mb-3">当前模型：{data.note}</div>}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.cards.map((c: any, i: number) => {
          const badge = STATUS_BADGE[c.status];
          return (
            <div key={i} className="glass-strong rounded-2xl p-5 border border-white/5">
              <div className="flex items-start gap-3">
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center text-xl ${TONE[c.tone] || TONE.blue}`}>{c.icon || "🧩"}</div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium">{c.name}</div>
                  {c.provider && <div className="text-xs text-gray-500">{c.provider}</div>}
                </div>
                {badge && <span className={`text-[10px] px-2 py-0.5 rounded-full ${badge.cls}`}>{badge.text}</span>}
              </div>
              <p className="text-xs text-gray-400 mt-3">{c.desc}</p>
              {typeof c.health === "number" && (
                <div className="mt-3">
                  <div className="flex justify-between text-[11px] text-gray-500 mb-1"><span>集成健康度</span><span>{c.health}%</span></div>
                  <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-violet-500 to-blue-500" style={{ width: `${c.health}%` }} />
                  </div>
                </div>
              )}
              {c.type && <div className="text-[11px] text-gray-500 mt-3">类型：{c.type}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MatrixView({ data }: any) {
  return (
    <div className="glass-strong rounded-2xl border border-white/5 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-gray-400 border-b border-white/5">
            <th className="px-4 py-3 text-left font-medium">权限 \ 角色</th>
            {data.roles.map((r: string) => <th key={r} className="px-4 py-3 text-center font-medium">{r}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.perms.map((p: string) => (
            <tr key={p} className="border-b border-white/5 last:border-0">
              <td className="px-4 py-3 text-gray-200">{p}</td>
              {data.roles.map((r: string) => (
                <td key={r} className="px-4 py-3 text-center">
                  {data.matrix[p][r]
                    ? <span className="text-emerald-300">✓</span>
                    : <span className="text-gray-600">—</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SettingsView({ data }: any) {
  const [vals, setVals] = useState<Record<string, any>>({});
  const [saved, setSaved] = useState(false);
  const get = (f: any) => (f.key in vals ? vals[f.key] : f.value);

  async function save() {
    const fields = data.fields.map((f: any) => ({ key: f.key, value: get(f) }));
    await fetch(`${API}/admin/settings`, {
      method: "POST", headers: authHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ fields }),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="glass-strong rounded-2xl p-6 border border-white/5 max-w-2xl space-y-4">
      {data.fields.map((f: any) => (
        <div key={f.key} className="flex items-center justify-between gap-4">
          <label className="text-sm text-gray-300">{f.label}</label>
          {f.type === "toggle" ? (
            <button onClick={() => setVals(v => ({ ...v, [f.key]: !get(f) }))}
              className={`w-11 h-6 rounded-full relative transition ${get(f) ? "bg-violet-500" : "bg-white/10"}`}>
              <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${get(f) ? "left-[22px]" : "left-0.5"}`} />
            </button>
          ) : (
            <input value={String(get(f))} onChange={e => setVals(v => ({ ...v, [f.key]: e.target.value }))}
              className="w-64 rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm outline-none focus:border-violet-400/40" />
          )}
        </div>
      ))}
      <div className="flex items-center gap-3 pt-2">
        <button onClick={save} className="text-sm px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white shadow-glow hover:opacity-90">
          保存设置
        </button>
        {saved && <span className="text-xs text-emerald-300">已保存至数据库</span>}
      </div>
    </div>
  );
}
