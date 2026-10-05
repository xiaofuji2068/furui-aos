"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import DashboardShell from "../../components/DashboardShell";
import { useAuth } from "../../components/AuthProvider";
import {
  createDataAsset,
  deleteDataAsset,
  fetchDataAssets,
  fetchDataAssetsLineage,
  fetchDataSources,
  syncDataAsset,
  type DataAsset,
  type DataSourceItem,
} from "../../lib/api";

const HEALTH_STYLE: Record<string, string> = {
  healthy: "bg-emerald-500/15 text-emerald-300",
  warning: "bg-amber-500/15 text-amber-300",
  error: "bg-rose-500/15 text-rose-300",
  stale: "bg-gray-500/15 text-gray-400",
};

const HEALTH_TEXT: Record<string, string> = {
  healthy: "健康",
  warning: "告警",
  error: "异常",
  stale: "过期",
};

export default function AssetsPage() {
  const { user } = useAuth();
  const canView = !!user?.permissions?.includes("datasource:view");
  const canConfig = !!user?.permissions?.includes("datasource:config");

  const [assets, setAssets] = useState<DataAsset[]>([]);
  const [lineage, setLineage] = useState<Array<{ source_id: string; source_name: string; source_status: string; datasets: DataAsset[] }>>([]);
  const [sources, setSources] = useState<DataSourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  // 新增弹窗
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", source_id: "", entity: "", row_count: "", fields: "" });
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    if (!canView) return;
    setLoading(true);
    Promise.all([
      fetchDataAssets().catch(() => ({ items: [], total: 0 })),
      fetchDataAssetsLineage().catch(() => ({ items: [], total: 0 })),
      fetchDataSources().catch(() => ({ items: [] })),
    ]).then(([a, l, s]) => {
      setAssets(a.items || []);
      setLineage(l.items || []);
      setSources(s.items || []);
      setLoading(false);
    });
  }, [canView]);

  useEffect(() => {
    load();
  }, [load]);

  const stats = useMemo(() => {
    const total = assets.length;
    const healthy = assets.filter((a) => a.health_status === "healthy").length;
    const sourcesCovered = new Set(assets.map((a) => a.source_id)).size;
    const rows = assets.reduce((s, a) => s + (a.row_count || 0), 0);
    return { total, healthy, sourcesCovered, rows };
  }, [assets]);

  function toastMsg(t: string) {
    setToast(t);
    setTimeout(() => setToast(""), 3500);
  }

  async function doSync(id: number) {
    setBusy(`sync-${id}`);
    try {
      const r = await syncDataAsset(id);
      toastMsg(`同步完成：${r.row_count?.toLocaleString?.() || r.row_count || "?"} 行 · 版本 ${r.version} · ${r.health_status || "—"}`);
      load();
    } catch (e: any) {
      toastMsg(`同步失败：${e?.message || "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  async function doDelete(a: DataAsset) {
    if (!confirm(`确认删除资产「${a.name}」？该操作不可撤销。`)) return;
    setBusy(`del-${a.id}`);
    try {
      await deleteDataAsset(a.id);
      toastMsg(`已删除「${a.name}」`);
      load();
    } catch (e: any) {
      toastMsg(`删除失败：${e?.message || "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  async function submitAdd() {
    if (!form.name.trim() || !form.source_id) {
      toastMsg("请填写资产名称并选择数据源");
      return;
    }
    setAdding(true);
    try {
      await createDataAsset({
        name: form.name.trim(),
        source_id: form.source_id,
        entity: form.entity.trim() || "table",
        row_count: parseInt(form.row_count || "0", 10) || 0,
        fields: form.fields.split(/[,，\s]+/).map((f) => f.trim()).filter(Boolean),
      });
      toastMsg("资产已创建");
      setShowAdd(false);
      setForm({ name: "", source_id: "", entity: "", row_count: "", fields: "" });
      load();
    } catch (e: any) {
      toastMsg(`创建失败：${e?.message || "未知错误"}`);
    } finally {
      setAdding(false);
    }
  }

  if (!canView) {
    return (
      <DashboardShell>
        <div className="text-sm text-gray-400 py-20 text-center">无权限查看数据资产（需要 datasource:view）</div>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <div className="flex items-end justify-between mb-5">
        <div>
          <h1 className="text-2xl font-semibold">数据资产</h1>
          <p className="text-sm text-gray-400 mt-1">数据源接入 · 资产治理 · 血缘追踪 · 同步健康</p>
        </div>
        {canConfig && (
          <button
            onClick={() => setShowAdd(true)}
            className="text-sm px-4 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 text-white shadow-glow hover:opacity-90"
          >
            + 新增资产
          </button>
        )}
      </div>

      {/* 统计卡 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          { label: "资产总数", value: String(stats.total), tone: "text-gray-100" },
          { label: "健康资产", value: `${stats.healthy}/${stats.total}`, tone: "text-emerald-300" },
          { label: "覆盖数据源", value: String(stats.sourcesCovered), tone: "text-blue-300" },
          { label: "累计行数", value: stats.rows >= 10000 ? `${(stats.rows / 10000).toFixed(1)}w` : stats.rows.toLocaleString(), tone: "text-gray-100" },
        ].map((s) => (
          <div key={s.label} className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
            <div className="text-[11px] text-gray-500">{s.label}</div>
            <div className={`text-xl font-semibold mt-1 ${s.tone}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {toast && (
        <div className="mb-4 text-xs px-4 py-2.5 rounded-xl border border-violet-400/20 bg-violet-500/10 text-violet-200">
          {toast}
        </div>
      )}

      {loading ? (
        <div className="h-40 rounded-2xl bg-white/[0.03] animate-pulse2" />
      ) : error ? (
        <div className="text-sm text-rose-300 py-16 text-center">{error}</div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[340px_1fr] gap-4 items-start">
          {/* 血缘视图 */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] overflow-hidden">
            <div className="px-4 py-2.5 text-xs font-medium text-gray-300 border-b border-white/5 flex items-center justify-between">
              <span>数据血缘</span>
              <span className="text-[10px] text-gray-600">{lineage.length} 个来源</span>
            </div>
            <div className="p-4 space-y-3">
              {lineage.length === 0 && <div className="text-xs text-gray-600 py-6 text-center">暂无资产，先新增一个</div>}
              {lineage.map((src) => (
                <div key={src.source_id}>
                  <div className="flex items-center gap-2 text-xs mb-1.5">
                    <span className="w-6 h-6 rounded-lg bg-blue-500/15 border border-blue-400/20 flex items-center justify-center">🗄</span>
                    <span className="text-gray-200 font-medium">{src.source_name}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${src.source_status === "connected" ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>
                      {src.source_status === "connected" ? "已连接" : src.source_status}
                    </span>
                  </div>
                  <div className="ml-8 space-y-1">
                    {src.datasets.map((d) => (
                      <div key={d.id} className="flex items-center gap-2 text-[11px] text-gray-400">
                        <span className="text-gray-600">└─</span>
                        <span className="truncate">{d.name}</span>
                        <span className="text-gray-600 ml-auto shrink-0">v{d.version}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 资产表格 */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] overflow-hidden">
            <div className="px-4 py-2.5 text-xs font-medium text-gray-300 border-b border-white/5">资产清单</div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-white/5">
                    <th className="px-4 py-2.5 font-medium">资产</th>
                    <th className="px-3 py-2.5 font-medium">来源</th>
                    <th className="px-3 py-2.5 font-medium">实体</th>
                    <th className="px-3 py-2.5 font-medium text-right">行数</th>
                    <th className="px-3 py-2.5 font-medium">版本</th>
                    <th className="px-3 py-2.5 font-medium">健康</th>
                    <th className="px-3 py-2.5 font-medium">最近同步</th>
                    {canConfig && <th className="px-3 py-2.5 font-medium text-right">操作</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {assets.length === 0 && (
                    <tr>
                      <td colSpan={canConfig ? 8 : 7} className="px-4 py-12 text-center text-gray-600">
                        暂无数据资产
                      </td>
                    </tr>
                  )}
                  {assets.map((a) => (
                    <tr key={a.id} className="hover:bg-white/[0.02]">
                      <td className="px-4 py-3">
                        <div className="text-gray-200 font-medium">{a.name}</div>
                        <div className="text-[10px] text-gray-500 mt-0.5 truncate max-w-[180px]">{a.fields?.join(", ") || "—"}</div>
                      </td>
                      <td className="px-3 py-3 text-gray-400">{a.source_name}</td>
                      <td className="px-3 py-3 text-gray-400 font-mono">{a.entity}</td>
                      <td className="px-3 py-3 text-right text-gray-200 font-mono">{a.row_count?.toLocaleString() || "0"}</td>
                      <td className="px-3 py-3 text-gray-400">{a.version}</td>
                      <td className="px-3 py-3">
                        <span className={`text-[10px] px-2 py-0.5 rounded-md ${HEALTH_STYLE[a.health_status] || "bg-white/5 text-gray-400"}`}>
                          {HEALTH_TEXT[a.health_status] || a.health_status}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-gray-500">
                        {a.last_sync_at ? new Date(a.last_sync_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—"}
                      </td>
                      {canConfig && (
                        <td className="px-3 py-3">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              disabled={busy === `sync-${a.id}`}
                              onClick={() => doSync(a.id)}
                              className="text-[11px] px-2.5 py-1 rounded-lg border border-white/10 text-gray-300 hover:text-white hover:bg-white/5 disabled:opacity-40 transition"
                            >
                              {busy === `sync-${a.id}` ? "同步中…" : "同步"}
                            </button>
                            <button
                              disabled={busy === `del-${a.id}`}
                              onClick={() => doDelete(a)}
                              className="text-[11px] px-2.5 py-1 rounded-lg border border-rose-500/20 text-rose-300 hover:bg-rose-500/10 disabled:opacity-40 transition"
                            >
                              删除
                            </button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 新增资产弹窗 */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowAdd(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-lg rounded-2xl border border-white/10 glass-strong p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="text-base font-semibold mb-1">新增数据资产</div>
            <div className="text-xs text-gray-400 mb-4">从已接入数据源创建一个数据集资产</div>
            <div className="space-y-3">
              <div>
                <label className="block text-[11px] text-gray-500 mb-1">资产名称 *</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="如：ERP 订单明细"
                  className="w-full text-xs bg-white/[0.04] border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-violet-400/40 placeholder:text-gray-600"
                />
              </div>
              <div>
                <label className="block text-[11px] text-gray-500 mb-1">来源数据源 *</label>
                <select
                  value={form.source_id}
                  onChange={(e) => setForm({ ...form, source_id: e.target.value })}
                  className="w-full text-xs bg-[#161b2e] border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-violet-400/40"
                >
                  <option value="">选择数据源…</option>
                  {sources.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}（{s.id}）</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-gray-500 mb-1">实体名（表名）</label>
                  <input
                    value={form.entity}
                    onChange={(e) => setForm({ ...form, entity: e.target.value })}
                    placeholder="orders"
                    className="w-full text-xs bg-white/[0.04] border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-violet-400/40 placeholder:text-gray-600"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-gray-500 mb-1">初始行数</label>
                  <input
                    value={form.row_count}
                    onChange={(e) => setForm({ ...form, row_count: e.target.value })}
                    placeholder="1200"
                    type="number"
                    className="w-full text-xs bg-white/[0.04] border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-violet-400/40 placeholder:text-gray-600"
                  />
                </div>
              </div>
              <div>
                <label className="block text-[11px] text-gray-500 mb-1">字段（逗号分隔）</label>
                <input
                  value={form.fields}
                  onChange={(e) => setForm({ ...form, fields: e.target.value })}
                  placeholder="order_id, customer_id, amount"
                  className="w-full text-xs bg-white/[0.04] border border-white/10 rounded-lg px-3 py-2 outline-none focus:border-violet-400/40 placeholder:text-gray-600"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => setShowAdd(false)}
                className="text-xs px-4 py-2 rounded-lg border border-white/10 text-gray-300 hover:text-white hover:bg-white/5 transition"
              >
                取消
              </button>
              <button
                onClick={submitAdd}
                disabled={adding}
                className="text-xs px-4 py-2 rounded-lg bg-gradient-to-r from-violet-500 to-blue-500 text-white disabled:opacity-50 hover:opacity-90 transition"
              >
                {adding ? "创建中…" : "创建资产"}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardShell>
  );
}
