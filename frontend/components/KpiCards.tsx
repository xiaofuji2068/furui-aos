"use client";

const COLOR: Record<string, { bg: string; ring: string; text: string; icon: string; unit: string }> = {
  "ai_employees_total":   { bg: "from-violet-500/20 to-violet-500/0",   ring: "ring-violet-500/30",  text: "text-violet-300",  icon: "👥", unit: "个" },
  "ai_employees_working": { bg: "from-sky-500/20 to-sky-500/0",         ring: "ring-sky-500/30",     text: "text-sky-300",     icon: "⚙", unit: "个" },
  "tasks_pending":        { bg: "from-amber-500/20 to-amber-500/0",     ring: "ring-amber-500/30",   text: "text-amber-300",   icon: "📋", unit: "项" },
  "tasks_completed":      { bg: "from-emerald-500/20 to-emerald-500/0", ring: "ring-emerald-500/30", text: "text-emerald-300", icon: "✅", unit: "项" },
};

export default function KpiCards({ kpis }: { kpis?: any }) {
  const items = kpis ? Object.entries(kpis).map(([k, v]: any) => ({ key: k, ...v })) : [];
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {items.map(it => {
        const c = COLOR[it.key] || COLOR["ai_employees_total"];
        const positive = it.delta >= 0;
        return (
          <div key={it.key} className={`relative overflow-hidden rounded-2xl glass-strong p-5 ring-1 ${c.ring}`}>
            <div className={`absolute inset-0 bg-gradient-to-br ${c.bg} pointer-events-none`} />
            <div className="relative">
              <div className={`w-9 h-9 rounded-lg bg-white/[0.06] flex items-center justify-center text-lg ${c.text}`}>{c.icon}</div>
              <div className="mt-4 text-3xl font-semibold flex items-end gap-2">
                {it.value}
                <span className={`text-xs px-1.5 py-0.5 rounded ${positive ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>
                  {positive ? "+" : ""}{it.delta}
                </span>
                <span className="text-xs text-gray-500 ml-0.5">{c.unit}</span>
              </div>
              <div className="mt-1 text-xs text-gray-400">
                {it.key === "ai_employees_total" && "AI 员工总数"}
                {it.key === "ai_employees_working" && "正在工作"}
                {it.key === "tasks_pending" && "待确认任务"}
                {it.key === "tasks_completed" && "已完成任务"}
              </div>
              <div className="mt-1 text-[11px] text-gray-500">{it.label}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
