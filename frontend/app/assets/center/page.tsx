"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import DashboardShell from "../../../components/DashboardShell";
import { useAuth } from "../../../components/AuthProvider";
import {
  fetchAssetBundles,
  fetchInstalledNav,
  installAssetBundle,
  rederiveAsset,
  uninstallAsset,
  type AssetBundleItem,
  type InstalledNavItem,
} from "../../../lib/api";

/** 平台资产中心（TASK-016）：系统 Bundle 目录 → 租户派生安装 → 动态导航。 */
export default function AssetCenterPage() {
  const { user } = useAuth();
  const canConfig = !!user?.permissions?.includes("tool:config");

  const [bundles, setBundles] = useState<AssetBundleItem[]>([]);
  const [navs, setNavs] = useState<InstalledNavItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      fetchAssetBundles().catch(() => ({ items: [] })),
      fetchInstalledNav().catch(() => ({ items: [] })),
    ]).then(([b, n]) => {
      setBundles(b.items || []);
      setNavs(n.items || []);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const stats = useMemo(() => {
    const installed = bundles.filter((b) => b.installed).length;
    const published = bundles.filter((b) => b.status === "published").length;
    const pages = bundles.reduce((s, b) => s + (b.page_codes?.length || 0), 0);
    return { total: bundles.length, installed, published, pages };
  }, [bundles]);

  function toastMsg(t: string) {
    setToast(t);
    setTimeout(() => setToast(""), 3500);
  }

  async function doInstall(b: AssetBundleItem) {
    if (!canConfig) return;
    setBusy(`in-${b.id}`);
    try {
      const r = await installAssetBundle(b.id);
      const pages = r.derived_pages.length;
      const graphs = r.derived_graphs.length;
      toastMsg(
        `${r.created ? "安装完成" : "已安装（补齐派生）"}：派生 ${pages} 页 + ${graphs} 图 · v${r.bundle.version}`,
      );
      load();
    } catch (e: any) {
      toastMsg(`安装失败：${e?.message || "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  async function doRederive(b: AssetBundleItem) {
    if (!canConfig || !b.installation) return;
    setBusy(`rd-${b.id}`);
    try {
      const r = await rederiveAsset(b.installation.id);
      toastMsg(
        `重新派生完成：补齐 ${r.added?.pages?.length || 0} 页 + ${r.added?.graphs?.length || 0} 图`,
      );
      load();
    } catch (e: any) {
      toastMsg(`重新派生失败：${e?.message || "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  async function doUninstall(b: AssetBundleItem) {
    if (!canConfig || !b.installation) return;
    if (!confirm(`确认卸载「${b.name}」？将删除本租户的派生页面与决策图。`)) return;
    setBusy(`un-${b.id}`);
    try {
      await uninstallAsset(b.installation.id);
      toastMsg("已卸载并清理派生资产");
      load();
    } catch (e: any) {
      toastMsg(`卸载失败：${e?.message || "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <DashboardShell>
      <div>
        <div className="mb-6">
          <h1 className="text-xl font-semibold">平台资产中心</h1>
          <p className="text-xs text-gray-500 mt-1">系统 Bundle 目录 · 租户派生安装 · 动态导航（TASK-016）</p>
        </div>

        {toast && (
        <div className="fixed top-4 right-4 z-50 px-4 py-2.5 rounded-xl bg-emerald-500/15 border border-emerald-400/30 text-emerald-200 text-sm shadow-glow">
          {toast}
        </div>
      )}

      {/* 统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Bundle 总数", value: stats.total },
          { label: "已发布", value: stats.published },
          { label: "本租户已装", value: stats.installed },
          { label: "派生页面", value: stats.pages },
        ].map((k) => (
          <div key={k.label} className="rounded-2xl bg-white/[0.03] border border-white/5 p-4">
            <div className="text-[11px] text-gray-500">{k.label}</div>
            <div className="text-2xl font-semibold mt-1">{k.value}</div>
          </div>
        ))}
      </div>

      {/* 动态导航（已安装入口） */}
      {navs.length > 0 && (
        <div className="mb-6 rounded-2xl bg-white/[0.03] border border-white/5 p-4">
          <div className="text-[11px] text-gray-500 mb-3">已安装资产入口（动态导航）</div>
          <div className="flex flex-wrap gap-3">
            {navs.map((n) => (
              <Link key={n.bundle} href={n.href}
                className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.04] border border-white/5 hover:border-violet-400/30 text-sm text-gray-200">
                <span>{n.icon || "📦"}</span>
                <span>{n.label}</span>
                <span className="text-[10px] text-gray-500">{n.bundle}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {error && <div className="rounded-xl bg-rose-500/10 border border-rose-400/20 text-rose-300 text-sm p-3 mb-4">{error}</div>}

      {loading && !bundles.length ? (
        <div className="text-sm text-gray-500 py-12 text-center">加载资产目录…</div>
      ) : (
        <div className="space-y-4">
          {bundles.map((b) => (
            <div key={b.id} className="rounded-2xl bg-white/[0.03] border border-white/5 p-5">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold">{b.name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/5 text-gray-400">{b.code}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-md ${
                      b.status === "published" ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
                    }`}>
                      {b.status === "published" ? "已发布" : "草稿"}
                    </span>
                    {b.installed && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-violet-500/20 text-violet-300">
                        本租户已装 · v{b.installation?.bundle_version}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1.5">{b.description}</p>
                  <div className="flex flex-wrap gap-4 mt-2 text-[11px] text-gray-400">
                    <span>页面：{b.page_codes?.length || 0} 个（{b.page_codes?.join("、") || "—"}）</span>
                    <span>决策图：{b.graph_codes?.length || 0} 个（{b.graph_codes?.join("、") || "—"}）</span>
                    {b.nav_entry?.label && <span>导航：{b.nav_entry.label}</span>}
                  </div>
                  {b.installation && (
                    <div className="mt-2 text-[11px] text-gray-500">
                      已派生：{b.installation.derived_pages.length} 页 / {b.installation.derived_graphs.length} 图 ·
                      安装于 {b.installation.installed_at ? new Date(b.installation.installed_at).toLocaleString() : "—"}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {!b.installed ? (
                    canConfig && b.status === "published" ? (
                      <button
                        disabled={busy === `in-${b.id}`}
                        onClick={() => doInstall(b)}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-violet-500 to-blue-500 text-white disabled:opacity-50">
                        {busy === `in-${b.id}` ? "安装中…" : "安装"}
                      </button>
                    ) : (
                      <span className="text-[11px] text-gray-600">{canConfig ? "未发布" : "无权限"}</span>
                    )
                  ) : (
                    canConfig && (
                      <>
                        <button
                          disabled={busy === `rd-${b.id}`}
                          onClick={() => doRederive(b)}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.06] border border-white/10 text-gray-200 disabled:opacity-50">
                          {busy === `rd-${b.id}` ? "补齐中…" : "重新派生"}
                        </button>
                        <button
                          disabled={busy === `un-${b.id}`}
                          onClick={() => doUninstall(b)}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-500/15 border border-rose-400/20 text-rose-300 disabled:opacity-50">
                          {busy === `un-${b.id}` ? "卸载中…" : "卸载"}
                        </button>
                      </>
                    )
                  )}
                </div>
              </div>
            </div>
          ))}
          {!bundles.length && !loading && (
            <div className="text-sm text-gray-500 py-12 text-center">资产目录为空</div>
          )}
        </div>
      )}
      </div>
    </DashboardShell>
  );
}
