"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import DashboardShell from "../../components/DashboardShell";
import { api, fetchMeta, fetchSkills, SystemMeta, SkillInfo } from "../../lib/api";

const STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  working: { text: "工作中", cls: "bg-emerald-500/15 text-emerald-300" },
  idle: { text: "空闲", cls: "bg-gray-500/15 text-gray-300" },
  waiting: { text: "等待确认", cls: "bg-amber-500/15 text-amber-300" },
  error: { text: "异常", cls: "bg-rose-500/15 text-rose-300" },
};

// 注意：Tailwind 只扫描源码里的字面量类名，这里必须写全，不能动态拼接
const AVATAR_BG: Record<string, string> = {
  "销售分析师": "bg-gradient-to-br from-rose-500/40 to-orange-500/30",
  "财务助手": "bg-gradient-to-br from-emerald-500/40 to-teal-500/30",
  "设备运维工程师": "bg-gradient-to-br from-sky-500/40 to-blue-500/30",
  "知识助手": "bg-gradient-to-br from-violet-500/40 to-purple-500/30",
};

function StatCard({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="glass-strong rounded-2xl p-4 border border-white/5">
      <div className="text-[11px] text-gray-500">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${ok === false ? "text-amber-300" : "text-gray-100"}`}>
        {value}
      </div>
    </div>
  );
}

export default function IntelligencePage() {
  const [meta, setMeta] = useState<SystemMeta | null>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.all([
      fetchMeta().catch(() => null),
      api.get<any>("/agents").catch(() => ({ items: [] })),
      fetchSkills().catch(() => ({ items: [] })),
    ]).then(([m, ag, sk]: any[]) => {
      if (!alive) return;
      setMeta(m);
      setAgents(ag?.items || []);
      setSkills(sk?.items || []);
      setLoading(false);
    });
    return () => { alive = false; };
  }, []);

  const isProduct = meta?.llm_enabled;
  const writeSkills = skills.filter((s) => s.write);
  const readSkills = skills.filter((s) => !s.write);

  const stats = meta
    ? [
        { label: "系统版本", value: meta.version, ok: true },
        { label: "LLM 模式", value: meta.llm_mode, ok: meta.llm_enabled },
        { label: "向量检索", value: meta.embedding_enabled ? "已启用" : "未启用", ok: meta.embedding_enabled },
        { label: "本体持久化", value: meta.ontology_mode, ok: true },
        { label: "多 Agent 编排", value: meta.multi_agent ? "已开启" : "关闭", ok: meta.multi_agent },
        { label: "注册 Skill", value: String(meta.skill_count), ok: true },
      ]
    : [];

  return (
    <DashboardShell>
      {/* 标题 + 运行态说明 */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">智能化中心</h1>
          <p className="text-sm text-gray-400 mt-1">
            企业 AI 能力指挥视图 — 模型 / 本体 / Agent / Skills 一站式状态
          </p>
        </div>
      </div>

      {/* 运行态横幅（产品态 / 演示态 显性化） */}
      <div className={`glass-strong rounded-2xl p-5 border ${isProduct ? "border-emerald-400/30" : "border-amber-400/30"}`}>
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <span className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl shrink-0 ${isProduct ? "bg-emerald-500/20" : "bg-amber-500/20"}`}>
              {isProduct ? "🚀" : "🧪"}
            </span>
            <div className="min-w-0">
              <div className="font-semibold">
                当前运行态：{meta ? meta.llm_mode : "检测中…"}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                {isProduct
                  ? "真 LLM 推理已接入，所有回答由大模型实时生成与工具调用。"
                  : "内置 mock 模型驱动，用于产品演示与功能验收，不代表真实大模型推理能力。"}
              </div>
            </div>
          </div>
          <span className={`shrink-0 text-xs px-3 py-1 rounded-full font-medium ${isProduct ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"}`}>
            {isProduct ? "PRODUCT · 产品态" : "DEMO · 演示态"}
          </span>
        </div>
        <p className="text-[11px] text-gray-500 mt-3 leading-relaxed">
          对外说明：本系统以傅瑞科技自研 <span className="text-gray-300">Ontology 语义层 + 多 Agent 编排</span> 为核心，对标 Palantir AIP / Claude Agent 架构；演示态数据均来自内置示例库。
        </p>
      </div>

      {/* 系统状态卡片 */}
      <section>
        <h2 className="text-base font-medium mb-3">系统状态</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="glass-strong rounded-2xl p-4 border border-white/5 h-[68px] animate-pulse2" />
              ))
            : stats.map((s) => <StatCard key={s.label} {...s} />)}
        </div>
      </section>

      {/* Agent 名册 + 编排模式 */}
      <section className="grid grid-cols-12 gap-5">
        <div className="col-span-12 xl:col-span-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-medium">
              AI 员工名册
              <span className="ml-2 text-xs text-gray-500">{agents.length} 个</span>
            </h2>
            <Link href="/employees" className="text-xs text-gray-400 hover:text-gray-200">查看全部 →</Link>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="glass-strong rounded-2xl p-5 border border-white/5 h-[132px] animate-pulse2" />
              ))}
            </div>
          ) : agents.length === 0 ? (
            <div className="glass-strong rounded-2xl p-10 border border-white/5 text-center text-gray-400 text-sm">
              暂无已注册的 AI 员工
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {agents.map((a) => {
                const st = STATUS_LABEL[a.status] || STATUS_LABEL.idle;
                const bg = AVATAR_BG[a.name] || "bg-gradient-to-br from-slate-500/40 to-slate-600/30";
                return (
                  <Link
                    key={a.id}
                    href={`/employees/${encodeURIComponent(a.name)}`}
                    className="block glass-strong rounded-2xl p-5 border border-white/5 hover:border-white/10 transition"
                  >
                    <div className="flex items-start gap-3">
                      <div className={`relative w-12 h-12 rounded-xl ${bg} flex items-center justify-center text-2xl shadow-glow`}>
                        {a.avatar}
                        {a.status === "working" && (
                          <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-400 ring-2 ring-ink-900 animate-pulse2" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <div className="font-medium truncate">{a.name}</div>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full ${st.cls}`}>{st.text}</span>
                        </div>
                        <div className="text-xs text-gray-400 truncate">{a.role}</div>
                      </div>
                    </div>

                    <div className="mt-4">
                      <div className="text-[11px] text-gray-400">当前任务</div>
                      <div className="text-sm mt-0.5 truncate">{a.current_task}</div>
                    </div>

                    <div className="mt-4 flex items-center gap-4 text-[11px] text-gray-400">
                      <span>今日任务 <span className="text-gray-200">{a.today_tasks ?? 0}</span></span>
                      <span>已完成 <span className="text-emerald-300">{a.success_tasks ?? 0}</span></span>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* 编排模式说明 */}
        <div className="col-span-12 xl:col-span-4">
          <h2 className="text-base font-medium mb-3">编排模式</h2>
          <div className="glass-strong rounded-2xl p-5 border border-white/5 space-y-4">
            <p className="text-xs text-gray-400">AI 工作台的聊天框内置切换开关：</p>

            <div className="flex gap-3">
              <span className="w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center text-lg shrink-0">🤖</span>
              <div>
                <div className="text-sm font-medium">单 Agent 编排（Orchestrator）</div>
                <div className="text-xs text-gray-400 mt-0.5">单一专家 + 工具调用 + 人类确认回路（HITL）</div>
              </div>
            </div>

            <div className="flex gap-3">
              <span className="w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center text-lg shrink-0">🩺</span>
              <div>
                <div className="text-sm font-medium">多 Agent 会诊（Coordinator）</div>
                <div className="text-xs text-gray-400 mt-0.5">按领域路由多个专家，流式回传 plan → 各方观点 → 综合结论</div>
              </div>
            </div>

            <Link
              href="/"
              className="block text-center text-xs py-2 rounded-xl bg-gradient-to-r from-violet-500/20 to-blue-500/10 border border-violet-400/30 text-violet-200 hover:text-white transition"
            >
              进入 AI 工作台 →
            </Link>
          </div>

          <h2 className="text-base font-medium mb-3 mt-5">快速入口</h2>
          <div className="grid grid-cols-2 gap-3">
            <Link href="/knowledge" className="glass-strong rounded-2xl p-4 border border-white/5 hover:border-white/10 transition">
              <div className="text-lg">📚</div>
              <div className="text-sm mt-1">企业知识</div>
            </Link>
            <Link href="/scenes" className="glass-strong rounded-2xl p-4 border border-white/5 hover:border-white/10 transition">
              <div className="text-lg">🧩</div>
              <div className="text-sm mt-1">业务场景</div>
            </Link>
            <Link href="/admin/model" className="glass-strong rounded-2xl p-4 border border-white/5 hover:border-white/10 transition">
              <div className="text-lg">🧠</div>
              <div className="text-sm mt-1">模型管理</div>
            </Link>
            <Link href="/admin/data" className="glass-strong rounded-2xl p-4 border border-white/5 hover:border-white/10 transition">
              <div className="text-lg">🗂</div>
              <div className="text-sm mt-1">数据管理</div>
            </Link>
          </div>
        </div>
      </section>

      {/* Skills 注册表 */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-medium">
            Skills 注册表
            <span className="ml-2 text-xs text-gray-500">{skills.length} 个工具</span>
          </h2>
          <div className="flex items-center gap-2 text-[11px]">
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300">只读 {readSkills.length}</span>
            <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300">写入·需确认 {writeSkills.length}</span>
          </div>
        </div>

        <div className="glass-strong rounded-2xl p-5 border border-white/5">
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-5 rounded bg-white/[0.04] animate-pulse2" />
              ))}
            </div>
          ) : skills.length === 0 ? (
            <div className="text-center text-gray-400 text-sm py-6">暂无已注册的 Skill</div>
          ) : (
            <div className="divide-y divide-white/5">
              {skills.map((s) => (
                <div key={s.name} className="flex items-start gap-3 py-3">
                  <code className="text-xs px-2 py-1 rounded-md bg-white/[0.06] text-violet-200 font-mono shrink-0">
                    {s.name}
                  </code>
                  {s.write && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 shrink-0 mt-0.5">
                      写入·需确认
                    </span>
                  )}
                  <div className="flex-1 text-sm text-gray-300">{s.description}</div>
                  <span className="text-[10px] text-gray-500 shrink-0 mt-1">{s.param_count} 参数</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </DashboardShell>
  );
}
