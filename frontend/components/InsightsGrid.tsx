"use client";

const TYPE_STYLE: Record<string, { border: string; text: string; bar: string; icon: string }> = {
  danger:  { border: "border-rose-500/40",    text: "text-rose-300",    bar: "bg-rose-400",    icon: "⚠" },
  warning: { border: "border-amber-500/40",   text: "text-amber-300",   bar: "bg-amber-400",   icon: "◆" },
  success: { border: "border-emerald-500/40", text: "text-emerald-300", bar: "bg-emerald-400", icon: "✓" },
  primary: { border: "border-blue-500/40",    text: "text-blue-300",    bar: "bg-blue-400",    icon: "✦" },
};

export default function InsightsGrid({ items }: { items: any[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {items.map((it, idx) => {
        const s = TYPE_STYLE[it.type] || TYPE_STYLE.primary;
        return (
          <div key={it.id} className={`relative overflow-hidden glass-strong rounded-2xl p-5 border ${s.border} hover:scale-[1.02] transition`}>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <div className={`w-8 h-8 rounded-lg bg-white/[0.06] flex items-center justify-center ${s.text}`}>{s.icon}</div>
                <div className={`text-sm font-medium ${s.text}`}>{it.title}</div>
              </div>
              <span className={`w-2 h-2 rounded-full ${s.bar} animate-pulse2`} />
            </div>
            <div className="mt-3 text-base font-medium leading-snug">{it.summary}</div>
            <div className="mt-1.5 text-xs text-gray-400">{it.detail}</div>
            <button className={`mt-4 inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/5`}>
              {it.action} <span className="opacity-60">→</span>
            </button>
            <div className={`absolute left-0 top-0 h-full w-[3px] ${s.bar} opacity-70`} />
          </div>
        );
      })}
    </div>
  );
}
