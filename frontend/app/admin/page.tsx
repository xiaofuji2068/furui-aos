"use client";

import Link from "next/link";
import DashboardShell from "../../components/DashboardShell";

const MODULES = [
  { slug: "data",        icon: "🗂",  title: "数据资产",   desc: "数据源接入、连接状态与字段目录" },
  { slug: "integration", icon: "🔌",  title: "集成对接",   desc: "外部系统 connector 与凭据管理" },
  { slug: "permission",  icon: "🔐",  title: "权限与角色", desc: "角色、权限点与成员授权" },
  { slug: "model",       icon: "🧠",  title: "模型管理",   desc: "对话模型 Key、激活切换与语义检索配置" },
  { slug: "logs",        icon: "📜",  title: "审计日志",   desc: "操作留痕与按条件查询" },
  { slug: "settings",    icon: "⚙️",  title: "系统设置",   desc: "系统参数与租户级配置（已落库）" },
];

export default function AdminIndexPage() {
  return (
    <DashboardShell>
      <div className="mb-5">
        <h1 className="text-2xl font-semibold">管理后台</h1>
        <p className="text-sm text-gray-400 mt-1">选择需要管理的模块</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {MODULES.map(m => (
          <Link
            key={m.slug}
            href={`/admin/${m.slug}`}
            className="glass-strong rounded-2xl border border-white/5 p-5 hover:border-violet-400/30 transition block"
          >
            <div className="text-xl mb-2">{m.icon}</div>
            <div className="text-sm font-semibold text-gray-200">{m.title}</div>
            <div className="text-xs text-gray-500 mt-1">{m.desc}</div>
          </Link>
        ))}
      </div>
    </DashboardShell>
  );
}
