"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import DashboardShell from "../../components/DashboardShell";
import { useAuth } from "../../components/AuthProvider";
import {
  createRelease,
  fetchReleases,
  promoteRelease,
  recallRelease,
  type ReleaseItem,
} from "../../lib/api";

/**
 * 交付发布管理（TASK-017 / 80-01 + 80-02）。
 *
 * 与平台资产中心（/assets/center）的区别：
 *   资产中心管「租户装了哪些页面/决策图」——看的是租户视角；
 *   本页管「产品版本怎么发到各环境、通道怎么推进、签名是否还对得上」——看的是交付视角。
 */

const CHANNEL_BADGE: Record<string, string> = {
  draft: "bg-amber-500/15 text-amber-300",
  staging: "bg-sky-500/15 text-sky-300",
  production: "bg-emerald-500/15 text-emerald-300",
};

const STATUS_TEXT: Record<string, string> = {
  draft: "草稿",
  promoted: "已发布",
  recalled: "已召回",
  superseded: "已归档",
};

/** 通道推进顺序：draft → staging → production（production 为终点） */
const NEXT_CHANNEL: Record<string, string> = {
  draft: "staging",
  staging: "production",
  production: "",
};

const CHANNELS = ["draft", "staging", "production"];

export default function ReleasesPage() {
  const { user } = useAuth();
  const canConfig = !!user?.permissions?.includes("tool:config");

  const [rows, setRows] = useState<ReleaseItem[]>([]);
  const [channel, setChannel] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  // 新建弹层
  const [showNew, setShowNew] = useState(false);
  const [nVersion, setNVersion] = useState("");
  const [nChannel, setNChannel] = useState("draft");
  const [nNotes, setNNotes] = useState("");
  const [nChanges, setNChanges] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetchReleases(channel || undefined);
      setRows(r.items || []);
      setError("");
    } catch (e: any) {
      setError(e?.message || "加载 Release 列表失败");
    } finally {
      setLoading(false);
    }
  }, [channel]);

  useEffect(() => {
    load();
  }, [load]);

  const stats = useMemo(() => {
    const valid = rows.filter((r) => r.signature_valid).length;
    const prod = rows.filter((r) => r.channel === "production").length;
    const changes = rows.reduce((s, r) => s + (r.changes?.length || 0), 0);
    return { total: rows.length, valid, prod, changes };
  }, [rows]);

  function toastMsg(t: string) {
    setToast(t);
    setTimeout(() => setToast(""), 3800);
  }

  /** 变更单文本域：每行一律 `kind: summary`，kind 缺省按 feat 处理。 */
  function parseChanges(raw: string) {
    return raw
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l) => {
        const i = l.indexOf(":");
        const kind = i > 0 ? l.slice(0, i).trim() : "feat";
        const summary = i > 0 ? l.slice(i + 1).trim() : l;
        return { kind, summary };
      });
  }

  async function doCreate() {
    if (!canConfig) return;
    const version = nVersion.trim();
    if (!version) {
      setError("版本号必填（形如 2.6.0，全局唯一）");
      return;
    }
    setBusy("create");
    setError("");
    try {
      await createRelease({
        version,
        channel: nChannel,
        notes: nNotes,
        manifest: {},
        sbom: [],
        changes: parseChanges(nChanges),
      });
      setShowNew(false);
      setNVersion("");
      setNNotes("");
      setNChanges("");
      toastMsg(`版本 ${version} 已创建并签名`);
      load();
    } catch (e: any) {
      setError(e?.message || "创建失败");
    } finally {
      setBusy(null);
    }
  }

  async function doPromote(r: ReleaseItem) {
    if (!canConfig) return;
    const nxt = NEXT_CHANNEL[r.channel] || "";
    if (!nxt) {
      toastMsg(`版本 ${r.version} 已在 production 终点，无法继续推进`);
      return;
    }
    setBusy(`pm-${r.id}`);
    try {
      await promoteRelease(r.id);
      toastMsg(`${r.version} 推进到 ${nxt}`);
      load();
    } catch (e: any) {
      toastMsg(`推进失败：${e?.message || "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  async function doRecall(r: ReleaseItem) {
    if (!canConfig) return;
    if (!confirm(`确认召回版本 ${r.version}？`)) return;
    setBusy(`rc-${r.id}`);
    try {
      await recallRelease(r.id);
      toastMsg(`${r.version} 已召回`);
      load();
    } catch (e: any) {
      toastMsg(`召回失败：${e?.message || "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <DashboardShell>
      {toast && (
        <div className="fixed top-4 right-4 z-50 px-4 py-2.5 rounded-xl bg-emerald-500/15 border border-emerald-400/30 text-emerald-200 text-sm shadow-glow">
          {toast}
        </div>
      )}

      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">交付发布管理</h1>
          <p className="text-xs text-gray-500 mt-1">
            Release / Channel / Change / SBOM 摘要 + sha256 签名 · 通道推进与召回（TASK-017 / 80-01·80-02）
          </p>
        </div>
        {canConfig && (
          <button
            onClick={() => setShowNew(true)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-violet-500 to-blue-500 text-white">
            新建版本
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "版本总数", value: stats.total },
          { label: "production 通道", value: stats.prod },
          { label: "签名一致", value: stats.valid },
          { label: "变更单", value: stats.changes },
        ].map((k) => (
          <div key={k.label} className="rounded-2xl bg-white/[0.03] border border-white/5 p-4">
            <div className="text-[11px] text-gray-500">{k.label}</div>
            <div className="text-2xl font-semibold mt-1">{k.value}</div>
          </div>
        ))}
      </div>

      {error && (
        <div className="rounded-xl bg-rose-500/10 border border-rose-400/20 text-rose-300 text-sm p-3 mb-4">{error}</div>
      )}

      {/* 通道筛选 */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {[{ v: "", t: "全部通道" }].concat(CHANNELS.map((c) => ({ v: c, t: c }))).map((c) => (
          <button
            key={c.v}
            onClick={() => setChannel(c.v)}
            className={`px-3 py-1 rounded-lg text-xs border transition ${
              channel === c.v
                ? "bg-violet-500/20 border-violet-400/30 text-violet-200"
                : "bg-white/[0.03] border-white/5 text-gray-400 hover:text-gray-200"
            }`}>
            {c.t}
          </button>
        ))}
      </div>

      {loading && !rows.length ? (
        <div className="text-sm text-gray-500 py-12 text-center">加载 Release…</div>
      ) : rows.length === 0 ? (
        <div className="text-sm text-gray-500 py-12 text-center">
          暂无版本{channel ? `（通道 ${channel}）` : ""}
        </div>
      ) : (
        <div className="space-y-4">
          {rows.map((r) => {
            const nxt = NEXT_CHANNEL[r.channel] || "";
            const badSig = r.signature && !r.signature_valid;
            return (
              <div key={r.id} className="rounded-2xl bg-white/[0.03] border border-white/5 p-5">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold">v{r.version}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-md ${CHANNEL_BADGE[r.channel] || "bg-white/5 text-gray-400"}`}>
                        {r.channel}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/5 text-gray-400">
                        {STATUS_TEXT[r.status] || r.status}
                      </span>
                      <span
                        title={r.signature}
                        className={`text-[10px] px-1.5 py-0.5 rounded-md ${
                          badSig ? "bg-rose-500/15 text-rose-300" : "bg-emerald-500/15 text-emerald-300"
                        }`}>
                        {badSig ? "签名不符（内容被改过）" : r.signature ? "签名一致" : "未签名"}
                      </span>
                    </div>
                    {r.notes && <p className="text-xs text-gray-500 mt-1.5">{r.notes}</p>}
                    <div className="mt-2 text-[11px] text-gray-400 space-y-1">
                      <div>
                        签名 <code className="text-gray-500">{r.signature ? r.signature.slice(0, 24) + "…" : "—"}</code>
                      </div>
                      {r.changes?.length ? (
                        <ul className="space-y-0.5">
                          {r.changes.map((c, i) => (
                            <li key={i}>
                              · <span className="text-gray-500">{c.kind}</span> {c.summary}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <div className="text-gray-600">无变更单</div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {canConfig && (
                      <>
                        <button
                          disabled={!!busy || !nxt}
                          onClick={() => doPromote(r)}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.06] border border-white/10 text-gray-200 disabled:opacity-40">
                          {busy === `pm-${r.id}` ? "推进中…" : nxt ? `推进到 ${nxt}` : "已是终点"}
                        </button>
                        <button
                          disabled={!!busy || r.status !== "promoted"}
                          onClick={() => doRecall(r)}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-500/15 border border-rose-400/20 text-rose-300 disabled:opacity-40">
                          {busy === `rc-${r.id}` ? "召回中…" : "召回"}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 新建版本弹层 */}
      {showNew && canConfig && (
        <div className="fixed inset-0 z-40 bg-black/50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-ink-900 border border-white/10 p-5">
            <div className="text-sm font-semibold mb-4">新建 Release</div>
            <div className="space-y-3">
              <label className="block">
                <span className="text-[11px] text-gray-500">版本号（全局唯一，如 2.6.0）</span>
                <input
                  value={nVersion}
                  onChange={(e) => setNVersion(e.target.value)}
                  placeholder="2.6.0"
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/10 text-sm outline-none focus:border-violet-400/40"
                />
              </label>
              <label className="block">
                <span className="text-[11px] text-gray-500">通道</span>
                <select
                  value={nChannel}
                  onChange={(e) => setNChannel(e.target.value)}
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/10 text-sm outline-none">
                  {CHANNELS.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-[11px] text-gray-500">发布说明</span>
                <textarea
                  value={nNotes}
                  onChange={(e) => setNNotes(e.target.value)}
                  rows={2}
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/10 text-sm outline-none"
                />
              </label>
              <label className="block">
                <span className="text-[11px] text-gray-500">
                  变更单（每行一条，格式 <code>kind: summary</code>，kind 可为
                  feat / fix / config / security / migration，缺省 feat）
                </span>
                <textarea
                  value={nChanges}
                  onChange={(e) => setNChanges(e.target.value)}
                  rows={4}
                  placeholder={"fix: 心跳超时阈值改为 3 个周期\nsecurity: 站点令牌改为 32 字节 urlsafe"}
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/10 text-sm outline-none"
                />
              </label>
              <p className="text-[11px] text-gray-600">
                版本创建时会按 <code>sha256(version|manifest|sbom)</code> 自动签名；
                manifest / sbom 可后续通过 API 回填（本页不提供，避免误改签名）。
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button
                onClick={() => setShowNew(false)}
                className="px-3 py-1.5 rounded-lg text-xs bg-white/[0.06] border border-white/10 text-gray-300">
                取消
              </button>
              <button
                disabled={busy === "create"}
                onClick={doCreate}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-violet-500 to-blue-500 text-white disabled:opacity-50">
                {busy === "create" ? "创建中…" : "创建并签名"}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardShell>
  );
}
