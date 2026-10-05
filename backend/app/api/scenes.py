"""业务场景中心数据。

真实环境下 `scenes` 来自场景注册表：每个场景 = 一组 Agent + 一组 Skills + 触发条件 + 收益指标。
这里返回演示数据。
"""
from __future__ import annotations

from typing import Any, Dict, List


def get_scenes_payload() -> Dict[str, Any]:
    return {
        "title": "业务场景中心",
        "subtitle": "选择场景流程，通过 AI 提升企业运营效率",
        "stages": [
            {"code": "L1", "title": "数字化",          "desc": "数据资产沉淀",   "active": False},
            {"code": "L2", "title": "知识智能化",      "desc": "知识结构化",     "active": False},
            {"code": "L3", "title": "AI 辅助决策",     "desc": "智能判断与建议", "active": True},
            {"code": "L4", "title": "Agent 自动执行",  "desc": "AI 员工自主行动", "active": False},
        ],
        "scenes": [
            {
                "id": "scene-ops",
                "name": "设备运维智能化",
                "level": "L2",
                "color": "from-sky-500/20 to-blue-500/10",
                "border": "border-sky-500/30",
                "badge": "bg-sky-500/15 text-sky-300",
                "desc": "通过 AI 算法精准预测异常，提前维护",
                "metrics": [{"label": "响应时间缩短", "value": "30%"}],
                "agents": ["设备运维工程师"],
            },
            {
                "id": "scene-sales",
                "name": "销售管理智能化",
                "level": "L3",
                "color": "from-rose-500/20 to-orange-500/10",
                "border": "border-rose-500/30",
                "badge": "bg-rose-500/15 text-rose-300",
                "desc": "通过 AI 算法精准预测异常，提前维护",
                "metrics": [{"label": "成单率提升", "value": "15%"}],
                "agents": ["销售分析师"],
            },
            {
                "id": "scene-knowledge",
                "name": "企业知识助手",
                "level": "L2",
                "color": "from-violet-500/20 to-purple-500/10",
                "border": "border-violet-500/30",
                "badge": "bg-violet-500/15 text-violet-300",
                "desc": "通过 AI 算法精准预测异常，提前维护",
                "metrics": [{"label": "查询效率提升", "value": "40%"}],
                "agents": ["知识助手"],
            },
        ],
    }
