"use client";

import { useState } from "react";
import { useAuth } from "./AuthProvider";

export default function Topbar() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  const displayName = user?.name || user?.username || "未登录";
  const roleLabel = user?.roles?.map((r) => r.name).join(" / ") || "—";
  const avatarChar = displayName.slice(0, 1);

  return (
    <header className="h-14 px-6 flex items-center justify-between border-b border-white/5 bg-ink-900/60 backdrop-blur">
      <div className="flex-1 max-w-[520px]">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.04] border border-white/5">
          <span className="text-gray-500">🔍</span>
          <input
            placeholder="搜索 AI 员工、订单、客户、文档…"
            className="flex-1 bg-transparent outline-none text-sm placeholder:text-gray-500"
          />
          <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-gray-400 border border-white/10">
            ⌘ + K
          </kbd>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button className="relative w-9 h-9 rounded-xl bg-white/[0.04] flex items-center justify-center hover:bg-white/[0.08]">
          🔔
          <span className="absolute -top-1 -right-1 w-4 h-4 text-[10px] rounded-full bg-rose-500 flex items-center justify-center">19</span>
        </button>
        <button className="w-9 h-9 rounded-xl bg-white/[0.04] flex items-center justify-center hover:bg-white/[0.08]">❓</button>

        {/* 当前用户 + 退出登录 */}
        <div className="relative flex items-center gap-2 pl-2 ml-1 border-l border-white/10">
          <button
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-2 hover:opacity-90 transition"
          >
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-pink-500 flex items-center justify-center text-xs font-bold">
              {avatarChar}
            </div>
            <div className="text-right leading-tight">
              <div className="text-xs">{displayName}</div>
              <div className="text-[10px] text-gray-500">{roleLabel}</div>
            </div>
          </button>

          {open && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
              <div className="absolute right-0 top-11 z-20 w-64 rounded-2xl glass-strong shadow-2xl p-3">
                <div className="px-2 py-2 border-b border-white/5">
                  <div className="text-sm text-gray-100">{displayName}</div>
                  <div className="text-[11px] text-gray-500 mt-0.5">@{user?.username}</div>
                  <div className="mt-2 space-y-1">
                    <div className="text-[11px] text-gray-500">
                      企业：<span className="text-gray-300">{user?.company?.name || "—"}</span>
                    </div>
                    <div className="text-[11px] text-gray-500">
                      部门：<span className="text-gray-300">{user?.department?.name || "—"}</span>
                    </div>
                    <div className="text-[11px] text-gray-500">
                      权限点：<span className="text-violet-300">{user?.permissions?.length ?? 0}</span> 项
                    </div>
                  </div>
                </div>
                <button
                  onClick={async () => {
                    setOpen(false);
                    await logout();
                    window.location.href = "/login";
                  }}
                  className="mt-2 w-full px-3 py-2 rounded-xl text-left text-[12.5px] text-rose-300 hover:bg-rose-500/10 transition"
                >
                  退出登录
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
