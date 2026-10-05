"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import DashboardShell from "../../components/DashboardShell";
import { authHeaders } from "../../lib/api";

const API = "/api/backend";

export default function ScenesPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetch(`${API}/scenes`, { headers: authHeaders() })
      .then(r => r.json())
      .then(d => { setData(d && d.data ? d.data : null); })
      .catch(() => setData(null));
  }, []);

  if (!data || !Array.isArray(data.stages) || !Array.isArray(data.scenes)) {
    return <DashboardShell><Skeleton /></DashboardShell>;
  }

  const { stages, scenes } = data;

  return (
    <DashboardShell>
      <div>
        <h1 className="text-2xl font-semibold">{data.title}</h1>
        <p className="text-sm text-gray-400 mt-1">{data.subtitle}</p>
      </div>

      {/* 流程搭建步骤条 */}
      <section className="glass-strong rounded-2xl p-5 border border-white/5">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-medium">场景流程搭建</h3>
          <button className="text-xs text-gray-400 hover:text-gray-200">自定义流程 →</button>
        </div>
        <div className="flex items-center gap-3">
          {stages.map((s: any, i: number) => (
            <div key={s.code} className="flex items-center gap-3 flex-1">
              <div className={`flex-1 rounded-xl px-4 py-3 border ${
                s.active
                  ? "bg-gradient-to-r from-violet-500/25 to-blue-500/15 border-violet-400/40 shadow-glow"
                  : "bg-white/[0.03] border-white/5"
              }`}>
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] font-mono ${s.active ? "text-violet-300" : "text-gray-500"}`}>{s.code}</span>
                  {s.active && <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/30 text-violet-200">当前阶段</span>}
                </div>
                <div className={`text-sm font-medium mt-1 ${s.active ? "text-white" : "text-gray-300"}`}>{s.title}</div>
                <div className="text-[10px] text-gray-500 mt-0.5">{s.desc}</div>
              </div>
              {i < stages.length - 1 && (
                <div className={`shrink-0 text-lg ${s.active ? "text-violet-300" : "text-gray-600"}`}>→</div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* 场景卡片 */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-medium">推荐场景</h3>
          <button className="text-xs text-gray-400 hover:text-gray-200">全部场景 →</button>
        </div>
        <div className="grid grid-cols-3 gap-5">
          {scenes.map((s: any) => (
            <div key={s.id} className={`relative overflow-hidden rounded-2xl p-5 bg-gradient-to-br ${s.color} border ${s.border} glass-strong hover:scale-[1.01] transition`}>
              <div className="flex items-center justify-between mb-3">
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${s.badge}`}>{s.level}</span>
                <button className="text-xs text-gray-400 hover:text-gray-200">⋯</button>
              </div>
              <div className="text-base font-medium mb-1.5">{s.name}</div>
              <div className="text-xs text-gray-400 leading-relaxed">{s.desc}</div>

              <div className="mt-4 space-y-2">
                {s.metrics.map((m: any) => (
                  <div key={m.label} className="flex items-center justify-between text-xs">
                    <span className="text-gray-400">{m.label}</span>
                    <span className="text-emerald-300 font-medium">{m.value}</span>
                  </div>
                ))}
              </div>

              <div className="mt-4 flex items-center gap-1">
                <span className="text-[10px] text-gray-500 mr-1">应用 AI 员工</span>
                {s.agents.map((a: string) => (
                  <span key={a} className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] border border-white/5">{a}</span>
                ))}
              </div>

              <button onClick={() => router.push("/workbench")} className="mt-4 w-full text-xs py-2 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white shadow-glow">
                进入场景
              </button>
            </div>
          ))}
        </div>
      </section>
    </DashboardShell>
  );
}

function Skeleton() {
  return (
    <div className="space-y-5 animate-pulse2">
      <div className="h-8 w-40 rounded-lg bg-white/[0.04]" />
      <div className="h-28 rounded-2xl bg-white/[0.03]" />
      <div className="grid grid-cols-3 gap-5">
        {[0, 1, 2].map(i => <div key={i} className="h-64 rounded-2xl bg-white/[0.03]" />)}
      </div>
    </div>
  );
}