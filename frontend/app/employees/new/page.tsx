"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import DashboardShell from "../../../components/DashboardShell";

const API = "/api/backend";

const AVATARS = ["🤖", "👨‍💼", "👩‍💼", "👷", "🧑‍🏫", "📊", "🔧", "💡", "🛡️", "⚙️"];
const COLORS = [
  "from-rose-500 to-orange-500",
  "from-emerald-500 to-teal-500",
  "from-sky-500 to-blue-500",
  "from-violet-500 to-purple-500",
  "from-amber-500 to-yellow-500",
  "from-cyan-500 to-sky-500",
];
const CAPABILITY_OPTIONS = [
  "销售趋势分析", "区域对比分析", "客户分层", "异常归因", "增长机会挖掘",
  "现金流分析", "损益回顾", "预算差异说明", "设备故障诊断", "参数自动调整",
  "维护计划制定", "工单自动派发", "知识语义检索", "文档归纳总结", "SOP 生成",
  "周报自动生成", "回款提醒", "成本结构拆解",
];
const PERMISSION_OPTIONS = [
  "基础查询", "订单查询", "客户数据", "报表生成", "通知推送",
  "设备监控", "工单创建", "参数调整", "财务数据", "知识读取", "知识写入",
];

const STEPS = ["基础信息", "能力配置", "权限设置"];

export default function CreateEmployeePage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [avatar, setAvatar] = useState(AVATARS[0]);
  const [color, setColor] = useState(COLORS[3]);
  const [caps, setCaps] = useState<string[]>([]);
  const [perms, setPerms] = useState<string[]>(["基础查询"]);

  const toggle = (arr: string[], v: string, setter: (x: string[]) => void) =>
    setter(arr.includes(v) ? arr.filter(x => x !== v) : [...arr, v]);

  async function submit() {
    if (!name.trim()) return setErr("请填写员工名称");
    setBusy(true);
    setErr("");
    try {
      const r = await fetch(`${API}/employees`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          role: role.trim() || "自定义 AI 员工",
          avatar, color, skills: [], capabilities: caps,
          permissions: perms.map(p => ({ name: p, granted: true })),
        }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || "创建失败");
      }
      router.push(`/employees/${encodeURIComponent(name.trim())}`);
    } catch (e: any) {
      setErr(e.message || "创建失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <DashboardShell>
      <div className="max-w-3xl mx-auto">
        <Link href="/employees" className="text-xs text-gray-400 hover:text-gray-200">← 返回员工列表</Link>
        <h1 className="text-2xl font-semibold mt-3">创建 AI 员工</h1>

        {/* 步骤指示 */}
        <div className="flex items-center gap-2 my-6">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2 flex-1">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium ${
                i <= step ? "bg-violet-500 text-white" : "bg-white/[0.06] text-gray-400"
              }`}>{i + 1}</div>
              <span className={`text-xs ${i === step ? "text-gray-100" : "text-gray-500"}`}>{s}</span>
              {i < STEPS.length - 1 && <div className={`flex-1 h-px ${i < step ? "bg-violet-500/50" : "bg-white/10"}`} />}
            </div>
          ))}
        </div>

        <div className="glass-strong rounded-2xl p-6 border border-white/5">
          {step === 0 && (
            <div className="space-y-5">
              <Field label="员工名称 *">
                <input value={name} onChange={e => setName(e.target.value)} placeholder="如：供应链分析师"
                  className="w-full rounded-xl bg-black/30 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-violet-400/40" />
              </Field>
              <Field label="角色描述">
                <input value={role} onChange={e => setRole(e.target.value)} placeholder="如：分析供应链风险并给出调度建议"
                  className="w-full rounded-xl bg-black/30 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-violet-400/40" />
              </Field>
              <Field label="头像">
                <div className="flex flex-wrap gap-2">
                  {AVATARS.map(a => (
                    <button key={a} onClick={() => setAvatar(a)}
                      className={`w-11 h-11 rounded-xl text-xl flex items-center justify-center border ${
                        avatar === a ? "border-violet-400/50 bg-violet-500/15" : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                      }`}>{a}</button>
                  ))}
                </div>
              </Field>
              <Field label="主题色">
                <div className="flex flex-wrap gap-2">
                  {COLORS.map(c => (
                    <button key={c} onClick={() => setColor(c)}
                      className={`w-11 h-11 rounded-xl bg-gradient-to-br ${c} border ${
                        color === c ? "border-white/70 ring-2 ring-violet-400/40" : "border-white/10"
                      }`} />
                  ))}
                </div>
              </Field>
            </div>
          )}

          {step === 1 && (
            <div>
              <p className="text-sm text-gray-400 mb-4">选择该员工具备的能力（可多选）。</p>
              <div className="flex flex-wrap gap-2">
                {CAPABILITY_OPTIONS.map(c => (
                  <button key={c} onClick={() => toggle(caps, c, setCaps)}
                    className={`px-3 py-1.5 rounded-lg text-xs border transition ${
                      caps.includes(c)
                        ? "bg-violet-500/20 text-violet-200 border-violet-400/40"
                        : "bg-white/[0.03] text-gray-300 border-white/10 hover:bg-white/[0.06]"
                    }`}>{c}</button>
                ))}
              </div>
              {caps.length > 0 && (
                <p className="text-xs text-gray-500 mt-4">已选 {caps.length} 项能力</p>
              )}
            </div>
          )}

          {step === 2 && (
            <div>
              <p className="text-sm text-gray-400 mb-4">为该员工授予的权限（默认全部开启，创建后可调整）。</p>
              <div className="flex flex-wrap gap-2">
                {PERMISSION_OPTIONS.map(p => (
                  <button key={p} onClick={() => toggle(perms, p, setPerms)}
                    className={`px-3 py-1.5 rounded-lg text-xs border transition ${
                      perms.includes(p)
                        ? "bg-emerald-500/15 text-emerald-300 border-emerald-400/40"
                        : "bg-white/[0.03] text-gray-400 border-white/10 hover:bg-white/[0.06]"
                    }`}>{p}</button>
                ))}
              </div>
            </div>
          )}

          {err && <div className="text-xs text-rose-300 mt-4">{err}</div>}

          <div className="flex items-center justify-between mt-7">
            <button onClick={() => step === 0 ? router.push("/employees") : setStep(step - 1)}
              className="text-sm px-4 py-2.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/5">
              {step === 0 ? "取消" : "上一步"}
            </button>
            {step < STEPS.length - 1 ? (
              <button onClick={() => setStep(step + 1)}
                className="text-sm px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white shadow-glow hover:opacity-90">
                下一步
              </button>
            ) : (
              <button onClick={submit} disabled={busy}
                className="text-sm px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white shadow-glow hover:opacity-90 disabled:opacity-50">
                {busy ? "创建中…" : "确认创建"}
              </button>
            )}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-xs text-gray-400 mb-1.5 block">{label}</label>
      {children}
    </div>
  );
}
