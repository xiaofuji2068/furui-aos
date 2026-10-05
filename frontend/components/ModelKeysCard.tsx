"use client";

import { useEffect, useState } from "react";
import { authHeaders } from "../lib/api";

const API = "/api/backend";

type Provider = {
  id: string;
  label: string;
  model_name: string;
  base_url: string;
  has_key: boolean;
  active: boolean;
};

type KeysState = {
  active: string;
  providers: Provider[];
  llm_enabled: boolean;
  active_model: string;
  embedding: { model: string; has_key: boolean; enabled: boolean };
  note?: string;
};

type Msg = { ok: boolean; text: string };

function Badge({ tone, text }: { tone: "emerald" | "amber" | "gray"; text: string }) {
  const cls = tone === "emerald"
    ? "bg-emerald-500/15 text-emerald-300"
    : tone === "amber"
      ? "bg-amber-500/15 text-amber-300"
      : "bg-gray-500/15 text-gray-400";
  return <span className={`text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap ${cls}`}>{text}</span>;
}

export default function ModelKeysCard() {
  const [keys, setKeys] = useState<KeysState | null>(null);
  const [inputs, setInputs] = useState<Record<string, string>>({});       // provider -> key
  const [customUrl, setCustomUrl] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<Msg | null>(null);

  function load() {
    fetch(`${API}/admin/model/keys`, { headers: authHeaders() })
      .then(r => r.json())
      .then(d => setKeys(d?.data ?? d))
      .catch(() => setMsg({ ok: false, text: "读取配置状态失败" }));
  }
  useEffect(() => { load(); }, []);

  async function save(provider: Provider, setActive: boolean) {
    const key = (inputs[provider.id] || "").trim();
    const body: Record<string, unknown> = { provider: provider.id, api_key: key, set_active: setActive };
    if (provider.id === "custom") {
      if (customUrl.trim()) body.custom_base_url = customUrl.trim();
      if (customModel.trim()) body.custom_model_name = customModel.trim();
    }
    setBusy(provider.id + (setActive ? "|act" : ""));
    setMsg(null);
    try {
      const r = await fetch(`${API}/admin/model/keys`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(body),
      });
      const d = await r.json();
      const result = d?.data ?? d;
      if (result.ok) {
        const what = setActive ? "已保存并设为当前对话模型" : "已保存";
        setMsg({ ok: true, text: `✓ ${provider.label}：${what}，立即生效` });
        setInputs(v => ({ ...v, [provider.id]: "" }));
        setKeys(result);
      } else {
        setMsg({ ok: false, text: result.detail || d?.message || "保存失败" });
      }
    } catch {
      setMsg({ ok: false, text: "保存请求失败，请确认后端已启动" });
    } finally {
      setBusy(null);
    }
  }

  async function test(provider: Provider) {
    const apiKey = (inputs[provider.id] || "").trim();
    setBusy(provider.id + "|test");
    setMsg(null);
    try {
      const r = await fetch(`${API}/admin/model/keys/test`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ provider: provider.id, api_key: apiKey }),
      });
      const d = await r.json();
      const result = d?.data ?? d;
      if (result.ok) {
        setMsg({ ok: true, text: `✓ ${provider.label} 连通正常（HTTP ${result.status}）` });
      } else {
        setMsg({ ok: false, text: `✗ ${provider.label}：${result.error || d?.message || `HTTP ${result.status}`}` });
      }
    } catch {
      setMsg({ ok: false, text: "测试请求失败，请确认后端已启动" });
    } finally {
      setBusy(null);
    }
  }

  const embedding: Provider = {
    id: "dashscope",
    label: "DashScope 语义模型（RAG）",
    model_name: keys?.embedding?.model || "text-embedding-v3",
    base_url: "embedding",
    has_key: !!keys?.embedding?.has_key,
    active: false,
  };

  // 首屏 keys 为 null（数据未加载完），先渲染占位，避免访问 keys.embedding.model 时空指针导致整页崩溃
  if (!keys) {
    return (
      <div className="glass-strong rounded-2xl border border-white/5 p-5 mt-5">
        <div className="h-40 rounded-2xl bg-white/[0.03] animate-pulse2" />
      </div>
    );
  }

  return (
    <div className="glass-strong rounded-2xl border border-white/5 p-5 mt-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <div className="text-sm font-semibold text-gray-200">API Key 配置（对话模型可选多家，单选启用）</div>
        <div className="flex gap-2 flex-wrap">
          <Badge tone={keys?.llm_enabled ? "emerald" : "amber"} text={keys?.llm_enabled ? `当前对话：${keys.active_model}` : "对话模型未启用（Mock）"} />
          <Badge tone={keys?.embedding.enabled ? "emerald" : "amber"} text={keys?.embedding.enabled ? "语义检索已启用" : "语义检索降级（本地哈希）"} />
        </div>
      </div>
      <p className="text-xs text-gray-500 mb-4">{keys?.note || "密钥只写不读；保存后立即生效，无需重启"}</p>

      <div className="space-y-3">
        {(keys?.providers || []).map(p => (
          <div key={p.id} className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
              <div>
                <span className="text-sm font-medium text-gray-200">{p.label}</span>
                <span className="text-xs text-gray-500 ml-2">{p.model_name}</span>
                <div className="text-[11px] text-gray-600 mt-0.5">{p.base_url}</div>
              </div>
              <div className="flex gap-2">
                {p.active
                  ? <Badge tone="emerald" text="当前对话模型" />
                  : <Badge tone={p.has_key ? "emerald" : "amber"} text={p.has_key ? "已配置" : "未配置"} />}
              </div>
            </div>

            {p.id === "custom" && (
              <div className="grid grid-cols-2 gap-2 mb-2">
                <input
                  value={customUrl}
                  onChange={e => setCustomUrl(e.target.value)}
                  placeholder="Base URL（如 https://your-model.example.com/v1）"
                  className="rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm outline-none focus:border-violet-400/40 placeholder:text-gray-600"
                />
                <input
                  value={customModel}
                  onChange={e => setCustomModel(e.target.value)}
                  placeholder="模型名（如 your-model-name）"
                  className="rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm outline-none focus:border-violet-400/40 placeholder:text-gray-600"
                />
              </div>
            )}

            <div className="flex gap-2 flex-wrap">
              <input
                type="password"
                value={inputs[p.id] || ""}
                onChange={e => setInputs(v => ({ ...v, [p.id]: e.target.value }))}
                placeholder={p.has_key ? "已配置 · 输入新 Key 可更换" : "sk-…（留空保存不覆盖）"}
                autoComplete="off"
                className="flex-1 min-w-[180px] rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm outline-none focus:border-violet-400/40 placeholder:text-gray-600"
              />
              <button
                disabled={busy === p.id + "|test"}
                onClick={() => test(p)}
                className="text-xs px-3.5 py-2 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 disabled:opacity-50"
              >
                {busy === p.id + "|test" ? "测试中…" : "测试连通性"}
              </button>
              <button
                disabled={busy === p.id || busy === p.id + "|act"}
                onClick={() => save(p, false)}
                className="text-xs px-3.5 py-2 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 disabled:opacity-50"
              >
                {busy === p.id ? "保存中…" : "保存 Key"}
              </button>
              {!p.active && (
                <button
                  disabled={busy === p.id + "|act"}
                  onClick={() => save(p, true)}
                  className="text-xs px-3.5 py-2 rounded-lg bg-violet-500/20 text-violet-200 hover:bg-violet-500/30 border border-violet-400/20 disabled:opacity-50"
                >
                  {busy === p.id + "|act" ? "切换中…" : "设为当前对话模型"}
                </button>
              )}
            </div>
            {p.has_key && !p.active && <div className="text-[11px] text-gray-600 mt-2">已配置 Key · 点「设为当前对话模型」启用</div>}
          </div>
        ))}

        {/* Embedding 独立行 */}
        <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
            <div>
              <span className="text-sm font-medium text-gray-200">{embedding.label}</span>
              <span className="text-xs text-gray-500 ml-2">{embedding.model_name}</span>
            </div>
            <Badge tone={embedding.has_key ? "emerald" : "amber"} text={embedding.has_key ? "已配置" : "未配置（本地哈希兜底）"} />
          </div>
          <div className="flex gap-2 flex-wrap">
            <input
              type="password"
              value={inputs.dashscope || ""}
              onChange={e => setInputs(v => ({ ...v, dashscope: e.target.value }))}
              placeholder={embedding.has_key ? "已配置 · 输入新 Key 可更换" : "sk-…（留空保存不覆盖）"}
              autoComplete="off"
              className="flex-1 min-w-[180px] rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm outline-none focus:border-violet-400/40 placeholder:text-gray-600"
            />
            <button
              disabled={busy === "dashscope|test"}
              onClick={() => test(embedding)}
              className="text-xs px-3.5 py-2 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 disabled:opacity-50"
            >
              {busy === "dashscope|test" ? "测试中…" : "测试连通性"}
            </button>
            <button
              disabled={busy === "dashscope"}
              onClick={() => save(embedding, false)}
              className="text-xs px-3.5 py-2 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 disabled:opacity-50"
            >
              {busy === "dashscope" ? "保存中…" : "保存 Key"}
            </button>
          </div>
        </div>
      </div>

      {msg && (
        <div className={`mt-4 text-xs ${msg.ok ? "text-emerald-300" : "text-rose-300"}`}>{msg.text}</div>
      )}
    </div>
  );
}
