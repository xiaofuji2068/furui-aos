"use client";

import { useCallback, useEffect, useState } from "react";
import DashboardShell from "../../components/DashboardShell";
import { useAuth } from "../../components/AuthProvider";
import {
  fetchKnowledgeBases,
  fetchKnowledgeDocuments,
  fetchKnowledgeOverview,
  uploadKnowledgeDoc,
  submitKnowledgeDoc,
  publishKnowledgeDoc,
  type KnowledgeDoc,
  type KnowledgeOverview,
} from "../../lib/api";

const STATUS_STYLE: Record<string, string> = {
  已发布: "bg-emerald-500/15 text-emerald-300",
  草稿: "bg-white/[0.06] text-gray-400",
  审核中: "bg-amber-500/15 text-amber-300",
  已过期: "bg-rose-500/15 text-rose-300",
  已归档: "bg-white/[0.06] text-gray-500",
};

export default function KnowledgePage() {
  const { user } = useAuth();
  const canManage = !!user?.permissions?.includes("knowledge:manage");

  const [data, setData] = useState<KnowledgeOverview | null>(null);
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [bases, setBases] = useState<{ id: number; name: string; category: string }[]>([]);
  const [error, setError] = useState("");

  // 上传表单
  const [showUpload, setShowUpload] = useState(false);
  const [form, setForm] = useState({
    kb_id: 0,
    title: "",
    content: "",
    source: "",
    valid_days: "",
  });
  const [uploading, setUploading] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);
  const [toast, setToast] = useState("");

  const load = useCallback(() => {
    fetchKnowledgeOverview()
      .then(setData)
      .catch((e: any) => setError(e?.message || "加载失败"));
    fetchKnowledgeDocuments()
      .then((r) => setDocs(r.items || []))
      .catch(() => setDocs([]));
    fetchKnowledgeBases()
      .then((r) => {
        const items = r.items || [];
        setBases(items);
        setForm((f) => (f.kb_id ? f : { ...f, kb_id: items[0]?.id || 0 }));
      })
      .catch(() => setBases([]));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function submitUpload() {
    if (!form.title.trim() || !form.content.trim() || !form.kb_id) {
      setToast("请填写标题、内容并选择知识库");
      return;
    }
    setUploading(true);
    setToast("");
    try {
      const r = await uploadKnowledgeDoc({
        kb_id: form.kb_id,
        title: form.title.trim(),
        content: form.content,
        source: form.source.trim() || "手工录入",
        file_type: "txt",
        valid_days: form.valid_days ? Number(form.valid_days) : null,
      });
      setToast(
        `已存为草稿：${r.title} —— 切分为 ${r.chunk_count} 个片段，提交审核并发布后 Agent 才会引用`,
      );
      setForm({ ...form, title: "", content: "", source: "" });
      setShowUpload(false);
      load();
    } catch (e: any) {
      setToast(`上传失败：${e?.message || "未知错误"}`);
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmitDoc(doc: KnowledgeDoc) {
    setActingId(doc.id);
    setToast("");
    try {
      await submitKnowledgeDoc(doc.id);
      setToast(`「${doc.title}」已提交审核`);
      load();
    } catch (e: any) {
      setToast(`提交失败：${e?.message || "未知错误"}`);
    } finally {
      setActingId(null);
    }
  }

  async function handlePublishDoc(doc: KnowledgeDoc) {
    setActingId(doc.id);
    setToast("");
    try {
      await publishKnowledgeDoc(doc.id);
      setToast(`「${doc.title}」已发布，Agent 现在可以引用`);
      load();
    } catch (e: any) {
      setToast(`发布失败：${e?.message || "未知错误"}`);
    } finally {
      setActingId(null);
    }
  }

  if (error) {
    return (
      <DashboardShell>
        <div className="glass-strong rounded-2xl border border-red-400/25 p-6 text-sm text-red-300">
          {error}
        </div>
      </DashboardShell>
    );
  }

  if (!data) return <DashboardShell><Skeleton /></DashboardShell>;

  const { kpis, health, reminders, categories } = data;

  // 健康度环形
  const r = 64, cx = 80, cy = 80;
  const C = 2 * Math.PI * r;
  const offset = C * (1 - health.score / 100);

  return (
    <DashboardShell>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{data.title}</h1>
          <p className="text-sm text-gray-400 mt-1">{data.subtitle}</p>
        </div>
        {canManage && (
          <button
            onClick={() => setShowUpload((v) => !v)}
            className="text-xs px-3 py-1.5 rounded-lg bg-gradient-to-r from-violet-500 to-blue-500 text-white"
          >
            {showUpload ? "收起" : "+ 上传知识"}
          </button>
        )}
      </div>

      {toast && (
        <div className="mt-3 px-4 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-400/25 text-[13px] text-emerald-300">
          {toast}
        </div>
      )}

      {/* 上传面板 */}
      {showUpload && canManage && (
        <div className="glass-strong rounded-2xl border border-white/5 p-5 space-y-3 animate-slideUp">
          <h3 className="text-sm font-medium">上传知识文档</h3>
          <div className="grid grid-cols-3 gap-3">
            <select
              value={form.kb_id}
              onChange={(e) => setForm({ ...form, kb_id: Number(e.target.value) })}
              className="px-3 py-2 rounded-xl glass border border-white/[0.08] bg-transparent outline-none text-sm"
            >
              {bases.map((b) => (
                <option key={b.id} value={b.id} className="bg-ink-800">
                  {b.name}（{b.category}）
                </option>
              ))}
            </select>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="文档标题"
              className="px-3 py-2 rounded-xl glass border border-white/[0.08] bg-transparent outline-none text-sm placeholder:text-gray-600"
            />
            <input
              value={form.source}
              onChange={(e) => setForm({ ...form, source: e.target.value })}
              placeholder="来源（如：质量管理部 · 2026 修订版）"
              className="px-3 py-2 rounded-xl glass border border-white/[0.08] bg-transparent outline-none text-sm placeholder:text-gray-600"
            />
          </div>
          <textarea
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
            placeholder="粘贴文档正文（支持纯文本 / Markdown）。上传后自动清洗、分块、向量化入库。"
            rows={6}
            className="w-full px-3 py-2.5 rounded-xl glass border border-white/[0.08] bg-transparent outline-none text-sm placeholder:text-gray-600 resize-y"
          />
          <div className="flex items-center gap-3">
            <input
              value={form.valid_days}
              onChange={(e) => setForm({ ...form, valid_days: e.target.value })}
              placeholder="有效期天数（留空=长期）"
              className="w-52 px-3 py-2 rounded-xl glass border border-white/[0.08] bg-transparent outline-none text-sm placeholder:text-gray-600"
            />
            <button
              onClick={submitUpload}
              disabled={uploading}
              className="text-xs px-4 py-2 rounded-lg bg-gradient-to-r from-violet-500 to-blue-500 text-white disabled:opacity-50"
            >
              {uploading ? "入库中…" : "确认入库"}
            </button>
            <span className="text-[11px] text-gray-500">
              Agent 只会引用「已发布」且在有效期内的知识
            </span>
          </div>
        </div>
      )}

      {/* 顶部 KPI 横条 */}
      <div className="grid grid-cols-5 gap-4">
        {kpis.map((k) => (
          <div key={k.label} className="glass-strong rounded-2xl p-4 border border-white/5">
            <div className="text-xs text-gray-400">{k.label}</div>
            <div className="mt-1.5 flex items-baseline gap-1">
              <span className="text-2xl font-semibold text-gradient-blue">{k.value}</span>
              {k.unit && <span className="text-xs text-gray-500">{k.unit}</span>}
            </div>
          </div>
        ))}
      </div>

      {/* 健康度 + 提醒 */}
      <div className="grid grid-cols-12 gap-5">
        <section className="col-span-7 glass-strong rounded-2xl p-5 border border-white/5">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-sm font-medium">知识健康度</h3>
            <span className="text-[11px] text-gray-500">
              依据 {health.basis?.docs ?? 0} 份文档实时计算
            </span>
          </div>
          <div className="grid grid-cols-2 gap-6 items-center">
            <div className="flex flex-col items-center justify-center">
              <svg viewBox="0 0 160 160" width={180} height={180}>
                <defs>
                  <linearGradient id="health-grad" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#10b981" />
                    <stop offset="100%" stopColor="#3b82f6" />
                  </linearGradient>
                </defs>
                <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
                <circle cx={cx} cy={cy} r={r} fill="none"
                  stroke="url(#health-grad)" strokeWidth="10"
                  strokeDasharray={C} strokeDashoffset={offset}
                  strokeLinecap="round"
                  transform={`rotate(-90 ${cx} ${cy})`} />
                <text x={cx} y={cy - 2} textAnchor="middle" fontSize="36" fill="white" fontWeight="600">{health.score}</text>
                <text x={cx} y={cy + 18} textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.5)">{health.level}</text>
              </svg>
              <div className="mt-3 text-xs text-gray-400">
                近 30 天新增占比 <span className="text-emerald-300 ml-1">+{health.delta}%</span>
              </div>
            </div>

            <div className="space-y-3">
              {health.dimensions.map((d) => (
                <div key={d.label}>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="text-gray-300">{d.label}</span>
                    <span className="text-gray-400 tabular-nums">{d.value}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                    <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-blue-400"
                      style={{ width: `${d.value}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="col-span-5 glass-strong rounded-2xl p-5 border border-white/5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium">知识更新提醒</h3>
            <span className="text-[11px] text-gray-500">由数据扫描生成</span>
          </div>
          {reminders.length === 0 ? (
            <div className="text-[13px] text-gray-500 py-6 text-center">
              暂无待处理事项，知识库状态良好
            </div>
          ) : (
            <ul className="space-y-2.5">
              {reminders.map((r) => (
                <li key={r.id} className="flex items-center justify-between px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/5">
                  <span className="text-sm text-gray-200 truncate flex-1 mr-2">{r.text}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${r.tagCls}`}>{r.tag}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* 知识分类 */}
      <section className="glass-strong rounded-2xl p-5 border border-white/5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium">知识分类</h3>
          <span className="text-[11px] text-gray-500">按知识库类别聚合</span>
        </div>
        {categories.length === 0 ? (
          <div className="text-[13px] text-gray-500 py-6 text-center">暂无知识库</div>
        ) : (
          <div className="grid grid-cols-5 gap-4">
            {categories.map((c) => (
              <div key={c.name} className={`relative rounded-2xl p-4 overflow-hidden border border-white/5 bg-gradient-to-br ${c.color}`}>
                <div className="absolute inset-0 bg-ink-900/50" />
                <div className="relative">
                  <div className="text-2xl mb-2">{c.icon}</div>
                  <div className="text-sm font-medium">{c.name}</div>
                  <div className="mt-2 flex items-baseline gap-1">
                    <span className="text-xl font-semibold">{c.value}</span>
                    <span className="text-xs text-gray-300">份</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 文档清单 */}
      <section className="glass-strong rounded-2xl p-5 border border-white/5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium">知识文档</h3>
          <span className="text-[11px] text-gray-500">{docs.length} 份</span>
        </div>
        {docs.length === 0 ? (
          <div className="text-[13px] text-gray-500 py-6 text-center">暂无文档</div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-white/[0.06]">
            <table className="w-full text-[13px]">
              <thead className="bg-white/[0.04]">
                <tr>
                  {["标题", "知识库", "状态", "来源", "分片", "字数", "有效期至", "上传人", "操作"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id} className="border-t border-white/[0.05]">
                    <td className="px-3 py-2 text-gray-200 max-w-[260px] truncate">{d.title}</td>
                    <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{d.kb_name}</td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${STATUS_STYLE[d.status] || "bg-white/[0.06] text-gray-400"}`}>
                        {d.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-gray-400 max-w-[180px] truncate">{d.source || "—"}</td>
                    <td className="px-3 py-2 text-gray-400 tabular-nums">{d.chunk_count}</td>
                    <td className="px-3 py-2 text-gray-400 tabular-nums">{d.char_count.toLocaleString()}</td>
                    <td className="px-3 py-2 text-gray-400 whitespace-nowrap">
                      {d.valid_to ? d.valid_to.slice(0, 10) : "长期"}
                    </td>
                    <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{d.author || "—"}</td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {d.status === "草稿" && (
                        <button
                          onClick={() => handleSubmitDoc(d)}
                          disabled={actingId === d.id}
                          className="text-[10px] px-2 py-1 rounded bg-violet-500/15 text-violet-300 hover:bg-violet-500/25 disabled:opacity-50"
                        >
                          {actingId === d.id ? "提交中…" : "提交审核"}
                        </button>
                      )}
                      {d.status === "审核中" && (
                        <button
                          onClick={() => handlePublishDoc(d)}
                          disabled={actingId === d.id}
                          className="text-[10px] px-2 py-1 rounded bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-50"
                        >
                          {actingId === d.id ? "发布中…" : "发布"}
                        </button>
                      )}
                      {d.status !== "草稿" && d.status !== "审核中" && (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </DashboardShell>
  );
}

function Skeleton() {
  return (
    <div className="space-y-5 animate-pulse2">
      <div className="h-8 w-56 rounded-lg bg-white/[0.04]" />
      <div className="grid grid-cols-5 gap-4">
        {[0, 1, 2, 3, 4].map(i => <div key={i} className="h-20 rounded-2xl bg-white/[0.03]" />)}
      </div>
      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-7 h-64 rounded-2xl bg-white/[0.03]" />
        <div className="col-span-5 h-64 rounded-2xl bg-white/[0.03]" />
      </div>
      <div className="h-40 rounded-2xl bg-white/[0.03]" />
    </div>
  );
}
