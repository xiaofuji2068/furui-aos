"use client";

/**
 * 自绘 SVG 图表组件 — 不引第三方库，匹配项目风格。
 * - BarChart:   柱状图
 * - LineChart:  折线图
 * - DonutChart: 环形图
 */

type BarDatum = { label: string; value: number };
type LineDatum = { label: string; value: number };

export function BarChart({ data, height = 160, color = "#60a5fa" }: { data: BarDatum[]; height?: number; color?: string }) {
  const w = 100;
  const h = height;
  const max = Math.max(...data.map(d => d.value), 1);
  const padX = 6, padY = 12;
  const bw = (w - padX * 2) / data.length - 4;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`bar-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.9" />
          <stop offset="100%" stopColor={color} stopOpacity="0.3" />
        </linearGradient>
      </defs>
      {data.map((d, i) => {
        const x = padX + i * ((w - padX * 2) / data.length);
        const bh = ((h - padY * 2) * d.value) / max;
        const y = h - padY - bh;
        return (
          <g key={i}>
            <rect x={x} y={y} width={bw} height={bh} rx="1" fill={`url(#bar-${color})`} />
          </g>
        );
      })}
      {data.map((d, i) => {
        const x = padX + i * ((w - padX * 2) / data.length) + bw / 2;
        return (
          <text key={`l-${i}`} x={x} y={h - 1} textAnchor="middle" fontSize="3.5" fill="rgba(255,255,255,0.4)">{d.label}</text>
        );
      })}
    </svg>
  );
}

export function LineChart({ data, height = 80, color = "#a78bfa" }: { data: LineDatum[]; height?: number; color?: string }) {
  const w = 100;
  const h = height;
  const max = Math.max(...data.map(d => d.value), 1);
  const min = Math.min(...data.map(d => d.value), 0);
  const range = Math.max(max - min, 1);
  const stepX = w / Math.max(data.length - 1, 1);
  const points = data.map((d, i) => ({
    x: i * stepX,
    y: h - 8 - ((d.value - min) / range) * (h - 16),
  }));
  const path = points.map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`)).join(" ");
  const area = `${path} L ${w} ${h} L 0 ${h} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`line-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.45" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#line-${color})`} />
      <path d={path} fill="none" stroke={color} strokeWidth="0.8" />
      {points.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="0.8" fill={color} />
      ))}
    </svg>
  );
}

export function DonutChart({ data, size = 120 }: { data: { label: string; value: number; color: string }[]; size?: number }) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const r = 50;
  const cx = size / 2;
  const cy = size / 2;
  let acc = 0;
  const arcs = data.map((d, i) => {
    const startAngle = (acc / total) * 2 * Math.PI;
    acc += d.value;
    const endAngle = (acc / total) * 2 * Math.PI;
    const x1 = cx + r * Math.sin(startAngle);
    const y1 = cy - r * Math.cos(startAngle);
    const x2 = cx + r * Math.sin(endAngle);
    const y2 = cy - r * Math.cos(endAngle);
    const large = endAngle - startAngle > Math.PI ? 1 : 0;
    return { d: `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`, color: d.color, label: d.label, pct: Math.round((d.value / total) * 100) };
  });
  return (
    <div className="flex items-center gap-4">
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
        {arcs.map((a, i) => (
          <path key={i} d={a.d} fill={a.color} opacity="0.85" />
        ))}
        <circle cx={cx} cy={cy} r="28" fill="#0a0e1a" />
        <text x={cx} y={cy - 4} textAnchor="middle" fontSize="11" fill="white" fontWeight="600">{total}</text>
        <text x={cx} y={cy + 9} textAnchor="middle" fontSize="6" fill="rgba(255,255,255,0.5)">总数</text>
      </svg>
      <div className="space-y-1.5 text-xs">
        {data.map((d, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-sm" style={{ background: d.color }} />
            <span className="text-gray-300">{d.label}</span>
            <span className="text-gray-500 ml-2">{Math.round((d.value / total) * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}