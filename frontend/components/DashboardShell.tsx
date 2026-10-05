"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { useAuth } from "./AuthProvider";

/**
 * 全站统一外壳：登录守卫 + 左侧导航 + 顶部栏 + 中间内容区。
 *
 * 用法：
 *   <DashboardShell>{...你的页面...}</DashboardShell>
 */
export default function DashboardShell({
  children,
  footer,
}: {
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  // 未登录时先不渲染业务内容，避免数据闪现
  if (loading || !user) {
    return (
      <div className="flex h-screen w-screen bg-ink-950 bg-grid items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-blue-500 animate-pulse2" />
          <div className="text-xs text-gray-500">正在校验登录状态…</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen bg-ink-950 bg-grid text-gray-200 overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <Topbar />
        <main className="flex-1 overflow-auto px-6 py-5 space-y-5">
          {children}
        </main>
        {footer}
      </div>
    </div>
  );
}
