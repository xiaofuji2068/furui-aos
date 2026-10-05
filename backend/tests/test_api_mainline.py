"""API 层验收：主线 SSE / 任务中心 / 审批中心。

覆盖：鉴权（未登录 401、无权限 403）、SSE 六步事件、审批闭环。
运行： ./venv/Scripts/python.exe tests/test_api_mainline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient          # noqa: E402

from app.bootstrap import init_all                  # noqa: E402
from app.main import app                            # noqa: E402

PASS, FAIL = [], []


def check(name: str, ok: bool, extra: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  → ' + extra) if extra else ''}")


def login(client: TestClient, username: str) -> dict:
    r = client.post("/api/auth/login", json={"username": username, "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


def main() -> int:
    init_all()

    with TestClient(app) as client:
        print("\n=== 鉴权 ===")
        r = client.get("/api/tasks")
        check("未登录访问任务列表被拒(401)", r.status_code == 401, str(r.status_code))
        r = client.get("/api/approvals")
        check("未登录访问审批中心被拒(401)", r.status_code == 401, str(r.status_code))

        h_sales = login(client, "sales")      # owner：有 employee:execute / approval:approve
        h_analyst = login(client, "analyst")  # analyst：有 employee:execute，无 approval:approve
        check("登录成功并取得 token", bool(h_sales))

        print("\n=== 主线 SSE 执行 ===")
        events = []
        with client.stream("POST", "/api/mainline/run",
                           json={"question": "分析本月销售下降原因"},
                           headers=h_sales, timeout=120) as resp:
            check("SSE 响应状态码 200", resp.status_code == 200, str(resp.status_code))
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())

        check("收到 task 事件", "task" in events)
        check("收到 step 事件（12 个：6步×开始/完成）",
              events.count("step") == 12, f"{events.count('step')} 个")
        check("收到 tool_result 事件", "tool_result" in events)
        check("收到 token 流式正文", events.count("token") > 100, f"{events.count('token')} 个")
        check("收到 pending 事件（待审批）", "pending" in events)
        check("收到 done 事件", "done" in events)
        check("未收到 error 事件", "error" not in events)

        print("\n=== 任务中心（真实持久化）===")
        r = client.get("/api/tasks", headers=h_sales)
        check("任务列表返回 200", r.status_code == 200, str(r.status_code))
        items = r.json()["data"]["items"] if r.json().get("data") else r.json().get("items", [])
        check("列表中存在刚才执行的任务", len(items) >= 1, f"{len(items)} 条")
        tid = items[0]["id"] if items else None
        if tid:
            check("任务状态为 WaitingApproval", items[0]["status"] == "WaitingApproval", items[0]["status"])
            r = client.get(f"/api/tasks/{tid}", headers=h_sales)
            d = r.json()["data"] if r.json().get("data") else r.json()
            check("任务详情含 6 个步骤", len(d.get("steps", [])) == 6, f"{len(d.get('steps', []))} 步")
            check("任务详情含执行日志", len(d.get("executions", [])) >= 5,
                  f"{len(d.get('executions', []))} 条")
            check("任务详情含报告正文", len(d.get("result", "")) > 300, f"{len(d.get('result',''))} 字")

        print("\n=== 审批中心 ===")
        r = client.get("/api/approvals", headers=h_sales)
        check("审批列表返回 200", r.status_code == 200, str(r.status_code))
        aps = r.json()["data"]["items"] if r.json().get("data") else r.json().get("items", [])
        check("存在待审批单", len(aps) >= 1, f"{len(aps)} 条")
        aid = aps[0]["id"] if aps else None

        if aid:
            r = client.get(f"/api/approvals/{aid}", headers=h_sales)
            d = r.json()["data"] if r.json().get("data") else r.json()
            check("详情含 AI 理由", bool(d.get("ai_reason")))
            check("详情含数据依据", bool(d.get("data_evidence")))
            check("详情含执行计划", bool(d.get("plan")))
            check("详情含待执行参数", bool(d.get("payload")))

            # 无审批权限的用户
            r = client.post(f"/api/approvals/{aid}/approve", json={"comment": "试试"},
                            headers=h_analyst)
            check("无审批权限者被拒(403)", r.status_code == 403, str(r.status_code))

            # 有审批权限者批准
            r = client.post(f"/api/approvals/{aid}/approve",
                            json={"comment": "同意，按二级响应执行"}, headers=h_sales)
            check("有权限者批准成功(200)", r.status_code == 200, str(r.status_code))
            d = r.json()["data"] if r.json().get("data") else r.json()
            check("批准后状态为 Executed", d.get("status") == "Executed", str(d.get("status")))
            check("返回了落库的销售任务", bool(d.get("sales_task")),
                  d.get("sales_task", {}).get("title", ""))

            r = client.get("/api/sales-tasks", headers=h_sales)
            st = r.json()["data"]["items"] if r.json().get("data") else r.json().get("items", [])
            check("销售任务列表可见该任务", len(st) >= 1, f"{len(st)} 条")

        print("\n=== 审批规则（四级动作分类）===")
        r = client.get("/api/approvals/rules", headers=h_sales)
        rules = r.json()["data"]["items"] if r.json().get("data") else r.json().get("items", [])
        check("返回动作分级规则", len(rules) >= 5, f"{len(rules)} 条")
        check("规则含分级文案", any(x.get("level_text") for x in rules))

    print("\n" + "=" * 56)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("\n失败项：")
        for f in FAIL:
            print("  -", f)
    print("=" * 56)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
