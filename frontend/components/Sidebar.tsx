"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "./AuthProvider";
import { authHeaders, fetchApprovals } from "../lib/api";

/** 主导航：按权限点渲染，无权限的菜单直接不出现（TASK-003 页面/菜单权限） */
const NAV = [
  { href: "/",            icon: "🏠", label: "企业总览",   perm: null },
  { href: "/workbench",   icon: "✦",  label: "AI 工作台",  perm: null },
  { href: "/approvals",   icon: "✓",  label: "审批中心",   perm: "approval:view" },
  { href: "/employees",   icon: "👥", label: "AI 员工",    perm: "employee:view" },
  { href: "/scenes",      icon: "🧩", label: "业务场景",   perm: "scene:view" },
  { href: "/objects",     icon: "◈",  label: "对象中心",   perm: "datasource:view" },
  { href: "/knowledge",   icon: "📚", label: "企业知识",   perm: "knowledge:view" },
  { href: "/intelligence", icon: "◇", label: "智能化中心", perm: "datasource:view" },
  { href: "/logic",        icon: "🔀", label: "Logic 编排", perm: "tool:config" },
  { href: "/pages",        icon: "🧱", label: "低代码构建", perm: "tool:config" },
  { href: "/assets/center", icon: "📦", label: "平台资产",   perm: "tool:config" },
  { href: "/releases",    icon: "🚀", label: "交付发布",   perm: "tool:config" },
  { href: "/edge-sites",  icon: "🖧", label: "边缘站点",   perm: "tool:config" },
];

const QUICK = [
  { icon: "🗂",  label: "数据管理", href: "/admin/data",        perm: "datasource:config" },
  { icon: "💠",  label: "数据资产", href: "/assets",            perm: "datasource:view" },
  { icon: "🧪",  label: "系统集成", href: "/admin/integration", perm: "datasource:config" },
  { icon: "🔐",  label: "权限管理", href: "/admin/permission",  perm: "role:manage" },
  { icon: "🧠",  label: "模型管理", href: "/admin/model",       perm: "employee:edit" },
  { icon: "📜",  label: "日志中心", href: "/admin/logs",        perm: "log:view" },
  { icon: "⚙️", label: "设置中心", href: "/admin/settings",    perm: "company:manage" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { hasPerm, user } = useAuth();
  const [pendingCount, setPendingCount] = useState(0);

  // 待审批数量：驱动审批中心入口的红点
  useEffect(() => {
    if (!user?.permissions?.includes("approval:view")) return;
    const load = () =>
      fetchApprovals("Pending")
        .then((r) => setPendingCount(r.total || 0))
        .catch(() => setPendingCount(0));
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [user]);

  // 后端连通性指示
  const [online, setOnline] = useState<boolean | null>(null);
  const [port, setPort] = useState<string>("");

  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch("/api/backend/overview", { cache: "no-store", headers: authHeaders() });
        setOnline(r.ok);
        if (r.ok) setPort(String(window.location.port || "3000"));
      } catch {
        setOnline(false);
      }
    };
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, []);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    if (href.startsWith("/employees")) return pathname.startsWith("/employees");
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <aside className="w-[220px] shrink-0 bg-ink-900/70 backdrop-blur-xl border-r border-white/5 flex flex-col">
      {/* Brand */}
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-blue-500 flex items-center justify-center font-bold text-white shadow-glow">
            F
          </div>
          <div>
            <div className="text-sm font-semibold flex items-center gap-1.5">
              傅瑞科技
              <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/5 text-gray-400">FURUI.TECH</span>
            </div>
            <div className="text-[11px] text-gray-500 flex items-center gap-1">
              企业 AI 操作系统
              <span className="px-1.5 rounded bg-violet-500/20 text-violet-300">v2.0</span>
            </div>
          </div>
        </div>
      </div>

      {/* 主导航 */}
      <div className="px-3 space-y-0.5 flex-1 overflow-auto">
        {NAV.filter(it => !it.perm || hasPerm(it.perm)).map(it => {
          const active = isActive(it.href);
          const cls = active
            ? "bg-gradient-to-r from-violet-500/20 to-blue-500/10 border border-violet-400/30 text-white shadow-glow"
            : "text-gray-400 hover:bg-white/[0.03] hover:text-gray-200 border border-transparent";
          const iconCls = active ? "bg-white/10" : "bg-white/[0.04]";
          const badge = it.href === "/approvals" ? pendingCount : 0;
          return (
            <Link key={it.href} href={it.href}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition ${cls}`}>
              <span className={`w-7 h-7 inline-flex items-center justify-center rounded-md ${iconCls}`}>{it.icon}</span>
              <span className="flex-1 text-left">{it.label}</span>
              {badge > 0 && (
                <span className="min-w-[18px] h-[18px] px-1 rounded-full bg-amber-500/90 text-[10px] text-black font-medium flex items-center justify-center">
                  {badge > 99 ? "99+" : badge}
                </span>
              )}
            </Link>
          );
        })}

        <div className="mt-6 px-3 text-[11px] uppercase tracking-wider text-gray-500">快速入口</div>
        {QUICK.filter(it => !it.perm || hasPerm(it.perm)).map((it) => (
          <Link key={it.href} href={it.href}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-gray-400 hover:text-gray-200 hover:bg-white/[0.03]">
            <span className="w-7 h-7 inline-flex items-center justify-center rounded-md bg-white/[0.04]">{it.icon}</span>
            <span>{it.label}</span>
          </Link>
        ))}
      </div>

      {/* 服务状态 */}
      <div className="mx-3 mb-2 space-y-1.5">
        <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-white/[0.03] border border-white/5">
          <span className="text-[11px] text-gray-500">后端服务</span>
          <span className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${
              online === null ? "bg-gray-500" : online ? "bg-emerald-400 animate-pulse2" : "bg-rose-500"
            }`} />
            <span className={`text-[10px] ${
              online === null ? "text-gray-500" : online ? "text-emerald-300" : "text-rose-300"
            }`}>
              {online === null ? "检测中" : online ? "已连接" : "未连接"}
            </span>
          </span>
        </div>
        <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-white/[0.03] border border-white/5">
          <span className="text-[11px] text-gray-500">前端端口</span>
          <span className="text-[10px] text-gray-400">:{port || "—"}</span>
        </div>
      </div>

      <div className="px-5 py-3 text-[11px] text-gray-600 border-t border-white/5">
        © 2026 · 傅瑞科技 · Furui Technology
      </div>
    </aside>
  );
}