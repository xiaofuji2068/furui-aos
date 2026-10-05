"""P0-016 企业总览 / AI 员工 / 最近活动 —— 真实数据回归（Task #16）。

锁定：
- GET /api/overview  KPI 来自真实统计（与 /api/agents 交叉校验）
- GET /api/agents   真实 Agent 表（含 today_tasks / success_tasks / id 等唯一字段）
- GET /api/activities 真实 AgentExecution 表
- 旧的 mock 路由（/api/agents、/api/tasks、/api/tasks/confirm、/api/activities）
  已被删除，/api/tasks 现在走真实任务中心（返回 {total, items}，item 含 step_count）

运行：
    backend/venv/Scripts/python.exe tests/test_dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client: TestClient | None = None
PASS, FAIL = [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def bearer(username: str, password: str = "123456") -> dict:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败 {username}: {r.text}"
    token = r.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def main():
    global client
    with TestClient(app) as c:
        client = c
        h = bearer("admin")

        print("\n=== /api/overview 真实 KPI ===")
        r = client.get("/api/overview", headers=h)
        check("overview 200", r.status_code == 200, r.text[:120])
        ov = r.json()["data"]
        check("greeting 存在", bool(ov.get("greeting")))
        kpis = ov.get("kpis") or {}
        for k in ("ai_employees_total", "ai_employees_working", "tasks_pending", "tasks_completed"):
            check(f"kpi.{k} 存在", k in kpis and isinstance(kpis[k].get("value"), int))
        check("insights 是列表", isinstance(ov.get("insights"), list))
        check("data_sources 是列表", isinstance(ov.get("data_sources"), list))

        print("\n=== /api/agents 真实 Agent 表 ===")
        r = client.get("/api/agents", headers=h)
        check("agents 200", r.status_code == 200, r.text[:120])
        ag = r.json()["data"]["items"]
        check("agents 非空", isinstance(ag, list) and len(ag) > 0)
        a0 = ag[0] if ag else {}
        # 以下字段只有真实端点提供，mock 版本没有 → 用来证明 mock 已删除
        check("agent 含 id(整数)", isinstance(a0.get("id"), int))
        check("agent 含 today_tasks", "today_tasks" in a0)
        check("agent 含 success_tasks", "success_tasks" in a0)
        check("agent 含 current_task", "current_task" in a0)
        check("agent.status 是映射值", a0.get("status") in ("working", "idle", "waiting", "error"))

        print("\n=== overview 与 agents 交叉校验 ===")
        check("ai_employees_total == len(agents)",
              kpis["ai_employees_total"]["value"] == len(ag),
              f"{kpis['ai_employees_total']['value']} vs {len(ag)}")
        working = sum(1 for a in ag if a["status"] == "working")
        check("ai_employees_working == 工作中数",
              kpis["ai_employees_working"]["value"] == working,
              f"{kpis['ai_employees_working']['value']} vs {working}")

        print("\n=== /api/activities 真实执行表 ===")
        r = client.get("/api/activities?limit=10", headers=h)
        check("activities 200", r.status_code == 200, r.text[:120])
        ac = r.json()["data"]["items"]
        check("activities 是列表", isinstance(ac, list))
        if ac:
            check("activity 含 actor/text/timestamp",
                  "actor" in ac[0] and "text" in ac[0] and "timestamp" in ac[0])

        print("\n=== 旧 mock /api/tasks 已被真实任务中心取代 ===")
        r = client.get("/api/tasks?category=待确认", headers=h)
        check("tasks 200", r.status_code == 200, r.text[:120])
        tk = r.json()["data"]
        check("tasks 返回 {total, items}", "total" in tk and "items" in tk)
        if tk["items"]:
            check("task item 含 step_count（真实 _task_brief）",
                  "step_count" in tk["items"][0] and "steps_done" in tk["items"][0])

        print("\n=== 旧 mock /api/tasks/confirm 已删除（不再 200）===")
        r = client.post("/api/tasks/confirm", headers=h, json={"task_id": "x"})
        check("tasks/confirm 不再是 200", r.status_code != 200, str(r.status_code))

    print("\n" + "=" * 56)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print(f"  - {f}")
    print("=" * 56)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
