"use client";

import { useEffect, useState, useCallback } from "react";

/**
 * 系统健康检查（图谱 90-01 可观测）。
 * 从 /api/health 读取 数据库 / 对话模型 / 语义检索 / 系统 四维状态，
 * 展示为紧凑状态条，可手动刷新；与数据源卡片视觉一致。
 */

const STATUS_META: Record<string, { label: string; dot: string; text: string; cls: string }> = {
  ok:           { label: "正常",     dot: "bg-emerald-400", text: "text-emerald-300", cls: "bg-emerald-500/10 border-emerald-400/20" },
  warning:      { label: "待启用",   dot: "bg-amber-400",    text: "text-amber-300",   cls: "bg-amber-500/10 border-amber-400/20" },
  disconnected: { label: "未连接",   dot: "bg-gray-500",     text: "text-gray-400",    cls: "bg-white/[0.02] border-white/5" },
  error:        { label: "异常",     dot: "bg-rose-400",     text: "text-rose-300",    cls: "bg-rose-500/10 border-rose-400/20" },
};

const ICON: Record<string, string> = {
  数据库: "🗄",
  对话模型: "🧠",
  语义检索: "🔎",
  系统: "🖥",
};

export default function SystemHealth() {
  const [data, setData] = useState<any | null>(null);

  const load = useCallback(() => {
    fetch("/api/backend/health")
      .then((r) => r.json())
      .then((d) => setData(d))
      .catch(() => setData(null));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const checks: any[] = data?.checks || [];
  const failed = checks.filter((c) => c.status === "error").length;

  return (
    <section className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-medium">系统健康</h2>
        <button
          onClick={load}
          className="text-xs text-gray-400 hover:text-gray-200 flex items-center gap-1.5"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 1 1-2.64-6.36" />
            <polyline points="21 3 21 9 15 9" />
          </svg>
          刷新
        </button>
      </div>

      {!data ? (
        <div className="rounded-xl border border-white/5 bg-white/[0.02] px-4 py-5 text-sm text-gray-500">
          健康检查服务未就绪（/api/health 不可用）。
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {checks.map((c, i) => {
              const meta = STATUS_META[c.status] || STATUS_META.disconnected;
              return (
                <div key={i} className={`rounded-xl border px-3.5 py-3 ${meta.cls}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-base">{ICON[c.name] || "•"}</span>
                      <span className="text-sm font-medium text-gray-100">{c.name}</span>
                    </div>
                    <span className={`flex items-center gap-1.5 text-[11px] ${meta.text}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                      {meta.label}
                    </span>
                  </div>
                  <div className="text-[11px] text-gray-400 mt-2 leading-relaxed truncate" title={c.detail}>
                    {c.detail}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="text-[11px] text-gray-500 mt-2">
            {failed > 0
              ? `⚠ ${failed} 项存在异常，请检查后端日志`
              : `系统运行正常 · ${data.ts || ""}`}
          </div>
        </>
      )}
    </section>
  );
}
