"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import DashboardShell from "../../../components/DashboardShell";
import {
  authHeaders,
  fetchDataAssets,
  fetchOntologySnapshot,
  fetchPageByCode,
  fetchTasks,
  type AppPage,
  type PageWidget,
} from "../../../lib/api";

async function fetchOverviewKpis() {
  try {
    const res = await fetch("/api/backend/overview", { cache: "no-store", headers: authHeaders() });
    if (!res.ok) return [];
    const json = await res.json();
    const d = json?.data ?? json ?? {};
    // overview 的 kpis 为 { key: {label,value,delta} } 对象 → 转数组
    const kpis = d?.kpis ?? {};
    return Object.entries(kpis).map(([k, v]: [string, any]) => ({
      label: v?.label || k,
      value: v?.value ?? "",
      unit: v?.unit || "",
      delta: v?.delta,
    }));
  } catch {
    return [];
  }
}

/** 单个 Widget 渲染：运行时读取数据源并展示（40-02） */
function WidgetView({ w }: { w: PageWidget }) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let dead = false;
    (async () => {
      try {
        if (w.widget === "stat_cards") {
          setData({ kpis: await fetchOverviewKpis() });
        } else if (w.widget === "object_list") {
          const s = await fetchOntologySnapshot();
          const want = (w.params?.type as string) || "All";
          const nodes = want === "All" ? s.nodes : s.nodes.filter((n) => n.type === want);
          setData({ nodes });
        } else if (w.widget === "data_assets") {
          const r = await fetchDataAssets();
          setData({ items: r.items });
        } else if (w.widget === "tasks") {
          const limit = Number(w.params?.limit ?? 8) || 8;
          const r = await fetchTasks(undefined, limit);
          setData({ items: r.items });
        } else {
          setData({ note: (w.params?.content as string) || "" });
        }
      } catch (e: any) {
        if (!dead) setError(e?.message || "组件加载失败");
      }
    })();
    return () => { dead = true; };
  }, [w]);

  const card = "rounded-2xl bg-white/[0.03] border border-white/10 p-5";
  const th = "text-left text-[11px] text-gray-500 font-medium py-2 px-3";
  const td = "text-sm text-gray-200 py-2 px-3 border-t border-white/5";

  if (error) return <div className={`${card} text-red-300 text-sm`}>{error}</div>;

  if (w.widget === "stat_cards" && data?.kpis) {
    return (
      <div className="rounded-2xl bg-white/[0.03] border border-white/10 p-5">
        <div className="text-sm font-semibold text-white mb-4">{w.title || "核心指标"}</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {(data.kpis as any[]).map((k, i) => (
            <div key={i} className="rounded-xl bg-white/[0.03] border border-white/10 p-4">
              <div className="text-[11px] text-gray-500">{k.label}</div>
              <div className="text-xl font-semibold text-white mt-1">
                {k.value} <span className="text-xs text-gray-400 font-normal">{k.unit}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (w.widget === "object_list" && data?.nodes) {
    const nodes = data.nodes as { type: string; id: string }[];
    return (
      <div className={card}>
        <div className="text-sm font-semibold text-white mb-3">{w.title || "对象列表"}</div>
        {nodes.length === 0
          ? <div className="text-xs text-gray-500 py-4">暂无对象</div>
          : (
            <table className="w-full">
              <thead>
                <tr><th className={th}>类型</th><th className={th}>对象</th><th className={th}>操作</th></tr>
              </thead>
              <tbody>
                {nodes.slice(0, 30).map((n, i) => (
                  <tr key={i}>
                    <td className={td}>{n.type}</td>
                    <td className={td}>{n.id}</td>
                    <td className={td}>
                      <Link href={`/objects/${encodeURIComponent(n.type)}/${encodeURIComponent(n.id)}`}
                        className="text-violet-300 hover:text-violet-200 text-xs">查看详情 →</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    );
  }

  if (w.widget === "data_assets" && data?.items) {
    const items = data.items as any[];
    return (
      <div className={card}>
        <div className="text-sm font-semibold text-white mb-3">{w.title || "数据资产"}</div>
        {items.length === 0
          ? <div className="text-xs text-gray-500 py-4">暂无数据资产</div>
          : (
            <table className="w-full">
              <thead>
                <tr><th className={th}>名称</th><th className={th}>实体</th><th className={th}>行数</th><th className={th}>状态</th></tr>
              </thead>
              <tbody>
                {items.slice(0, 20).map((it) => (
                  <tr key={it.id}>
                    <td className={td}>{it.name}</td>
                    <td className={td}>{it.entity || "—"}</td>
                    <td className={td}>{it.row_count ?? "—"}</td>
                    <td className={td}>{it.status || it.source_status || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    );
  }

  if (w.widget === "tasks" && data?.items) {
    const items = data.items as any[];
    return (
      <div className={card}>
        <div className="text-sm font-semibold text-white mb-3">{w.title || "最近任务"}</div>
        {items.length === 0
          ? <div className="text-xs text-gray-500 py-4">暂无任务</div>
          : (
            <table className="w-full">
              <thead>
                <tr><th className={th}>任务</th><th className={th}>状态</th><th className={th}>Agent</th></tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.id}>
                    <td className={td}>{it.title}</td>
                    <td className={td}>{it.status}</td>
                    <td className={td}>{it.agent || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    );
  }

  if (w.widget === "text_note") {
    return (
      <div className={`${card} text-sm text-gray-300 leading-relaxed`}>
        {(w.params?.content as string) || w.title || ""}
      </div>
    );
  }

  return <div className={`${card} text-sm text-gray-400`}>组件加载中…</div>;
}

export default function PageRuntime({ params }: { params: { code: string } }) {
  const { code } = params;
  const [page, setPage] = useState<AppPage | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPageByCode(code)
      .then((p) => { setPage(p); setError(""); })
      .catch((e: any) => setError(e?.message || "页面不存在或未发布"))
      .finally(() => setLoading(false));
  }, [code]);

  if (loading) return <DashboardShell><div className="text-sm text-gray-400 py-10">加载中…</div></DashboardShell>;
  if (error || !page) {
    return (
      <DashboardShell>
        <div className="rounded-2xl bg-white/[0.03] border border-white/10 p-8 text-center space-y-3">
          <div className="text-lg text-white font-semibold">页面不可用</div>
          <div className="text-sm text-gray-400">{error || "页面不存在"}</div>
          <Link href="/pages" className="inline-block px-4 py-2 rounded-xl bg-white/[0.06] text-gray-300 text-sm hover:bg-white/[0.1]">返回低代码构建</Link>
        </div>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white">{page.title}</h1>
            {page.description && <p className="text-sm text-gray-400 mt-1">{page.description}</p>}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-gray-500">v{page.version}</span>
            <span className="text-[11px] px-2 py-0.5 rounded-md bg-white/[0.06] text-gray-400">{page.status === "published" ? "已发布" : "草稿预览"}</span>
            <Link href="/pages" className="px-3 py-1.5 rounded-lg bg-white/[0.06] text-gray-300 text-xs hover:bg-white/[0.1]">构建器</Link>
          </div>
        </div>
        {page.layout.length === 0
          ? <div className="rounded-2xl bg-white/[0.03] border border-dashed border-white/10 p-8 text-center text-sm text-gray-500">页面暂无组件，请到构建器添加</div>
          : (
            <div className="grid grid-cols-1 gap-4">
              {page.layout.map((w, i) => (
                <WidgetView key={i} w={w} />
              ))}
            </div>
          )}
      </div>
    </DashboardShell>
  );
}
