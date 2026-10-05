"use client";

import Link from "next/link";

export default function CreateAgentCTA() {
  return (
    <div className="p-5">
      <div className="relative rounded-2xl p-5 overflow-hidden glass-strong border border-violet-400/30">
        <div className="absolute -top-8 -right-8 w-32 h-32 rounded-full bg-violet-500/30 blur-3xl" />
        <div className="absolute -bottom-12 -left-12 w-32 h-32 rounded-full bg-blue-500/30 blur-3xl" />

        <div className="relative">
          <h3 className="text-sm font-medium">创建新的 AI 员工</h3>
          <p className="text-[11px] text-gray-400 mt-1">根据您的业务需求，创建专属的 AI 员工。</p>

          <div className="flex -space-x-2 mt-4">
            <div className="w-8 h-8 rounded-full bg-rose-500/70 ring-2 ring-ink-900 flex items-center justify-center text-[10px]">SA</div>
            <div className="w-8 h-8 rounded-full bg-sky-500/70 ring-2 ring-ink-900 flex items-center justify-center text-[10px]">FA</div>
            <div className="w-8 h-8 rounded-full bg-emerald-500/70 ring-2 ring-ink-900 flex items-center justify-center text-[10px]">OE</div>
            <div className="w-8 h-8 rounded-full bg-violet-500/70 ring-2 ring-ink-900 flex items-center justify-center text-[10px]">KA</div>
            <div className="w-8 h-8 rounded-full bg-white/10 ring-2 ring-ink-900 flex items-center justify-center text-xs">+</div>
          </div>

          <Link
            href="/employees/new"
            className="mt-4 block text-center text-xs px-3 py-2 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white shadow-glow hover:opacity-90"
          >
            立即创建
          </Link>
        </div>
      </div>
    </div>
  );
}
