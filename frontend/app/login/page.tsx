"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";

/** 演示账号，便于一键验收「不同用户看到不同数据」 */
const DEMO_ACCOUNTS = [
  { username: "admin",   label: "王欢 · 管理员",     desc: "全部企业 / 全部权限",     tag: "admin" },
  { username: "sales",   label: "李明 · 业务负责人", desc: "傅瑞 · 销售部 · 可审批",  tag: "owner" },
  { username: "analyst", label: "张分析 · 数据分析师", desc: "傅瑞 · 财务部 · 只读",  tag: "analyst" },
  { username: "ops",     label: "赵运维 · 运维工程师", desc: "傅瑞 · 设备运维部",     tag: "ops" },
  { username: "guest",   label: "外部访客",           desc: "演示企业A · 数据完全隔离", tag: "guest" },
];

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login } = useAuth();

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("123456");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 已登录直接进系统
  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user, router]);

  const submit = async (u = username, p = password) => {
    setError("");
    setSubmitting(true);
    try {
      await login(u, p);
      router.replace("/");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-ink-950 bg-grid flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-[980px] grid grid-cols-1 lg:grid-cols-[1.15fr_.85fr] gap-6">

        {/* 左侧：品牌与价值主张 */}
        <div className="glass-strong rounded-3xl p-9 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute -top-24 -right-24 w-72 h-72 rounded-full bg-violet-600/20 blur-3xl" />
          <div className="absolute -bottom-28 -left-20 w-72 h-72 rounded-full bg-blue-600/15 blur-3xl" />

          <div className="relative">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-violet-500 to-blue-500 flex items-center justify-center font-bold text-white text-lg shadow-glow">
                F
              </div>
              <div>
                <div className="text-base font-semibold">傅瑞科技</div>
                <div className="text-[11px] text-gray-500">FURUI TECHNOLOGY</div>
              </div>
            </div>

            <h1 className="mt-9 text-[30px] leading-tight font-semibold">
              企业 AI <span className="text-gradient-blue">Agent 操作系统</span>
            </h1>
            <p className="mt-3 text-sm text-gray-400 leading-relaxed max-w-[420px]">
              以 Palantir Ontology 为骨架、Claude Skills 为能力单元，
              让 AI 员工<b className="text-gray-200">在权限边界内</b>调用企业知识与数据，
              执行任务并接受人工确认。
            </p>

            <div className="mt-8 grid grid-cols-2 gap-3 max-w-[440px]">
              {[
                ["🧠", "Agent 理解任务", "意图识别 · 计划分解"],
                ["📚", "调用企业知识", "RAG · 权限过滤"],
                ["🗄", "调用业务数据", "只读网关 · 敏感脱敏"],
                ["✅", "人工确认闭环", "分级审批 · 全链审计"],
              ].map(([icon, title, desc]) => (
                <div key={title}
                  className="rounded-2xl bg-white/[0.03] border border-white/5 px-3.5 py-3">
                  <div className="text-lg">{icon}</div>
                  <div className="mt-1.5 text-[13px] text-gray-200">{title}</div>
                  <div className="text-[11px] text-gray-500 mt-0.5">{desc}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative mt-8 text-[11px] text-gray-600">
            © 2026 · 傅瑞科技 · Furui AIOS v2.0
          </div>
        </div>

        {/* 右侧：登录表单 */}
        <div className="glass rounded-3xl p-8 flex flex-col justify-center">
          <div className="text-lg font-semibold">登录工作台</div>
          <div className="text-[12px] text-gray-500 mt-1">使用企业账号登录，数据按企业严格隔离</div>

          <form
            className="mt-7 space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <div>
              <label className="block text-[12px] text-gray-400 mb-1.5">账号</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                placeholder="请输入用户名"
                className="w-full px-4 py-3 rounded-xl bg-white/[0.04] border border-white/8 text-sm outline-none focus:border-violet-400/50 focus:bg-white/[0.06] transition placeholder:text-gray-600"
              />
            </div>

            <div>
              <label className="block text-[12px] text-gray-400 mb-1.5">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="请输入密码"
                className="w-full px-4 py-3 rounded-xl bg-white/[0.04] border border-white/8 text-sm outline-none focus:border-violet-400/50 focus:bg-white/[0.06] transition placeholder:text-gray-600"
              />
            </div>

            {error && (
              <div className="px-3.5 py-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-[12px] text-rose-300">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50 transition shadow-glow"
            >
              {submitting ? "登录中…" : "登 录"}
            </button>
          </form>

          <div className="mt-7">
            <div className="text-[11px] uppercase tracking-wider text-gray-500 mb-2.5">
              演示账号 · 一键体验权限差异
            </div>
            <div className="space-y-1.5">
              {DEMO_ACCOUNTS.map((a) => (
                <button
                  key={a.username}
                  onClick={() => {
                    setUsername(a.username);
                    submit(a.username, "123456");
                  }}
                  disabled={submitting}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.06] hover:border-white/10 transition text-left disabled:opacity-50"
                >
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-300 shrink-0">
                    {a.tag}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-[12.5px] text-gray-200 truncate">{a.label}</span>
                    <span className="block text-[11px] text-gray-500 truncate">{a.desc}</span>
                  </span>
                  <span className="text-gray-600 text-sm">→</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
