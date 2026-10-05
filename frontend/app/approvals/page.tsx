"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import DashboardShell from "../../components/DashboardShell";
import { useAuth } from "../../components/AuthProvider";
import {
  approveApproval,
  fetchApprovalDetail,
  fetchApprovals,
  fetchSalesTasks,
  rejectApproval,
  type ApprovalItem,
} from "../../lib/api";

type Detail = ApprovalItem & {
  data_evidence: Record<string, any>;
  plan: any[];
  payload: Record<string, any>;
  decision_lineage: Record<string, any>;
  receipts: Array<{
    id: number;
    tool_name: string;
    params_hash: string;
    result_hash: string;
    actor_type: string;
    actor_id: number | null;
    created_at: string;
  }>;
};

const LEVEL_TEXT: Record<number, string> = {
  1: "Level 1 · 自动执行",
  2: "Level 2 · 通知后执行",
  3: "Level 3 · 必须审批",
  4: "Level 4 · 禁止执行",
};

const LEVEL_STYLE: Record<number, string> = {
  1: "bg-emerald-500/15 text-emerald-300",
  2: "bg-cyan-500/15 text-cyan-300",
  3: "bg-amber-500/15 text-amber-300",
  4: "bg-red-500/15 text-red-300",
};

const STATUS_STYLE: Record<string, string> = {
  Pending: "bg-amber-500/15 text-amber-300",
  Executed: "bg-emerald-500/15 text-emerald-300",
  Rejected: "bg-red-500/15 text-red-300",
};

const OBJ_ICON: Record<string, string> = {
  Customer: "🏢", Order: "🧾", Device: "🖥", Product: "📦", WorkOrder: "🔧", Ticket: "⚠️",
};

const TABS = [
  { key: "Pending", label: "待我审批" },
  { key: "Executed", label: "已执行" },
  { key: "Rejected", label: "已拒绝" },
  { key: "all", label: "全部" },
];

export default function ApprovalsPage() {
  const { user } = useAuth();
  const canApprove = !!user?.permissions?.includes("approval:approve");

  const [tab, setTab] = useState("Pending");
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [current, setCurrent] = useState<Detail | null>(null);
  const [salesTasks, setSalesTasks] = useState<any[]>([]);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");

  const load = useCallback(() => {
    fetchApprovals(tab)
      .then((r) => setItems(r.items || []))
      .catch(() => setItems([]));
    fetchSalesTasks(10)
      .then((r) => setSalesTasks(r.items || []))
      .catch(() => setSalesTasks([]));
  }, [tab]);

  useEffect(() => {
    load();
    setCurrent(null);
  }, [load]);

  async function open(id: number) {
    setToast("");
    setComment("");
    try {
      const d = await fetchApprovalDetail(id);
      setCurrent(d);
    } catch (e: any) {
      setToast(e?.message || "加载失败");
    }
  }

  async function decide(action: "approve" | "reject") {
    if (!current) return;
    setBusy(true);
    try {
      const r =
        action === "approve"
          ? await approveApproval(current.id, comment)
          : await rejectApproval(current.id, comment);
      setToast(
        action === "approve"
          ? r.sales_task
            ? `已批准并执行：${r.sales_task.title}（负责人 ${r.sales_task.owner}，截止 ${r.sales_task.due_date}）`
            : "已批准，动作已执行"
          : "已拒绝，Agent 不会执行该动作",
      );
      await fetchApprovalDetail(current.id).then(setCurrent).catch(() => setCurrent(null));
      load();
    } catch (e: any) {
      setToast(e?.message || "操作失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <DashboardShell>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">审批中心</h1>
          <p className="text-sm text-gray-400 mt-1">
            AI 的每一个写入类动作都会在此停下，等你确认后才执行。
          </p>
        </div>
        {!canApprove && (
          <span className="text-xs px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-400/25 text-amber-300">
            当前账号仅可查看，无审批权限
          </span>
        )}
      </div>

      {toast && (
        <div className="mt-3 px-4 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-400/25 text-sm text-emerald-300">
          {toast}
        </div>
      )}

      <div className="flex items-center gap-2 mt-4">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition ${
              tab === t.key
                ? "bg-violet-500/20 border-violet-400/40 text-white"
                : "bg-white/[0.03] border-white/[0.06] text-gray-400 hover:text-gray-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-12 gap-5 mt-2">
        {/* 列表 */}
        <div className="col-span-5 space-y-2.5">
          {items.length === 0 && (
            <div className="glass-strong rounded-2xl border border-white/5 p-10 text-center text-sm text-gray-500">
              暂无相关审批单
            </div>
          )}

          {items.map((a) => (
            <button
              key={a.id}
              onClick={() => open(a.id)}
              className={`w-full text-left glass-strong rounded-2xl border p-4 transition ${
                current?.id === a.id
                  ? "border-violet-400/40"
                  : "border-white/5 hover:border-white/15"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${LEVEL_STYLE[a.level] || ""}`}>
                  {LEVEL_TEXT[a.level] || `Level ${a.level}`}
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${STATUS_STYLE[a.status] || "bg-white/[0.06] text-gray-400"}`}>
                  {a.status}
                </span>
              </div>
              <div className="text-sm font-medium text-white mb-1.5">{a.title}</div>
              <p className="text-[12.5px] text-gray-400 leading-relaxed line-clamp-2">
                {a.ai_reason}
              </p>
              <div className="flex items-center gap-3 mt-2.5 text-[11px] text-gray-500">
                <span>{a.agent}</span>
                <span>{a.created_at?.slice(0, 16).replace("T", " ")}</span>
              </div>
            </button>
          ))}

          {/* 已生效任务 */}
          {salesTasks.length > 0 && (
            <div className="glass-strong rounded-2xl border border-white/5 p-4">
              <h3 className="text-sm font-medium mb-3">Agent 已创建的跟进任务</h3>
              <div className="space-y-1.5">
                {salesTasks.map((t) => (
                  <div
                    key={t.id}
                    className="px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.05]"
                  >
                    <div className="text-[13px] text-gray-200">{t.title}</div>
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-gray-500">
                      <span>{t.customer_name}</span>
                      <span>·</span>
                      <span>负责人 {t.owner}</span>
                      <span>·</span>
                      <span>截止 {t.due_date}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 详情 */}
        <div className="col-span-7">
          {!current ? (
            <div className="glass-strong rounded-2xl border border-white/5 p-12 text-center text-sm text-gray-500">
              选择左侧审批单，查看 AI 的判断理由与数据依据
            </div>
          ) : (
            <div className="glass-strong rounded-2xl border border-white/5 p-5 space-y-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${LEVEL_STYLE[current.level] || ""}`}>
                    {LEVEL_TEXT[current.level] || `Level ${current.level}`}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${STATUS_STYLE[current.status] || "bg-white/[0.06] text-gray-400"}`}>
                    {current.status}
                  </span>
                </div>
                <h2 className="text-lg font-semibold">{current.title}</h2>
                <div className="flex items-center gap-3 mt-1.5 text-[11px] text-gray-500">
                  <span>发起 Agent：{current.agent}</span>
                  <span>动作：{current.action}</span>
                  <span>{current.created_at?.slice(0, 16).replace("T", " ")}</span>
                </div>
              </div>

              <Section title="AI 判断理由">
                <p className="text-[13px] text-gray-300 leading-relaxed">{current.ai_reason}</p>
              </Section>

              <Section title="数据依据">
                {Object.keys(current.data_evidence || {}).length === 0 ? (
                  <Empty />
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(current.data_evidence).map(([k, v]) => (
                      <div
                        key={k}
                        className="rounded-lg bg-white/[0.03] border border-white/[0.05] px-3 py-2"
                      >
                        <div className="text-[10px] text-gray-500">{k}</div>
                        <div className="text-[13px] text-gray-100 mt-0.5 break-all">
                          {typeof v === "object" ? JSON.stringify(v) : String(v)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Section>

              <Section title="执行计划">
                {!current.plan || current.plan.length === 0 ? (
                  <Empty />
                ) : (
                  <ol className="space-y-1.5">
                    {(Array.isArray(current.plan) ? current.plan : []).map((p: any, i: number) => (
                      <li key={i} className="flex items-start gap-2 text-[13px] text-gray-300">
                        <span className="text-violet-400 mt-0.5">{i + 1}.</span>
                        <span className="leading-relaxed">
                          {typeof p === "string" ? p : p.title || JSON.stringify(p)}
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
              </Section>

              {current.payload?.object_id && (
                <Section title="来源对象">
                  <div className="flex items-center gap-3">
                    <span className="w-9 h-9 rounded-xl flex items-center justify-center text-base bg-violet-500/15 border border-violet-400/25">
                      {OBJ_ICON[current.payload?.object_type] || "◈"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-gray-100 font-medium truncate">{current.payload?.object_name || current.payload?.object_id}</div>
                      <div className="text-[11px] text-gray-500">{current.payload?.object_type} · {current.payload?.object_id}</div>
                    </div>
                    <Link
                      href={`/objects?type=${encodeURIComponent(current.payload?.object_type || "")}&id=${encodeURIComponent(current.payload?.object_id || "")}`}
                      className="text-xs px-3 py-1.5 rounded-lg border border-white/10 text-gray-300 hover:text-white hover:bg-white/5 transition shrink-0"
                    >
                      查看对象 →
                    </Link>
                  </div>
                </Section>
              )}

              <Section title="待执行参数">
                {Object.keys(current.payload || {}).length === 0 ? (
                  <Empty />
                ) : (
                  <div className="rounded-lg bg-black/30 border border-white/[0.06] px-3 py-2.5 overflow-x-auto">
                    <pre className="text-[12px] text-gray-300 leading-relaxed">
                      {JSON.stringify(current.payload, null, 2)}
                    </pre>
                  </div>
                )}
              </Section>

              {current.status === "Pending" ? (
                <div className="pt-1 border-t border-white/[0.06]">
                  <label className="text-xs text-gray-400 block mb-1.5">审批意见（可选）</label>
                  <input
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="例如：同意，按二级响应执行"
                    className="w-full px-3 py-2 rounded-xl glass border border-white/[0.08] bg-transparent outline-none text-sm placeholder:text-gray-600 mb-3"
                  />
                  <div className="flex items-center gap-2">
                    <button
                      disabled={!canApprove || busy}
                      onClick={() => decide("approve")}
                      className="text-xs px-4 py-2 rounded-lg bg-gradient-to-r from-violet-500 to-blue-500 text-white disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      批准并执行
                    </button>
                    <button
                      disabled={!canApprove || busy}
                      onClick={() => decide("reject")}
                      className="text-xs px-4 py-2 rounded-lg bg-white/[0.05] hover:bg-white/[0.09] border border-white/10 text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      拒绝
                    </button>
                    {!canApprove && (
                      <span className="text-[11px] text-amber-300/80">
                        当前账号无 approval:approve 权限
                      </span>
                    )}
                  </div>
                </div>
              ) : (
                <div className="pt-3 border-t border-white/[0.06] text-[13px] text-gray-400">
                  审批结果：
                  <span className={current.status === "Executed" ? "text-emerald-300" : "text-red-300"}>
                    {current.status === "Executed" ? " 已批准并执行" : " 已拒绝"}
                  </span>
                  {current.decided_by && <span> · 处理人 {current.decided_by}</span>}
                  {current.decided_at && (
                    <span> · {current.decided_at.slice(0, 16).replace("T", " ")}</span>
                  )}
                  {current.comment && (
                    <div className="mt-1.5 text-gray-300">意见：{current.comment}</div>
                  )}

                  {/* 决策溯源（EvalContract lineage）：输入/输出哈希可复算核验 */}
                  {current.decision_lineage &&
                    Object.keys(current.decision_lineage).length > 0 && (
                      <div className="mt-3 rounded-xl bg-white/[0.02] border border-white/[0.06] p-3 space-y-1.5">
                        <div className="text-[11px] font-medium text-gray-400">
                          决策溯源（lineage · 哈希可复算核验）
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
                          <div className="flex justify-between gap-2">
                            <span className="text-gray-500 shrink-0">决策</span>
                            <span className="text-gray-200 truncate font-mono">
                              {current.decision_lineage.decision || "-"}
                            </span>
                          </div>
                          <div className="flex justify-between gap-2">
                            <span className="text-gray-500 shrink-0">决策人</span>
                            <span className="text-gray-200 truncate">
                              {current.decision_lineage.decided_by || "-"}
                            </span>
                          </div>
                          <div className="flex justify-between gap-2 col-span-1 sm:col-span-2">
                            <span className="text-gray-500 shrink-0">输入哈希</span>
                            <span className="text-gray-200 truncate font-mono">
                              {current.decision_lineage.input_hash
                                ? String(current.decision_lineage.input_hash).slice(0, 24) + "…"
                                : "-"}
                            </span>
                          </div>
                          <div className="flex justify-between gap-2 col-span-1 sm:col-span-2">
                            <span className="text-gray-500 shrink-0">输出哈希</span>
                            <span className="text-gray-200 truncate font-mono">
                              {current.decision_lineage.output_hash
                                ? String(current.decision_lineage.output_hash).slice(0, 24) + "…"
                                : "（拒绝，无输出）"}
                            </span>
                          </div>
                          {current.decision_lineage.receipt_id && (
                            <div className="flex justify-between gap-2 col-span-1 sm:col-span-2">
                              <span className="text-gray-500 shrink-0">动作凭证</span>
                              <span className="text-gray-200 truncate font-mono">
                                receipt#{current.decision_lineage.receipt_id}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                  {/* 动作凭证（Receipt）：执行留痕哈希 */}
                  {current.receipts && current.receipts.length > 0 && (
                    <div className="mt-2 rounded-xl bg-white/[0.02] border border-white/[0.06] p-3 space-y-1">
                      <div className="text-[11px] font-medium text-gray-400">
                        动作凭证（Receipt · {current.receipts.length} 条）
                      </div>
                      {current.receipts.map((r) => (
                        <div key={r.id} className="flex items-center gap-2 text-[11px] text-gray-500">
                          <span className="text-gray-300">#{r.id}</span>
                          <span>{r.tool_name}</span>
                          <span className="truncate font-mono">{r.params_hash}</span>
                          <span className="text-gray-600">→</span>
                          <span className="truncate font-mono">{r.result_hash}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </DashboardShell>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium text-gray-400 mb-2">{title}</div>
      {children}
    </div>
  );
}

function Empty() {
  return <div className="text-[12.5px] text-gray-600">无</div>;
}
