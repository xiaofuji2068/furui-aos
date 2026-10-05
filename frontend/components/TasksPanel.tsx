"use client";

const LEVEL_TAG: Record<number, { text: string; cls: string }> = {
  1: { text: "自动", cls: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" },
  2: { text: "通知", cls: "bg-sky-500/20 text-sky-300 border-sky-500/40" },
  3: { text: "需审批", cls: "bg-amber-500/20 text-amber-300 border-amber-500/40" },
  4: { text: "禁止", cls: "bg-rose-500/20 text-rose-300 border-rose-500/40" },
};

export default function TasksPanel({ items, onConfirm, onReject }: {
  items: any[];
  onConfirm: (id: number | string) => void;
  onReject?: (id: number | string) => void;
}) {
  return (
    <div className="p-5 border-b border-white/5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium">
          待我确认的任务 <span className="text-gray-500">({items.length})</span>
        </h3>
        <button className="text-xs text-gray-500 hover:text-gray-300">查看全部 →</button>
      </div>

      <div className="space-y-3">
        {items.length === 0 && (
          <div className="text-xs text-gray-500 italic px-3 py-6 text-center rounded-xl bg-white/[0.02]">暂无待确认任务</div>
        )}
        {items.map((t, i) => (
          <div key={t.id}
            className={`relative rounded-xl p-3.5 border border-white/5 glass-strong ${i === 0 ? "ring-1 ring-rose-500/40" : ""}`}>
            {i === 0 && (
              <span className="absolute -top-2 left-3 text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">
                高优
              </span>
            )}
            {i === 1 && (
              <span className="absolute -top-2 left-3 text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                中优
              </span>
            )}
            {t.level != null && LEVEL_TAG[t.level] && (
              <span className={`absolute -top-2 right-3 text-[10px] px-1.5 py-0.5 rounded border ${LEVEL_TAG[t.level].cls}`}>
                {LEVEL_TAG[t.level].text}
              </span>
            )}
            <div className="text-sm font-medium mt-1">{t.title}</div>
            <div className="text-[11px] text-gray-400 mt-1 leading-snug">{t.description}</div>
            <div className="text-[10px] text-gray-500 mt-1.5">{t.created_at}</div>
            <div className="flex items-center gap-2 mt-3">
              <button
                onClick={() => onConfirm(t.id)}
                className="text-xs px-3 py-1.5 rounded-lg bg-gradient-to-r from-violet-500 to-blue-500 text-white shadow-glow hover:opacity-90">
                确认
              </button>
              <button
                onClick={() => onReject?.(t.id)}
                className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/5">
                拒绝
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
