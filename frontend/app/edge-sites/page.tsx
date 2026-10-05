"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import DashboardShell from "../../components/DashboardShell";
import { useAuth } from "../../components/AuthProvider";
import {
  fetchEdgeSites,
  fetchSiteSync,
  heartbeatEdgeSite,
  registerEdgeSite,
  unregisterEdgeSite,
  type EdgeSiteItem,
  type SiteRegisterResult,
  type SiteSyncTarget,
} from "../../lib/api";

/**
 * 边缘站点管理（TASK-017 / 70-03 Hub-Spoke）。
 *
 * 与 Release 页的分工：
 *   /releases      看「产品版本发到哪条通道、签名对不对」；
 *   本页看「客户现场哪些机在跑、跑的什么版本、要不要升」——两边版本对不上就是待升级。
 *
 * 令牌说明：注册时后端一次性返回明文 token，库里只存 sha256；
 * 本页只负责**展示一次**并提示立即接管，不缓存、不二次回显。
 */

const STATUS_BADGE: Record<string, string> = {
  online: "bg-emerald-500/15 text-emerald-300",
  registered: "bg-amber-500/15 text-amber-300",
  offline: "bg-rose-500/15 text-rose-300",
  syncing: "bg-sky-500/15 text-sky-300",
};

const STATUS_TEXT: Record<string, string> = {
  online: "在线",
  registered: "未上报",
  offline: "失联",
  syncing: "升级中",
};

export default function EdgeSitesPage() {
  const { user } = useAuth();
  const canConfig = !!user?.permissions?.includes("tool:config");

  const [rows, setRows] = useState<EdgeSiteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  // 每站的同步结果（Hub → Spoke 应运行版本）
  const [syncMap, setSyncMap] = useState<Record<string, SiteSyncTarget>>({});

  // 注册弹层 + 一次性令牌
  const [showReg, setShowReg] = useState(false);
  const [rCode, setRCode] = useState("");
  const [rName, setRName] = useState("");
  const [rType, setRType] = useState("edge");
  const [rEndpoint, setREndpoint] = useState("");
  const [oneTimeToken, setOneTimeToken] = useState<{ site: string; token: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetchEdgeSites();
      setRows(r.items || []);
      setError("");
    } catch (e: any) {
      setError(e?.message || "加载站点列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const stats = useMemo(() => {
    const online = rows.filter((r) => r.status === "online").length;
    const pending = rows.filter(
      (r) => (syncMap[r.site_code]?.upgrade_needed ?? (!r.version || !syncMap[r.site_code])),
    ).length;
    return { total: rows.length, online, pending, unknown: rows.length - online };
  }, [rows, syncMap]);

  function toastMsg(t: string) {
    setToast(t);
    setTimeout(() => setToast(""), 3800);
  }

  async function doRegister() {
    if (!canConfig) return;
    const code = rCode.trim();
    if (!code) {
      setError("site_code 必填（全局唯一，如 EDGE-HANGZHOU-01）");
      return;
    }
    setBusy("register");
    setError("");
    try {
      const r = await registerEdgeSite({
        site_code: code,
        name: rName.trim() || code,
        site_type: rType,
        endpoint: rEndpoint.trim(),
      });
      // 明文令牌只出现这一次，关掉弹层就没了（库里只有 sha256）
      setOneTimeToken({ site: r.site_code, token: r.token });
      setShowReg(false);
      setRCode("");
      setRName("");
      setREndpoint("");
      toastMsg(`站点 ${r.site_code} 已注册`);
      load();
    } catch (e: any) {
      setError(e?.message || "注册失败");
    } finally {
      setBusy(null);
    }
  }

  async function doSync(code: string) {
    setBusy(`sync-${code}`);
    try {
      const s = await fetchSiteSync(code);
      setSyncMap((m) => ({ ...m, [code]: s }));
      toastMsg(
        s.upgrade_needed
          ? `${code}：${s.from_version || "未知"} → ${s.to_version}，需升级`
          : `${code}：已是 ${s.to_version || "—"}`,
      );
    } catch (e: any) {
      toastMsg(`查询同步失败：${e?.message || "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  async function doHeartbeat(code: string) {
    setBusy(`hb-${code}`);
    try {
      const s = await heartbeatEdgeSite(code, { status: "healthy" });
      toastMsg(`${s.site_code} 心跳已上报 · v${s.version || "—"}`);
      load();
    } catch (e: any) {
      toastMsg(`心跳失败：${e?.message || "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  async function doUnregister(code: string) {
    if (!canConfig) return;
    if (!confirm(`确认注销站点 ${code}？（该站点的注册令牌随即作废）`)) return;
    setBusy(`del-${code}`);
    try {
      await unregisterEdgeSite(code);
      setSyncMap((m) => {
        const n = { ...m };
        delete n[code];
        return n;
      });
      toastMsg(`${code} 已注销`);
      load();
    } catch (e: any) {
      toastMsg(`注销失败：${e?.message || "未知错误"}`);
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

      {/* 一次性令牌弹层：提醒立即接管，不缓存 */}
      {oneTimeToken && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-ink-900 border border-amber-400/30 p-5">
            <div className="text-sm font-semibold text-amber-200">站点注册令牌（仅此一次）</div>
            <p className="text-[11px] text-gray-400 mt-1">
              站点 <code>{oneTimeToken.site}</code> 的明文令牌如下。服务端只保存 sha256，
              关闭本弹层后无法再次取回，请立即落到你自己的密钥体系。
            </p>
            <div className="mt-3 flex items-center gap-2">
              <code className="flex-1 break-all px-3 py-2 rounded-lg bg-white/[0.04] border border-white/10 text-xs text-emerald-200">
                {oneTimeToken.token}
              </code>
              <button
                onClick={() => navigator.clipboard?.writeText(oneTimeToken.token)}
                className="px-3 py-2 rounded-lg text-xs bg-white/[0.06] border border-white/10 text-gray-200">
                复制
              </button>
            </div>
            <div className="flex justify-end mt-5">
              <button
                onClick={() => setOneTimeToken(null)}
                className="px-3 py-1.5 rounded-lg text-xs bg-white/[0.06] border border-white/10 text-gray-300">
                我已保存，关闭
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">边缘站点（Hub-Spoke）</h1>
          <p className="text-xs text-gray-500 mt-1">
            现场站点注册 · 心跳续约 · 应运行版本下发（TASK-017 / 70-03）
          </p>
        </div>
        {canConfig && (
          <button
            onClick={() => setShowReg(true)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-violet-500 to-blue-500 text-white">
            注册站点
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "站点总数", value: stats.total },
          { label: "在线", value: stats.online },
          { label: "待升级 / 未上报", value: stats.pending },
          { label: "非在线", value: stats.unknown },
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

      {loading && !rows.length ? (
        <div className="text-sm text-gray-500 py-12 text-center">加载站点…</div>
      ) : rows.length === 0 ? (
        <div className="text-sm text-gray-500 py-12 text-center">暂无边缘站点，点右上角「注册站点」接入第一台现场机</div>
      ) : (
        <div className="space-y-4">
          {rows.map((s) => {
            const syn = syncMap[s.site_code];
            const needUpgrade = syn?.upgrade_needed ?? false;
            const from = syn?.from_version ?? s.version;
            const to = syn?.to_version ?? "";
            return (
              <div
                key={s.site_code}
                className={`rounded-2xl border p-5 ${
                  needUpgrade ? "bg-amber-500/[0.06] border-amber-400/25" : "bg-white/[0.03] border-white/5"
                }`}
              >
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold">{s.site_code}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-md ${STATUS_BADGE[s.status] || "bg-white/5 text-gray-400"}`}>
                        {STATUS_TEXT[s.status] || s.status}
                      </span>
                      {s.name && s.name !== s.site_code && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/5 text-gray-400">{s.name}</span>
                      )}
                      {needUpgrade && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-amber-500/20 text-amber-200">
                          待升级 {from || "?"} → {to}
                        </span>
                      )}
                    </div>
                    <div className="mt-2 text-[11px] text-gray-400 space-y-1">
                      <div>类型：{s.site_type || "edge"} · 端点：{s.endpoint || "—"}</div>
                      <div>
                        已运行版本：<span className="text-gray-300">{s.version || "—"}</span>
                        {to && to !== s.version && (
                          <>
                            {" → 应运行："}
                            <span className="text-amber-300">{to}</span>
                          </>
                        )}
                      </div>
                      <div>最近心跳：{s.last_heartbeat_at ? new Date(s.last_heartbeat_at).toLocaleString() : "从未上报"}</div>
                      {Object.keys(s.metadata || {}).length > 0 && (
                        <div>运行时：{JSON.stringify(s.metadata)}</div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      disabled={!!busy}
                      onClick={() => doSync(s.site_code)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.06] border border-white/10 text-gray-200 disabled:opacity-40">
                      {busy === `sync-${s.site_code}` ? "查询中…" : "查应运行版本"}
                    </button>
                    <button
                      disabled={!!busy}
                      onClick={() => doHeartbeat(s.site_code)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.06] border border-white/10 text-gray-200 disabled:opacity-40">
                      {busy === `hb-${s.site_code}` ? "上报中…" : "模拟心跳上报"}
                    </button>
                    {canConfig && (
                      <button
                        disabled={!!busy}
                        onClick={() => doUnregister(s.site_code)}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-500/15 border border-rose-400/20 text-rose-300 disabled:opacity-40">
                        {busy === `del-${s.site_code}` ? "注销中…" : "注销"}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 注册弹层 */}
      {showReg && canConfig && (
        <div className="fixed inset-0 z-40 bg-black/50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-ink-900 border border-white/10 p-5">
            <div className="text-sm font-semibold mb-4">注册边缘站点</div>
            <div className="space-y-3">
              <label className="block">
                <span className="text-[11px] text-gray-500">站点编码（唯一，如 EDGE-HANGZHOU-01）</span>
                <input
                  value={rCode}
                  onChange={(e) => setRCode(e.target.value)}
                  placeholder="EDGE-HANGZHOU-01"
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/10 text-sm outline-none focus:border-violet-400/40"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-[11px] text-gray-500">名称</span>
                  <input
                    value={rName}
                    onChange={(e) => setRName(e.target.value)}
                    placeholder="杭州现场机"
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/10 text-sm outline-none"
                  />
                </label>
                <label className="block">
                  <span className="text-[11px] text-gray-500">类型</span>
                  <input
                    value={rType}
                    onChange={(e) => setRType(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/10 text-sm outline-none"
                  />
                </label>
              </div>
              <label className="block">
                <span className="text-[11px] text-gray-500">端点（可选）</span>
                <input
                  value={rEndpoint}
                  onChange={(e) => setREndpoint(e.target.value)}
                  placeholder="http://10.20.3.11:8000"
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/10 text-sm outline-none"
                />
              </label>
              <p className="text-[11px] text-gray-600">
                注册后服务端返回一次性明文令牌（库里只存 sha256）。新站点默认挂当前最新版本，
                之后由「查应运行版本」下发目标版本。
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button
                onClick={() => setShowReg(false)}
                className="px-3 py-1.5 rounded-lg text-xs bg-white/[0.06] border border-white/10 text-gray-300">
                取消
              </button>
              <button
                disabled={busy === "register"}
                onClick={doRegister}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-violet-500 to-blue-500 text-white disabled:opacity-50">
                {busy === "register" ? "注册中…" : "注册并取令牌"}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardShell>
  );
}
