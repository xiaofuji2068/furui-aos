"""P0-017 多 Agent 编排（协调层 Coordinator）—— 真实数据回归（Task #17/#18）。

锁定：
- Coordinator.plan() 规则路由：单领域命中只选 1 个专家，多领域命中选 N 个，
  无命中时回退到打分最高的 1 个。
- Coordinator.agent_view() 锚定 Ontology 真实语义对象（订单/设备/工单/风险事件），
  不编造数字；sales-analyst 视角必须出现"在册订单 N 笔"（来自真实 Ontology 种子）。
- Coordinator.synthesize() 把多视角收敛成一份带归属的综合结论。
- POST /api/orchestrate SSE：返回 plan / agent_view / token / done 四类事件，且 200。

运行：
    backend/venv/Scripts/python.exe tests/test_coordinator.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.coordinator import Coordinator  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models_ai import Agent  # noqa: E402

PASS, FAIL = [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def get_agent(db, code: str) -> Agent:
    return db.query(Agent).filter(Agent.code == code).first()


def main():
    coord = Coordinator()
    db = SessionLocal()
    try:
        roster = coord.roster(db, None)
        check("名册非空(含可执行 Agent)", len(roster) > 0, f"len={len(roster)}")
        roster_codes = {a.code for a in roster}
        check("名册包含 sales-analyst", "sales-analyst" in roster_codes)
        check("名册包含 ops-engineer", "ops-engineer" in roster_codes)
        check("名册包含 knowledge-assistant", "knowledge-assistant" in roster_codes)

        # ---------- plan：单领域 ----------
        print("\n=== plan 单领域 ===")
        p_single = coord.plan("分析本月销售业绩增长与下滑归因", roster)
        single_codes = {a.code for a in p_single["agents"]}
        check("单领域只选 sales-analyst", single_codes == {"sales-analyst"}, str(single_codes))
        check("单领域 strategy=single", p_single["strategy"] == "single")
        check("单领域 reason 非空", bool(p_single["reason"]))

        # ---------- plan：多领域 ----------
        print("\n=== plan 多领域 ===")
        p_multi = coord.plan("销售订单下滑的同时设备频繁故障，需要复盘并排查运维", roster)
        multi_codes = {a.code for a in p_multi["agents"]}
        check("多领域命中 sales-analyst", "sales-analyst" in multi_codes, str(multi_codes))
        check("多领域命中 ops-engineer", "ops-engineer" in multi_codes, str(multi_codes))
        check("多领域 strategy=multi", p_multi["strategy"] == "multi")
        check("多领域选出 >=2 个专家", len(p_multi["agents"]) >= 2, str(multi_codes))

        # ---------- plan：无命中回退 ----------
        print("\n=== plan 无命中回退 ===")
        p_fallback = coord.plan("今天杭州天气怎么样，适合开会吗", roster)
        check("无命中仍选出 1 个专家(打分回退)", len(p_fallback["agents"]) == 1,
              str({a.code for a in p_fallback["agents"]}))
        check("无命中 strategy=single", p_fallback["strategy"] == "single")

        # ---------- agent_view：锚定真实 Ontology ----------
        print("\n=== agent_view 锚定真实数据 ===")
        sales = get_agent(db, "sales-analyst")
        view = coord.agent_view(sales, "分析销售数据")
        check("agent_view 返回非空字符串", isinstance(view, str) and len(view) > 0)
        check("agent_view 带专家视角头", view.startswith("【") and "视角" in view)
        check("agent_view 锚定真实订单数据(在册订单 N 笔)", "在册订单" in view and "笔" in view,
              view[:80])

        ops = get_agent(db, "ops-engineer")
        ops_view = coord.agent_view(ops, "设备状态巡检")
        check("ops agent_view 含设备状态", "设备" in ops_view and "状态" in ops_view, ops_view[:80])

        # ---------- synthesize：收敛多视角 ----------
        print("\n=== synthesize 综合收敛 ===")
        views = [
            {"agent": sales.name, "avatar": sales.avatar or "🤖", "code": "sales-analyst", "view": view},
            {"agent": ops.name, "avatar": ops.avatar or "🤖", "code": "ops-engineer", "view": ops_view},
        ]
        final = coord.synthesize("综合诊断经营问题", views)
        check("synthesize 含原始问题", "综合诊断经营问题" in final)
        check("synthesize 含专家归属", sales.name in final and ops.name in final)
        check("synthesize 含综合结论", "综合结论" in final)
        check("synthesize 含下一步建议", "下一步" in final and "确认" in final)

        # ---------- SSE：POST /api/orchestrate ----------
        print("\n=== POST /api/orchestrate SSE ===")
        from fastapi.testclient import TestClient
        from app.main import app

        events: list = []
        with TestClient(app) as tc:
            with tc.stream("POST", "/api/orchestrate", json={"message": "分析本月销售并排查设备异常"}) as r:
                check("orchestrate HTTP 200", r.status_code == 200, str(r.status_code))
                buf = ""
                for line in r.iter_lines():
                    if line is None:
                        continue
                    if line.startswith("event:"):
                        buf = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                        try:
                            parsed = json.loads(data)
                        except json.JSONDecodeError:
                            parsed = data
                        events.append((buf, parsed))
                        buf = ""

        ev_types = [e[0] for e in events]
        check("SSE 含 plan 事件", "plan" in ev_types, str(ev_types))
        check("SSE 含 agent_view 事件", "agent_view" in ev_types, str(ev_types))
        check("SSE 含 token 事件", "token" in ev_types, str(ev_types))
        check("SSE 含 done 事件", "done" in ev_types, str(ev_types))

        plan_ev = next((p for t, p in events if t == "plan"), None)
        check("plan 事件含 strategy", isinstance(plan_ev, dict) and "strategy" in plan_ev, str(plan_ev))
        check("plan 事件含 agents 列表", isinstance(plan_ev, dict)
              and isinstance(plan_ev.get("agents"), list) and len(plan_ev["agents"]) > 0,
              str(plan_ev))

        done_ev = next((p for t, p in events if t == "done"), None)
        check("done 事件含 strategy 与 agents", isinstance(done_ev, dict)
              and "strategy" in done_ev and "agents" in done_ev, str(done_ev))
    finally:
        db.close()

    print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
    if FAIL:
        print("失败项：", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
