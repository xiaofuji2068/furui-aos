"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import DashboardShell from "../../components/DashboardShell";

const API = "/api/backend";

// 任意名字都能取到配色，避免写死映射
const PALETTE = [
  "from-rose-500/40 to-orange-500/30",
  "from-emerald-500/40 to-teal-500/30",
  "from-sky-500/40 to-blue-500/30",
  "from-violet-500/40 to-purple-500/30",
  "from-amber-500/40 to-yellow-500/30",
  "from-cyan-500/40 to-sky-500/30",
  "from-pink-500/40 to-rose-500/30",
];

const STATUS: Record<string, { text: string; cls: string }> = {
  working:       { text: "工作中",   cls: "bg-emerald-500/15 text-emerald-300" },
  idle:          { text: "空闲",     cls: "bg-gray-500/15 text-gray-300" },
  waiting_human: { text: "等待确认", cls: "bg-amber-500/15 text-amber-300" },
  error:         { text: "异常",     cls: "bg-rose-500/15 text-rose-300" },
};

const FILTERS = [
  { key: "all", label: "全部" },
  { key: "working", label: "工作中" },
  { key: "idle", label: "空闲" },
  { key: "waiting_human", label: "等待确认" },
  { key: "error", label: "异常" },
];

export default function EmployeesPage() {
  const [list, setList] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/employees`)
      .then(r => r.json())
      .then(d => { setList(d.data?.items || d.items || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    return list.filter(e => {
      const matchQ = !q || (e.name + e.role).includes(q);
      const matchF = filter === "all" || e.status === filter;
      return matchQ && matchF;
    });
  }, [list, q, filter]);

  return (
    <DashboardShell>
      <div className="flex items-end justify-between mb-5">
        <div>
          <h1 className="text-2xl font-semibold">AI 员工</h1>
          <p className="text-sm text-gray-400 mt-1">企业内已部署的 AI 数字员工，点击查看档案、能力与权限。</p>
        </div>
        <Link
          href="/employees/new"
          className="text-sm px-4 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white shadow-glow hover:opacity-90"
        >
          + 创建 AI 员工
        </Link>
      </div>

      {/* 搜索 + 筛选 */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="relative flex-1 min-w-[220px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">🔍</span>
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="搜索员工名称或角色…"
            className="w-full rounded-xl bg-white/[0.04] border border-white/10 pl-9 pr-3 py-2.5 text-sm text-gray-100 outline-none focus:border-violet-400/40"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1.5 rounded-lg text-xs transition ${
                filter === f.key
                  ? "bg-violet-500/20 text-violet-200 border border-violet-400/30"
                  : "bg-white/[0.03] text-gray-400 border border-white/5 hover:text-gray-200"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[0, 1, 2].map(i => <div key={i} className="h-32 rounded-2xl bg-white/[0.03] animate-pulse2" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center text-gray-500 text-sm py-16">没有匹配的 AI 员工</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((e, i) => {
            const st = STATUS[e.status] || STATUS.idle;
            const bg = PALETTE[i % PALETTE.length];
            return (
              <Link
                key={e.name}
                href={`/employees/${encodeURIComponent(e.name)}`}
                className="glass-strong rounded-2xl p-5 border border-white/5 hover:border-white/15 hover:-translate-y-0.5 transition group"
              >
                <div className="flex items-start gap-3">
                  <div className={`relative w-12 h-12 rounded-xl bg-gradient-to-br ${bg} flex items-center justify-center text-2xl shadow-glow`}>
                    {e.avatar}
                    {e.status === "working" && (
                      <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-400 ring-2 ring-ink-900 animate-pulse2" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-medium truncate">{e.name}</div>
                      <span className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full ${st.cls}`}>{st.text}</span>
                    </div>
                    <div className="text-xs text-gray-400 truncate mt-0.5">{e.role}</div>
                  </div>
                </div>
                <div className="mt-4 text-xs text-gray-500 group-hover:text-violet-300 transition">查看档案 →</div>
              </Link>
            );
          })}
        </div>
      )}
    </DashboardShell>
  );
}
