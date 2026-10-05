"use client";

import { useEffect, useState } from "react";
import DashboardShell from "../../../components/DashboardShell";

const API = "/api/backend";

export default function EmployeeDetailPage({ params }: { params: { id: string } }) {
  const name = decodeURIComponent(params.id);
  const [e, setE] = useState<any>(null);

  useEffect(() => {
    setE(null);
    fetch(`${API}/employees/${encodeURIComponent(name)}`)
      .then(r => {
        if (!r.ok) throw new Error(`employee not found (${r.status})`);
        return r.json();
      })
      .then(d => setE(d.data ?? d))   // 兼容统一包装 {code,message,data} 与裸返回
      .catch(() => setE(null));
  }, [name]);

  if (!e) return <DashboardShell><Skeleton /></DashboardShell>;

  return (
    <DashboardShell>
      {/* 顶部员工卡 */}
      <div className="glass-strong rounded-2xl p-5 border border-white/5 flex items-start gap-5">
        <div className={`w-20 h-20 rounded-2xl bg-gradient-to-br ${e.color} flex items-center justify-center text-4xl shadow-glow relative`}>
          {e.avatar}
          <span className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 ring-2 ring-ink-900 animate-pulse2" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <h1 className="text-xl font-semibold">{e.name}</h1>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
              {e.status === "working" ? "工作中" : e.status === "idle" ? "空闲" : e.status}
            </span>
          </div>
          <p className="text-xs text-gray-400 mb-3">{e.role}</p>

          <div className="flex items-center gap-3 mb-4">
            {e.tags?.map((t: any) => (
              <span key={t.label} className="text-xs px-2.5 py-1 rounded-lg bg-white/[0.04] border border-white/5">
                {t.label} ★ {t.value}
              </span>
            ))}
          </div>

          <div className="grid grid-cols-3 gap-3 max-w-3xl">
            {e.metrics?.map((m: any) => (
              <div key={m.label} className="glass rounded-xl px-4 py-3 border border-white/5">
                <div className="text-[11px] text-gray-400">{m.label}</div>
                <div className="mt-0.5 flex items-baseline gap-1">
                  <span className="text-2xl font-semibold text-gradient-blue">{m.value}</span>
                  <span className="text-xs text-gray-500">{m.unit}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 三列：日志 / 能力 / 权限 */}
      <div className="grid grid-cols-12 gap-5">
        <section className="col-span-5 glass-strong rounded-2xl p-5 border border-white/5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium">工作日志</h3>
            <button className="text-xs text-gray-400 hover:text-gray-200">查看更多 →</button>
          </div>
          <div className="relative pl-4">
            <div className="absolute left-[6px] top-1 bottom-1 w-px bg-gradient-to-b from-violet-500/40 via-white/10 to-transparent" />
            <ul className="space-y-3">
              {e.logs?.map((l: any, i: number) => (
                <li key={i} className="relative flex items-start gap-3">
                  <span className="absolute -left-[14px] top-1.5 w-2 h-2 rounded-full bg-violet-400 ring-4 ring-violet-500/15" />
                  <span className="text-[11px] text-gray-500 tabular-nums shrink-0 w-10">{l.time}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-200">{l.event}</div>
                    <span className={`inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded ${l.tagCls}`}>{l.tag}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="col-span-3 glass-strong rounded-2xl p-5 border border-white/5">
          <h3 className="text-sm font-medium mb-4">能力配置</h3>
          <ul className="space-y-2">
            {e.capabilities?.map((c: string) => (
              <li key={c} className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-sm text-gray-200">
                <span>{c}</span>
                <span className="text-emerald-300 text-xs">✓</span>
              </li>
            ))}
          </ul>
          <button className="mt-4 w-full text-xs py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/5">
            + 添加能力
          </button>
        </section>

        <section className="col-span-4 glass-strong rounded-2xl p-5 border border-white/5">
          <h3 className="text-sm font-medium mb-4">权限设置</h3>
          <ul className="space-y-2">
            {e.permissions?.map((p: any) => (
              <li key={p.name} className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 text-sm">
                <span className="text-gray-200">{p.name}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                  p.granted ? "bg-emerald-500/15 text-emerald-300" : "bg-gray-500/15 text-gray-400"
                }`}>
                  {p.granted ? "已授权" : "未授权"}
                </span>
              </li>
            ))}
          </ul>
          <button className="mt-4 w-full text-xs py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/5">
            调整权限
          </button>
        </section>
      </div>

      {/* 底部按钮 */}
      <div className="flex items-center justify-end gap-3 pb-2">
        <button className="text-sm px-5 py-2.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/5">
          人工运维
        </button>
        <button className="text-sm px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white shadow-glow">
          确认运行
        </button>
      </div>
    </DashboardShell>
  );
}

function Skeleton() {
  return (
    <div className="space-y-5 animate-pulse2">
      <div className="h-36 rounded-2xl bg-white/[0.03]" />
      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-5 h-72 rounded-2xl bg-white/[0.03]" />
        <div className="col-span-3 h-72 rounded-2xl bg-white/[0.03]" />
        <div className="col-span-4 h-72 rounded-2xl bg-white/[0.03]" />
      </div>
    </div>
  );
}