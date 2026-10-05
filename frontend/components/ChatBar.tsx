"use client";

import { useEffect, useRef, useState } from "react";

export default function ChatBar({ chat, onSend, multiAgent, onToggleMulti }: {
  chat: { role: string; agent?: string; avatar?: string; content: string }[];
  onSend: (m: string) => void;
  multiAgent?: boolean;
  onToggleMulti?: (v: boolean) => void;
}) {
  const [input, setInput] = useState("");
  const [expanded, setExpanded] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [chat, expanded]);

  const send = () => {
    const t = input.trim();
    if (!t) return;
    onSend(t);
    setInput("");
    setExpanded(true);
  };

  return (
    <footer className={`${expanded ? "h-[320px]" : "h-[110px]"} border-t border-white/5 bg-ink-900/80 backdrop-blur-xl transition-all flex flex-col`}>
      {expanded && (
        <div ref={scroller} className="flex-1 overflow-auto px-6 py-3 space-y-3">
          {chat.filter(c => c.content).map((c, i) => (
            <div key={i} className={`flex gap-3 ${c.role === "user" ? "justify-end" : ""}`}>
              {c.role === "ai" && (
                <div className="w-8 h-8 shrink-0 rounded-full bg-gradient-to-br from-violet-500 to-blue-500 flex items-center justify-center text-sm shadow-glow">
                  {c.avatar || "🤖"}
                </div>
              )}
              <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap
                ${c.role === "user"
                  ? "bg-gradient-to-br from-violet-500/30 to-blue-500/30 border border-violet-400/30"
                  : "glass-strong border border-white/5"}`}>
                {c.agent && c.role === "ai" && (
                  <div className="text-[10px] text-violet-300 mb-1">@ {c.agent}</div>
                )}
                <div dangerouslySetInnerHTML={{ __html: mdLite(c.content) }} />
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="px-6 py-4">
        <div className="flex items-center gap-3 px-4 py-2 rounded-2xl glass-strong border border-white/5">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-500 to-pink-500 flex items-center justify-center text-sm shadow-glow">
            {multiAgent ? "🩺" : "📊"}
          </div>
          <div className="flex-1">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") send(); }}
              onFocus={() => setExpanded(true)}
              placeholder={multiAgent
                ? "多方会诊模式：把复杂问题交给多位专家协同诊断，回车发起…"
                : "你好，我是企业智能助手。请输入你要分析的内容，回车发送…"}
              className="w-full bg-transparent outline-none text-sm placeholder:text-gray-500"
            />
            <div className="flex items-center gap-2 mt-1.5">
              <button
                onClick={() => onToggleMulti?.(!multiAgent)}
                className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                  multiAgent
                    ? "bg-gradient-to-br from-amber-500/30 to-orange-500/30 border-amber-400/40 text-amber-200"
                    : "bg-white/[0.04] hover:bg-white/[0.08] border-white/5 text-gray-400"
                }`}
                title="切换多方会诊 / 单 Agent 对话"
              >
                {multiAgent ? "🩺 多方会诊 · 开" : "🩺 多方会诊 · 关"}
              </button>
              {!multiAgent && ["分析销售数据", "查企业知识", "发现经营问题", "生成报告", "创建 AI 员工"].map(t => (
                <button key={t} onClick={() => setInput(t)} className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.04] hover:bg-white/[0.08] border border-white/5">
                  {t}
                </button>
              ))}
            </div>
          </div>
          <button onClick={send} className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-blue-500 text-white flex items-center justify-center shadow-glow">➤</button>
        </div>
      </div>
    </footer>
  );
}

function mdLite(s: string) {
  return s
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, '<b class="text-violet-300">$1</b>')
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-white/10 text-violet-200 text-xs">$1</code>')
    .replace(/^>\s(.+)$/gm, '<blockquote class="border-l-2 border-amber-400 pl-2 text-amber-200 my-1">$1</blockquote>');
}
