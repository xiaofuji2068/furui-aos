"use client";

import React from "react";

/**
 * 极简 Markdown 渲染器（只覆盖 Agent 报告用到的语法）。
 * 不引第三方库 —— 报告由我们自己生成，语法可控，没必要为此多装一个包。
 * 支持：##/### 标题、**粗体**、`代码`、- 列表、1. 有序列表、> 引用、| 表格、--- 分割线
 */

function inline(text: string, keyPrefix: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  // 先拆 `code`，再拆 **bold**
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  let i = 0;
  for (const p of parts) {
    if (!p) continue;
    const k = `${keyPrefix}-${i++}`;
    if (p.startsWith("`") && p.endsWith("`") && p.length > 2) {
      out.push(
        <code key={k} className="px-1 py-0.5 rounded bg-white/[0.08] text-[12px] text-cyan-300">
          {p.slice(1, -1)}
        </code>,
      );
    } else if (p.startsWith("**") && p.endsWith("**") && p.length > 4) {
      out.push(
        <strong key={k} className="font-semibold text-white">
          {p.slice(2, -2)}
        </strong>,
      );
    } else {
      out.push(<React.Fragment key={k}>{p}</React.Fragment>);
    }
  }
  return out;
}

function splitRow(line: string): string[] {
  return line
    .replace(/^\s*\|/, "")
    .replace(/\|\s*$/, "")
    .split("|")
    .map((c) => c.trim());
}

export default function Markdown({ text }: { text: string }) {
  if (!text) return null;
  const lines = text.split("\n");
  const blocks: React.ReactNode[] = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // 空行
    if (!trimmed) {
      i++;
      continue;
    }

    // 分割线
    if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
      blocks.push(<hr key={`hr-${i}`} className="my-3 border-white/10" />);
      i++;
      continue;
    }

    // 表格：当前行含 | 且下一行是分隔行
    if (trimmed.includes("|") && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1]) && lines[i + 1].includes("-")) {
      const header = splitRow(trimmed);
      i += 2;
      const body: string[][] = [];
      while (i < lines.length && lines[i].trim().includes("|")) {
        body.push(splitRow(lines[i].trim()));
        i++;
      }
      blocks.push(
        <div key={`table-${i}`} className="my-3 overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full text-[13px]">
            <thead className="bg-white/[0.05]">
              <tr>
                {header.map((h, hi) => (
                  <th key={hi} className="px-3 py-2 text-left font-medium text-gray-300 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((row, ri) => (
                <tr key={ri} className="border-t border-white/[0.06]">
                  {row.map((c, ci) => (
                    <td key={ci} className="px-3 py-2 text-gray-300 whitespace-nowrap">
                      {inline(c, `${ri}-${ci}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    // 标题
    const h = trimmed.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      const level = h[1].length;
      const content = inline(h[2], `h${i}`);
      if (level <= 2) {
        blocks.push(
          <h3 key={`h-${i}`} className="text-[15px] font-semibold text-white mt-4 mb-2 first:mt-0">
            {content}
          </h3>,
        );
      } else {
        blocks.push(
          <h4 key={`h-${i}`} className="text-[13.5px] font-semibold text-gray-100 mt-3 mb-1.5 first:mt-0">
            {content}
          </h4>,
        );
      }
      i++;
      continue;
    }

    // 引用
    if (trimmed.startsWith(">")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        items.push(lines[i].trim().replace(/^>\s?/, ""));
        i++;
      }
      blocks.push(
        <blockquote
          key={`q-${i}`}
          className="my-2 pl-3 border-l-2 border-violet-400/50 text-[13px] text-gray-400 leading-relaxed"
        >
          {inline(items.join(" "), `q${i}`)}
        </blockquote>,
      );
      continue;
    }

    // 有序列表
    if (/^\d+[.、)]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+[.、)]\s+/.test(lines[i])) {
        items.push(lines[i].trim().replace(/^\d+[.、)]\s+/, ""));
        i++;
      }
      blocks.push(
        <ol key={`ol-${i}`} className="my-2 space-y-1 list-decimal list-inside text-[13.5px] text-gray-300">
          {items.map((it, k) => (
            <li key={k} className="leading-relaxed">
              {inline(it, `ol${i}-${k}`)}
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    // 无序列表
    if (/^[-*+]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        items.push(lines[i].trim().replace(/^[-*+]\s+/, ""));
        i++;
      }
      blocks.push(
        <ul key={`ul-${i}`} className="my-2 space-y-1 list-disc list-inside text-[13.5px] text-gray-300">
          {items.map((it, k) => (
            <li key={k} className="leading-relaxed">
              {inline(it, `ul${i}-${k}`)}
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    // 普通段落：连续非空行合并
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|[-*+]\s|\d+[.、)]\s|>|\s*\|)/.test(lines[i])) {
      para.push(lines[i].trim());
      i++;
    }
    if (para.length) {
      blocks.push(
        <p key={`p-${i}`} className="my-1.5 text-[13.5px] leading-[1.85] text-gray-300">
          {inline(para.join(" "), `p${i}`)}
        </p>,
      );
    }
  }

  return <div className="text-gray-300">{blocks}</div>;
}
