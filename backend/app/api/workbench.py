"""AI 工作台数据。

真实环境下：
- `history` 来自会话存储（Redis / Postgres）
- `charts` 由 Agent 执行分析后回填（走 Ontology 语义层查询）
- 这里先返回演示数据
"""
from __future__ import annotations

from typing import Any, Dict, List


def get_workbench_payload() -> Dict[str, Any]:
    return {
        "greeting": "AI 工作台",
        "subtitle": "与您的 AI 助理对话，可让它帮您执行查询、分析、生成等操作。",
        "history": {
            "today": [
                {"id": 1, "title": "分析本月销售情况", "active": True},
                {"id": 2, "title": "查询设备维护手册", "active": False},
                {"id": 3, "title": "生成财务周报",     "active": False},
                {"id": 4, "title": "客户分层运营建议", "active": False},
            ],
            "yesterday": [
                {"id": 5, "title": "AI 员工任务复盘",   "active": False},
                {"id": 6, "title": "本月库存预警分析", "active": False},
            ],
        },
        "session": {
            "title": "分析一下最近的销售数据，让 AI 帮我判断哪些区域需要重点关注？",
            "summary": "我将自动分析 ERP 销售数据。请确认完成后，可以生成完整报告或协助销售负责人。",
            "action_label": "分析一下最近的销售数据",
        },
        "steps": [
            {"id": 1, "label": "查询 ERP 销售数据",     "status": "done"},
            {"id": 2, "label": "分析销售数据变化趋势", "status": "done"},
            {"id": 3, "label": "对比去年同期数据",     "status": "done"},
            {"id": 4, "label": "生成可视化报告",       "status": "active"},
            {"id": 5, "label": "生成可视化图表",       "status": "pending"},
        ],
        "charts": {
            "bar": {
                "title": "月度销售额（万元）",
                "delta": "↑ 12.4%",
                "color": "#60a5fa",
                "data": [
                    {"label": "1月", "value": 78},  {"label": "2月", "value": 92},
                    {"label": "3月", "value": 65},  {"label": "4月", "value": 88},
                    {"label": "5月", "value": 110}, {"label": "6月", "value": 134},
                ],
            },
            "line": {
                "title": "本周趋势",
                "badge": "实时",
                "color": "#a78bfa",
                "data": [
                    {"label": "M", "value": 38}, {"label": "T", "value": 52},
                    {"label": "W", "value": 41}, {"label": "T", "value": 68},
                    {"label": "F", "value": 74}, {"label": "S", "value": 58},
                    {"label": "S", "value": 62},
                ],
            },
            "donut": {
                "title": "任务分布",
                "data": [
                    {"label": "已完成", "value": 38, "color": "#10b981"},
                    {"label": "进行中", "value": 7,  "color": "#f59e0b"},
                    {"label": "待确认", "value": 2,  "color": "#ef4444"},
                    {"label": "已暂停", "value": 0,  "color": "#6b7280"},
                ],
            },
        },
        "quick_actions": [
            "📋 请生成销售周报",
            "✉️ 请协助销售负责人",
            "💬 继续对话",
            "📤 导出数据",
        ],
    }
