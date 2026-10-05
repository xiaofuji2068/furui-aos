"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import DashboardShell from "../../components/DashboardShell";
import Markdown from "../../components/Markdown";
import { useAuth } from "../../components/AuthProvider";
import {
  fetchTaskDetail,
  fetchTasks,
  approveApproval,
  rejectApproval,
  streamSSE,
  type TaskBrief,
} from "../../lib/api";

interface Step {
  seq: number;
  title: string;
  status: "Pending" | "Running" | "Completed" | "Skipped" | "Failed";
}

interface Stage {
  seq: number;
  name: string;
  kind: string;
  status: string;
  steps: number[];
  checkpoint?: Record<string, any>;
  started_at?: string;
  finished_at?: string;
}

const STAGE_PLAN: { seq: number; name: string; kind: string; steps: number[] }[] = [
  { seq: 1, name: "数据采集", kind: "data", steps: [1, 2] },
  { seq: 2, name: "归因分析", kind: "analysis", steps: [3, 4, 5] },
  { seq: 3, name: "行动确认", kind: "approval", steps: [6] },
];

/** 从步骤状态推导阶段投影（后端 AgentStage 是权威来源；此处仅运行中实时兜底） */
function deriveStages(plan: Step[]): Stage[] {
  return STAGE_PLAN.map((st) => {
    const inner = plan.filter((s) => st.steps.includes(s.seq));
    const done = inner.filter((s) => s.status === "Completed" || s.status === "Skipped").length;
    const status = inner.length === 0 ? "Pending"
      : done === 0 ? "Pending"
      : done === inner.length ? "Completed" : "Running";
    return { seq: st.seq, name: st.name, kind: st.kind, steps: st.steps, status };
  });
}

interface ToolResult {
  seq: number;
  tool: string;
  label: string;
  ok?: boolean;
  error?: string;
  summary?: string;
  rows?: any[];
  hits?: { title: string; score: number }[];
  overview?: any;
}

interface Pending {
  approval_id: number;
  title: string;
  customer: string;
  message: string;
  decided?: "approved" | "rejected";
  decidedText?: string;
}

const TOOL_LABEL: Record<string, string> = {
  query_erp_orders: "ERP 销售数据",
  query_crm_customers: "CRM 客户信息",
  search_knowledge: "企业知识库",
  analyze_sales_drop: "销售归因分析引擎",
  create_sales_task: "CRM 任务写入",
  query_monitoring_stations: "核电监测站台账",
  query_device_metrics: "设备指标读数",
  analyze_inspection_anomaly: "巡检异常归因引擎",
  create_workorder: "巡检处置工单",
};

const MODES = ["智能问答", "数据分析", "文档生成", "任务执行", "深度分析"];

/** 识别结果中的业务对象 id（P1：工作台 → 对象中心跳转） */
function objectLinkOf(v: string): { type: string; id: string } | null {
  const m = v.match(/^(CUS-\d{3}|ORD-\d{4}-\d{4}|DEV-SKU-[A-Z]\d{2}|SKU-[A-Z]\d{2}|WO-\d{3}|T-\d{3}|MS-\d{2}|INSP-\d{3}|MET-\d{3}|AREA-[A-Z]{2})$/);
  if (!m) return null;
  const id = m[1];
  const prefix = id.split("-")[0];
  const OBJ_TYPE: Record<string, string> = {
    CUS: "Customer", ORD: "Order", DEV: "Device", SKU: "Product",
    WO: "WorkOrder", T: "Ticket", MS: "MonitoringStation",
    INSP: "InspectionRecord", MET: "MetricRecord", AREA: "Area",
  };
  const type = prefix === "SKU" ? "Product" : OBJ_TYPE[prefix];
  return type ? { type, id } : null;
}

const QUICK = [
  "分析本月销售下降原因",
  "哪些大客户存在流失风险",
  "8月核电设备巡检异常归因",
  "各监测站设备健康度如何",
];

export default function WorkbenchPage() {
  const { user } = useAuth();
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("数据分析");
  const [running, setRunning] = useState(false);
  const [taskId, setTaskId] = useState<number | null>(null);
  const [plan, setPlan] = useState<Step[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [tools, setTools] = useState<ToolResult[]>([]);
  const [report, setReport] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<TaskBrief[]>([]);

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(() => {
    fetchTasks(undefined, 30)
      .then((r) => setHistory(r.items || []))
      .catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [report, tools, pending]);

  function reset() {
    setPlan([]);
    setStages([]);
    setTools([]);
    setReport("");
    setPending(null);
    setError("");
    setTaskId(null);
  }

  const run = useCallback(
    async (q: string) => {
      if (!q.trim() || running) return;
      reset();
      setQuestion(q);
      setRunning(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        const isInspection = /巡检|监测站|辐射|设备健康|工单/.test(q);
        const agentCode = isInspection ? "inspection-analyst" : "sales-analyst";
        await streamSSE(
          "/mainline/run",
          { question: q, agent_code: agentCode },
          (event, data) => {
            if (event === "task") {
              setTaskId(data.task_id);
              setPlan((data.plan || []).map((p: any) => ({ ...p, status: "Pending" })));
            } else if (event === "step") {
              setPlan((prev) => {
                const next = prev.map((s) =>
                  s.seq === data.seq ? { ...s, status: data.status } : s,
                );
                setStages(deriveStages(next));
                return next;
              });
            } else if (event === "tool_result") {
              setTools((prev) => [
                ...prev,
                {
                  seq: prev.length + 1,
                  tool: data.tool,
                  label: TOOL_LABEL[data.tool] || data.tool,
                  ok: data.ok,
                  error: data.error,
                  summary: data.summary,
                  rows: data.rows,
                  hits: data.hits,
                  overview: data.overview,
                },
              ]);
            } else if (event === "token") {
              setReport((prev) => prev + (typeof data === "string" ? data : String(data)));
            } else if (event === "pending") {
              setPending(data as Pending);
            } else if (event === "error") {
              setError(typeof data === "string" ? data : data?.message || "执行失败");
            } else if (event === "done") {
              setRunning(false);
              loadHistory();
            }
          },
          ctrl.signal,
        );
      } catch (e: any) {
        if (e?.name !== "AbortError") setError(e?.message || "连接中断");
      } finally {
        setRunning(false);
        abortRef.current = null;
      }
    },
    [running, loadHistory],
  );

  async function decide(action: "approve" | "reject") {
    if (!pending) return;
    try {
      const r =
        action === "approve"
          ? await approveApproval(pending.approval_id, "在工作台确认执行")
          : await rejectApproval(pending.approval_id, "在工作台拒绝");
      const workorder = r?.result?.workorder_id || r?.workorder;
      const salesTask = r?.sales_task;
      const txt =
        action === "approve"
          ? workorder
            ? `已执行，生成巡检工单 #${r.result?.workorder_id}：${r.result?.title}（负责人 ${r.result?.owner}，截止 ${r.result?.due_date}）`
            : salesTask
              ? `已执行，生成跟进任务 #${salesTask.id}：${salesTask.title}（负责人 ${salesTask.owner}，截止 ${salesTask.due_date}）`
              : "已批准并执行"
          : "已拒绝，Agent 不会执行该动作";
      setPending({ ...pending, decided: action === "approve" ? "approved" : "rejected", decidedText: txt });
      loadHistory();
    } catch (e: any) {
      setPending({ ...pending, decidedText: `操作失败：${e?.message || "未知错误"}` });
    }
  }

  async function openHistory(id: number) {
    try {
      const d = await fetchTaskDetail(id);
      setQuestion(d.input_text || d.title);
      setTaskId(d.id);
      setPlan(
        (d.steps || []).map((s: any) => ({
          seq: s.seq,
          title: s.title,
          status: s.status,
        })),
      );
      setStages(
        Array.isArray(d.stages) && d.stages.length
          ? d.stages
          : deriveStages((d.steps || []).map((s: any) => ({ seq: s.seq, title: s.title, status: s.status }))),
      );
      setTools([]);
      setReport(d.result || "");
      setPending(null);
    } catch {
      /* 详情拉取失败不打断当前视图 */
    }
  }

  const doneCount = plan.filter((s) => s.status === "Completed" || s.status === "Skipped").length;
  const progress = plan.length ? Math.round((doneCount / plan.length) * 100) : 0;

  return (
    <DashboardShell>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">AI 工作台</h1>
          <p className="text-sm text-gray-400 mt-1">
            提出问题，Agent 调用知识、数据与工具完成分析，关键动作需你确认后执行。
          </p>
        </div>
        {taskId && (
          <span className="text-xs px-2.5 py-1 rounded-lg bg-white/[0.05] border border-white/10 text-gray-400">
            任务 #{taskId}
          </span>
        )}
      </div>

      <div className="grid grid-cols-12 gap-5 mt-2">
        {/* 左侧：历史任务 */}
        <aside className="col-span-3 glass-strong rounded-2xl p-4 border border-white/5 h-[calc(100vh-220px)] flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium">任务历史</h3>
            <button
              onClick={() => {
                abortRef.current?.abort();
                reset();
                setQuestion("");
              }}
              className="text-xs px-2.5 py-1 rounded-lg bg-gradient-to-r from-violet-500 to-blue-500 text-white"
            >
              + 新对话
            </button>
          </div>
          <div className="flex-1 overflow-auto -mx-1 px-1 space-y-1">
            {history.length === 0 && (
              <div className="text-xs text-gray-500 px-2 py-6 text-center">暂无任务记录</div>
            )}
            {history.map((h) => (
              <button
                key={h.id}
                onClick={() => openHistory(h.id)}
                className={`w-full text-left px-3 py-2 rounded-xl text-sm transition ${
                  taskId === h.id
                    ? "bg-violet-500/15 border border-violet-400/30 text-white"
                    : "text-gray-400 hover:bg-white/[0.04] hover:text-gray-200"
                }`}
              >
                <div className="truncate">{h.title}</div>
                <div className="flex items-center gap-2 mt-1">
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded ${
                      h.status === "Completed"
                        ? "bg-emerald-500/15 text-emerald-300"
                        : h.status === "WaitingApproval"
                          ? "bg-amber-500/15 text-amber-300"
                          : h.status === "Failed"
                            ? "bg-red-500/15 text-red-300"
                            : "bg-white/[0.06] text-gray-400"
                    }`}
                  >
                    {h.status}
                  </span>
                  <span className="text-[10px] text-gray-500">
                    {h.steps_done}/{h.step_count} 步
                  </span>
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* 主区：执行过程 + 报告 */}
        <section className="col-span-9 space-y-4">
          <div className="glass-strong rounded-2xl border border-white/5 min-h-[calc(100vh-320px)] flex flex-col">
            {!question && plan.length === 0 && !report && (
              <div className="flex-1 flex flex-col items-center justify-center py-16 px-8 text-center">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 to-blue-500 flex items-center justify-center text-2xl shadow-glow mb-4">
                  ✦
                </div>
                <h3 className="text-lg font-medium mb-2">今天想让 AI 帮你做什么？</h3>
                <p className="text-sm text-gray-400 max-w-md leading-relaxed mb-6">
                  {user?.name || ""} 你好，我可以直接查询 ERP/CRM 数据、检索企业知识，
                  并在关键动作前停下来等你确认。
                </p>
                <div className="flex flex-wrap gap-2 justify-center max-w-xl">
                  {QUICK.map((q) => (
                    <button
                      key={q}
                      onClick={() => run(q)}
                      className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/5 text-gray-300"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {(question || plan.length > 0 || report) && (
              <div className="flex-1 overflow-auto p-5 space-y-4">
                {question && (
                  <div className="flex justify-end">
                    <div className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-br-md bg-violet-500/20 border border-violet-400/25 text-sm text-white">
                      {question}
                    </div>
                  </div>
                )}

                {error && (
                  <div className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-400/25 text-sm text-red-300">
                    {error}
                  </div>
                )}

                {/* 阶段投影（40-06：Stage/Checkpoint） */}
                {stages.length > 0 && (
                  <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-medium">阶段进度</span>
                      <span className="text-[11px] text-gray-400">
                        {stages.filter((s) => s.status === "Completed").length}/{stages.length} 阶段
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      {stages.map((st, i) => (
                        <div
                          key={st.seq}
                          className={`relative rounded-lg border p-3 ${
                            st.status === "Completed"
                              ? "border-emerald-400/25 bg-emerald-500/[0.06]"
                              : st.status === "Running"
                                ? "border-amber-400/25 bg-amber-500/[0.06]"
                                : "border-white/[0.06] bg-white/[0.02]"
                          }`}
                        >
                          {i < stages.length - 1 && (
                            <div className="absolute right-[-8px] top-1/2 -translate-y-1/2 text-gray-600">
                              →
                            </div>
                          )}
                          <div className="flex items-center gap-1.5 mb-1">
                            {st.status === "Completed" ? (
                              <span className="text-emerald-400 text-xs">✓</span>
                            ) : st.status === "Running" ? (
                              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse2" />
                            ) : (
                              <span className="w-2 h-2 rounded-full bg-white/20" />
                            )}
                            <span className="text-xs font-medium text-gray-200">
                              {st.seq}. {st.name}
                            </span>
                          </div>
                          <div className="text-[10px] text-gray-500">
                            {st.status === "Completed"
                              ? st.checkpoint
                                ? "已完成 · 产出已归档"
                                : "已完成"
                              : st.status === "Running"
                                ? "进行中"
                                : "待开始"}
                          </div>
                          {st.checkpoint && (
                            <div className="mt-1.5 text-[10px] text-violet-300/80 leading-snug">
                              {Object.entries(st.checkpoint)
                                .filter(([k]) => !["stage_seq", "stage_name"].includes(k))
                                .slice(0, 2)
                                .map(([k, v]) => (
                                  <div key={k} className="truncate">
                                    {k}: {typeof v === "object" ? JSON.stringify(v).slice(0, 40) : String(v)}
                                  </div>
                                ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 执行计划 */}
                {plan.length > 0 && (
                  <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-medium">执行计划</span>
                      <span className="text-[11px] text-gray-400">
                        {doneCount}/{plan.length} 步 · {progress}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/[0.06] mb-3 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-violet-500 to-blue-500 transition-all duration-500"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    <ul className="space-y-2">
                      {plan.map((s) => (
                        <li key={s.seq} className="flex items-center gap-2.5 text-sm">
                          {s.status === "Completed" ? (
                            <span className="text-emerald-400">✓</span>
                          ) : s.status === "Running" ? (
                            <span className="w-3 h-3 rounded-full bg-amber-400 animate-pulse2" />
                          ) : s.status === "Failed" ? (
                            <span className="text-red-400">✕</span>
                          ) : s.status === "Skipped" ? (
                            <span className="text-gray-500">↷</span>
                          ) : (
                            <span className="text-gray-600">○</span>
                          )}
                          <span
                            className={
                              s.status === "Pending" ? "text-gray-500" : "text-gray-200"
                            }
                          >
                            {s.seq}. {s.title}
                          </span>
                          {s.status === "Running" && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300">
                              进行中
                            </span>
                          )}
                          {s.status === "Skipped" && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-gray-400">
                              已跳过
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 工具调用结果 */}
                {tools.map((t, idx) => (
                  <div
                    key={idx}
                    className={`rounded-xl border p-4 animate-slideUp ${
                      t.ok === false
                        ? "border-red-400/30 bg-red-500/[0.06]"
                        : "border-white/[0.07] bg-white/[0.02]"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2.5">
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded ${
                          t.ok === false
                            ? "bg-red-500/20 text-red-300"
                            : "bg-cyan-500/15 text-cyan-300"
                        }`}
                      >
                        {t.ok === false ? "调用失败" : "工具调用"}
                      </span>
                      <span className="text-xs text-gray-400">{t.label}</span>
                    </div>

                    {t.error && (
                      <p className="text-[13px] text-red-300 leading-relaxed mb-2">{t.error}</p>
                    )}

                    {t.summary && (
                      <p className="text-[13px] text-gray-300 leading-relaxed">{t.summary}</p>
                    )}

                    {t.rows && t.rows.length > 0 && (
                      <div className="overflow-x-auto rounded-lg border border-white/[0.06]">
                        <table className="w-full text-[12.5px]">
                          <thead className="bg-white/[0.04]">
                            <tr>
                              {Object.keys(t.rows[0]).map((k) => (
                                <th
                                  key={k}
                                  className="px-2.5 py-1.5 text-left font-medium text-gray-400 whitespace-nowrap"
                                >
                                  {k}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {t.rows.map((r, ri) => (
                              <tr key={ri} className="border-t border-white/[0.05]">
                                {Object.values(r).map((v: any, ci) => {
                                  const ol = objectLinkOf(String(v));
                                  return (
                                  <td
                                    key={ci}
                                    className="px-2.5 py-1.5 text-gray-300 whitespace-nowrap"
                                  >
                                    {ol ? (
                                      <Link
                                        href={`/objects?type=${ol.type}&id=${encodeURIComponent(ol.id)}`}
                                        className="text-violet-300 hover:text-violet-200 underline decoration-dotted"
                                      >
                                        {String(v)}
                                      </Link>
                                    ) : (
                                      String(v)
                                    )}
                                  </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {t.hits && t.hits.length > 0 && (
                      <div className="space-y-1.5">
                        {t.hits.map((h, hi) => (
                          <div
                            key={hi}
                            className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.05]"
                          >
                            <span className="text-[13px] text-gray-300">{h.title}</span>
                            <span className="text-[11px] text-violet-300">
                              相关度 {h.score}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {t.overview && (
                      <div className="grid grid-cols-4 gap-2">
                        {[
                          ["上月", `${t.overview.previous?.amt_wan ?? "-"} 万`],
                          ["本月", `${t.overview.current?.amt_wan ?? "-"} 万`],
                          ["增减", `${t.overview.delta_amt_wan ?? "-"} 万`],
                          ["环比", `${t.overview.pct ?? "-"}%`],
                        ].map(([k, v]) => (
                          <div
                            key={k}
                            className="rounded-lg bg-white/[0.03] border border-white/[0.05] px-3 py-2"
                          >
                            <div className="text-[10px] text-gray-500">{k}</div>
                            <div className="text-[13px] text-gray-100 mt-0.5">{v}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {/* 流式报告 */}
                {report && (
                  <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-500 to-blue-500 flex items-center justify-center text-[11px]">
                        ✦
                      </div>
                      <span className="text-sm font-medium">分析报告</span>
                      {running && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300">
                          生成中
                        </span>
                      )}
                    </div>
                    <Markdown text={report} />
                    {running && (
                      <span className="inline-block w-1.5 h-4 bg-violet-400 animate-pulse2 align-middle ml-0.5" />
                    )}
                  </div>
                )}

                {/* 待确认卡片 */}
                {pending && (
                  <div className="rounded-xl border border-amber-400/25 bg-amber-500/[0.07] p-4 animate-slideUp">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">
                        Level 3 · 需人工确认
                      </span>
                      <span className="text-sm font-medium text-white">{pending.title}</span>
                    </div>
                    <p className="text-[13px] text-gray-300 leading-relaxed mb-3">
                      {pending.message}
                    </p>
                    {pending.decided ? (
                      <div
                        className={`text-[13px] px-3 py-2 rounded-lg ${
                          pending.decided === "approved"
                            ? "bg-emerald-500/10 text-emerald-300"
                            : "bg-red-500/10 text-red-300"
                        }`}
                      >
                        {pending.decidedText}
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => decide("approve")}
                          className="text-xs px-4 py-1.5 rounded-lg bg-gradient-to-r from-violet-500 to-blue-500 text-white"
                        >
                          确认执行
                        </button>
                        <button
                          onClick={() => decide("reject")}
                          className="text-xs px-4 py-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.09] border border-white/10 text-gray-300"
                        >
                          拒绝
                        </button>
                        <span className="text-[11px] text-gray-500">
                          Agent 在人工确认前不会写入任何业务数据
                        </span>
                      </div>
                    )}
                  </div>
                )}

                <div ref={bottomRef} />
              </div>
            )}

            {/* 输入区 */}
            <div className="p-4 border-t border-white/[0.06]">
              <div className="flex items-center gap-2 mb-3 flex-wrap">
                {MODES.map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`text-xs px-2.5 py-1 rounded-lg border transition ${
                      mode === m
                        ? "bg-violet-500/20 border-violet-400/40 text-white"
                        : "bg-white/[0.03] border-white/[0.06] text-gray-400 hover:text-gray-200"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-3 px-4 py-2.5 rounded-2xl glass border border-white/5">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !running) {
                      run(input);
                      setInput("");
                    }
                  }}
                  placeholder="请输入您的问题…"
                  disabled={running}
                  className="flex-1 bg-transparent outline-none text-sm placeholder:text-gray-500 disabled:opacity-60"
                />
                {running ? (
                  <button
                    onClick={() => abortRef.current?.abort()}
                    className="w-9 h-9 rounded-xl bg-white/[0.06] text-gray-300 flex items-center justify-center text-xs"
                  >
                    ■
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      run(input);
                      setInput("");
                    }}
                    className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-blue-500 text-white flex items-center justify-center shadow-glow"
                  >
                    ➤
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>
      </div>
    </DashboardShell>
  );
}
