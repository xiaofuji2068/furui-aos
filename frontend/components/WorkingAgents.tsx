"use client";

import Link from "next/link";

const STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  working:          { text: "工作中",      cls: "bg-emerald-500/15 text-emerald-300" },
  idle:             { text: "空闲",        cls: "bg-gray-500/15 text-gray-300" },
  waiting:          { text: "等待确认",    cls: "bg-amber-500/15 text-amber-300" },
  waiting_human:    { text: "等待确认",    cls: "bg-amber-500/15 text-amber-300" },
  error:            { text: "异常",        cls: "bg-rose-500/15 text-rose-300" },
};

// 注意：Tailwind 只扫描源码里的字面量类名，这里必须写全，不能动态拼接
const AVATAR_BG: Record<string, string> = {
  "销售分析师":     "bg-gradient-to-br from-rose-500/40 to-orange-500/30",
  "财务助手":       "bg-gradient-to-br from-emerald-500/40 to-teal-500/30",
  "设备运维工程师": "bg-gradient-to-br from-sky-500/40 to-blue-500/30",
  "知识助手":       "bg-gradient-to-br from-violet-500/40 to-purple-500/30",
};

export default function WorkingAgents({ agents }: { agents: any[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {agents.map(a => {
        const st = STATUS_LABEL[a.status] || STATUS_LABEL.idle;
        const bg = AVATAR_BG[a.name] || "bg-gradient-to-br from-slate-500/40 to-slate-600/30";
        return (
          <Link key={a.name} href={`/employees/${encodeURIComponent(a.name)}`} className="block glass-strong rounded-2xl p-5 border border-white/5 hover:border-white/10 transition">
            <div className="flex items-start gap-3">
              <div className={`relative w-12 h-12 rounded-xl ${bg} flex items-center justify-center text-2xl shadow-glow`}>
                {a.avatar}
                {a.status === "working" && (
                  <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-400 ring-2 ring-ink-900 animate-pulse2" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <div className="font-medium truncate">{a.name}</div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full ${st.cls}`}>{st.text}</span>
                </div>
                <div className="text-xs text-gray-400 truncate">{a.role}</div>
              </div>
            </div>

            <div className="mt-4">
              <div className="flex items-center justify-between text-[11px] text-gray-400">
                <span>进度</span>
                <span className="text-gray-300">{a.progress}%</span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                <div className="h-full bg-gradient-to-r from-violet-500 to-blue-500 transition-all"
                     style={{ width: `${a.progress}%` }} />
              </div>
            </div>

            <div className="mt-4">
              <div className="text-[11px] text-gray-400">当前任务</div>
              <div className="text-sm mt-0.5 truncate">{a.current_task}</div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
