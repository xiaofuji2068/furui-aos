"use client";

const COLOR: Record<string, string> = {
  "销售分析师":     "bg-rose-500/20 text-rose-300",
  "财务助手":       "bg-emerald-500/20 text-emerald-300",
  "设备运维工程师": "bg-sky-500/20 text-sky-300",
  "知识助手":       "bg-violet-500/20 text-violet-300",
  "系统管理员":     "bg-amber-500/20 text-amber-300",
};

export default function ActivitiesPanel({ items }: { items: any[] }) {
  return (
    <div className="p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium">最近活动</h3>
        <button className="text-xs text-gray-500 hover:text-gray-300">查看全部 →</button>
      </div>
      <div className="space-y-2.5">
        {items.map(a => (
          <div key={a.id} className="flex items-start gap-3 px-3 py-2.5 rounded-xl hover:bg-white/[0.03]">
            <div className={`mt-0.5 w-7 h-7 shrink-0 rounded-full flex items-center justify-center text-[10px] font-medium ${COLOR[a.actor] || "bg-gray-500/20 text-gray-300"}`}>
              {(a.actor || "?").slice(0, 1)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs">
                <span className="font-medium">{a.actor}</span>
                <span className="text-gray-400 ml-1">{a.text.replace(a.actor, "").replace(/^ · /, "")}</span>
              </div>
              <div className="text-[10px] text-gray-500 mt-0.5">{a.timestamp}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
