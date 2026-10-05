"""TASK-011 对象 AIP/Action 嵌入（图谱 40-04）。

锁定：
- GET /api/objects/{type}/{id} 返回对象视图 + AIP/Action 表单（动作含 level/权限过滤）
- Device 对象有通用动作（send_notification / draft_report）；Customer 对象额外有 create_sales_task
- POST 执行 Level2 动作（draft_report）→ 直行成功 + receipt_id（写回留凭证）
- POST 执行 Level3 动作（send_notification / create_sales_task）→ blocked + approval_id（写回走审批）
- 不存在的对象 → 404；不存在的动作 → 400；未登录 → 401
- 清理：删除产生的 receipt / approval / notification / sales_task

依赖：admin 用户存在（bootstrap 种子）；本体图种子含 Customer CUS-001、Device DEV-SKU-A12。

运行：
    backend/venv/Scripts/python.exe tests/test_object_actions.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.models_ai import (  # noqa: E402
    ActionReceipt, Approval, Notification, SalesTask, ToolExecution,
)

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
    with TestClient(app) as c:
        global client
        client = c
        db = SessionLocal()
        user = db.query(User).filter(User.username == "admin").first()
        check("admin 用户存在", user is not None)
        if not user:
            print("  无法继续：种子用户缺失")
            print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
            return 1

        rcpt_baseline = db.query(ActionReceipt).count()
        ap_baseline = db.query(Approval).count()
        created: dict = {"receipts": [], "approvals": [], "notifications": [], "tasks": []}

        h = bearer("admin")

        print("\n=== 1. 对象视图 + AIP/Action 表单 ===")
        r = client.get("/api/objects/Device/DEV-SKU-A12", headers=h)
        check("GET 对象视图 200", r.status_code == 200, r.text[:160])
        body = r.json().get("data", r.json())
        check("对象信息返回", body.get("object", {}).get("id") == "DEV-SKU-A12", str(body.get("object"))[:120])
        check("Device 有通用动作", len(body.get("actions", [])) >= 2, str(len(body.get("actions", []))))
        acts = {a["action"]: a for a in body.get("actions", [])}
        check("动作含 send_notification", "send_notification" in acts, str(list(acts)))
        check("动作含 draft_report", "draft_report" in acts, str(list(acts)))
        check("动作带 level 字段", all("level" in a for a in body.get("actions", [])),
              str([a.get("action") for a in body.get("actions", [])]))
        check("动作带参数 schema", bool(acts.get("draft_report", {}).get("params")))

        r = client.get("/api/objects/Customer/CUS-001", headers=h)
        check("Customer 对象视图 200", r.status_code == 200, r.text[:160])
        body = r.json().get("data", r.json())
        acts = {a["action"]: a for a in body.get("actions", [])}
        check("Customer 有 create_sales_task", "create_sales_task" in acts, str(list(acts)))

        print("\n=== 2. 校验分支 ===")
        r = client.get("/api/objects/Device/NO-SUCH-DEV", headers=h)
        check("对象不存在 → 404", r.status_code == 404, str(r.status_code))
        r = client.get("/api/objects/Device/DEV-SKU-A12")
        check("未登录 GET → 401/403", r.status_code in (401, 403), str(r.status_code))
        r = client.post("/api/objects/Device/DEV-SKU-A12/actions/no_such_action",
                        headers=h, json={"params": {}})
        check("动作不存在 → 400", r.status_code == 400, r.text[:120])

        print("\n=== 3. Level2 写回：draft_report 直行留 Receipt ===")
        r = client.post("/api/objects/Device/DEV-SKU-A12/actions/draft_report",
                        headers=h, json={"params": {"topic": "设备运行分析"}})
        check("draft_report 200", r.status_code == 200, r.text[:200])
        dr = r.json().get("data", r.json())
        check("直行成功 ok=true", dr.get("ok") is True, str(dr)[:160])
        check("返回 receipt_id（写回留凭证）", bool(dr.get("receipt_id")), str(dr.get("receipt_id")))
        if dr.get("receipt_id"):
            rcpt = db.get(ActionReceipt, dr["receipt_id"])
            check("Receipt 已落库", rcpt is not None)
            if rcpt:
                created["receipts"].append(rcpt.id)
                check("Receipt.tool = draft_report", rcpt.tool_name == "draft_report", rcpt.tool_name)
        # 对象上下文注入实证：网关 _log 落 ToolExecution.input_data（params 明文 JSON）
        te = (db.query(ToolExecution)
              .filter(ToolExecution.tool_name == "draft_report")
              .order_by(ToolExecution.id.desc()).first())
        check("ToolExecution 已落库", te is not None)
        if te:
            inp = te.input_data or ""
            check("对象上下文注入 object_id", "DEV-SKU-A12" in inp, inp[:200])
            check("对象上下文注入 object_type", "object_type" in inp, inp[:200])
            check("对象上下文注入 object_name", "object_name" in inp, inp[:200])

        print("\n=== 4. Level3 写回：send_notification 生成审批单 ===")
        r = client.post("/api/objects/Device/DEV-SKU-A12/actions/send_notification",
                        headers=h, json={"params": {"message": "对象动作验收通知"}})
        check("send_notification 200", r.status_code == 200, r.text[:200])
        sn = r.json().get("data", r.json())
        check("Level3 被拦截 blocked=true", sn.get("blocked") is True, str(sn)[:160])
        check("生成 approval_id", bool(sn.get("approval_id")), str(sn.get("approval_id")))
        if sn.get("approval_id"):
            ap = db.get(Approval, sn["approval_id"])
            check("审批单 Pending", ap is not None and ap.status == "Pending", str(ap))
            if ap:
                created["approvals"].append(ap.id)
                check("审批单 action=send_notification", ap.action == "send_notification", ap.action)
                created["notifications"].append(ap.id)  # 通知在审批创建时生成（ref_id=approval）

        print("\n=== 5. Level3 写回：create_sales_task 生成审批单（对象上下文注入） ===")
        r = client.post("/api/objects/Customer/CUS-001/actions/create_sales_task",
                        headers=h, json={"params": {"title": "对象动作验收-跟进任务", "priority": "high"}})
        check("create_sales_task 200", r.status_code == 200, r.text[:200])
        ct = r.json().get("data", r.json())
        check("Level3 被拦截 blocked=true", ct.get("blocked") is True, str(ct)[:160])
        if ct.get("approval_id"):
            created["approvals"].append(ct["approval_id"])

        # ---- 清理 ----
        print("\n=== 清理 ===")
        for ap_id in created["approvals"]:
            for st in db.query(SalesTask).filter(SalesTask.approval_id == ap_id).all():
                created["tasks"].append(st.id)
                db.delete(st)
            ap = db.get(Approval, ap_id)
            if ap:
                db.delete(ap)
        for n in db.query(Notification).filter(Notification.ref_id.in_(
                [a for a in created["approvals"] if a]) if created["approvals"] else []).all():
            created["notifications"].append(n.id)
            db.delete(n)
        for rid in created["receipts"]:
            rc = db.get(ActionReceipt, rid)
            if rc:
                db.delete(rc)
        db.commit()

        check("清理后 receipt 数回基线",
              db.query(ActionReceipt).count() == rcpt_baseline,
              f"{rcpt_baseline} -> {db.query(ActionReceipt).count()}")
        check("清理后 approval 数回基线",
              db.query(Approval).count() == ap_baseline,
              f"{ap_baseline} -> {db.query(Approval).count()}")
        db.close()

    print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
    if FAIL:
        print("失败：", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
