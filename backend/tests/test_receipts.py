"""3.X.2 动作表 #4：Receipt 受控动作凭证（图谱 20-05）。

验收口径（差距清单原文）：
    「tool_gateway.execute() 路径强制 Receipt；测试覆盖补写」

锁定：
- 任何经网关真实执行（Level1/2 直行 + Level3 审批批准）成功后必写 ActionReceipt
- execute() 返回 receipt_id；写回门禁 _require_receipt 校验凭证真实存在
- Receipt 含 params/result 的 sha256 哈希，事后可复算核验（同参同哈希）
- 审批详情 GET /api/approvals/{id} 返回 receipts（前端可见凭证）
- GET /api/admin/receipts 全局凭证查询（工具过滤）
- 门禁反例：不存在的 receipt / approval 不匹配 → 校验失败

依赖：admin / sales 用户存在（bootstrap 默认种子）；create_sales_task 为 Level3。

运行：
    backend/venv/Scripts/python.exe tests/test_receipts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Company, User  # noqa: E402
from app.models_ai import (  # noqa: E402
    ActionReceipt, Agent, Approval, AuditLog, SalesTask,
)
from app.tool_gateway import ToolContext, _hash, _require_receipt, decide_approval, execute  # noqa: E402

PASS, FAIL = [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def _login(c: TestClient, username: str, password: str) -> str | None:
    r = c.post("/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        return None
    try:
        return r.json()["data"]["token"]
    except (KeyError, TypeError):
        return None


def main():
    with TestClient(app) as c:
        db = SessionLocal()
        cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)
        user = db.query(User).filter(User.username == "admin").first()
        agent = db.query(Agent).filter(Agent.code == "sales-agent").order_by(Agent.id).first() or \
            db.query(Agent).order_by(Agent.id).first()
        check("admin 用户存在", user is not None)
        check("agent 存在", agent is not None)
        if not user or not agent:
            print("  无法继续：种子用户/Agent 缺失")
            print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
            return 1

        # 记录起点，结束时清理
        rcpt_baseline = db.query(ActionReceipt).count()
        created_ids: list = []

        print("\n=== 1. Level2 直行：execute 成功强制写 Receipt ===")
        ctx = ToolContext(db=db, agent=agent, user=user, company_id=cid)
        r = execute(ctx, "analyze_sales_drop", {})
        check("Level2 直行成功", r.get("ok"), str(r.get("error", "")))
        check("execute 返回 receipt_id", bool(r.get("receipt_id")), str(r.get("receipt_id")))
        rcpt = db.get(ActionReceipt, r.get("receipt_id")) if r.get("receipt_id") else None
        check("Receipt 已落库", rcpt is not None)
        if rcpt:
            created_ids.append(rcpt.id)
            check("Receipt.tool_name = analyze_sales_drop", rcpt.tool_name == "analyze_sales_drop",
                  rcpt.tool_name)
            check("Receipt.actor_type = agent", rcpt.actor_type == "agent", rcpt.actor_type)
            check("Receipt 无 approval 关联（直行）", rcpt.approval_id is None,
                  str(rcpt.approval_id))

            # 哈希可复算：同参同哈希（复算调用产生的 receipt 一并记入清理）
            params = {"_approval_id": None}
            fresh_r = execute(ctx, "analyze_sales_drop", {})
            fresh = fresh_r.get("result", {})
            if fresh_r.get("receipt_id"):
                created_ids.append(fresh_r["receipt_id"])
            recompute_p = _hash(params)
            recompute_r = _hash(fresh)
            check("params_hash 可复算（同参同哈希）",
                  rcpt.params_hash == _hash({}), f"{rcpt.params_hash[:12]} vs {recompute_p[:12]}")
            check("result_hash 可复算（同工具同结果）",
                  rcpt.result_hash == _hash(fresh), f"{rcpt.result_hash[:12]} vs {recompute_r[:12]}")

        print("\n=== 2. 写回门禁校验（_require_receipt） ===")
        check("门禁：真实 receipt 校验通过",
              _require_receipt(db, rcpt.id, approval_id=None, tool_name="analyze_sales_drop"),
              f"id={rcpt.id}")
        check("门禁：tool_name 不匹配 → False",
              not _require_receipt(db, rcpt.id, approval_id=None, tool_name="other_tool"))
        check("门禁：approval_id 不匹配 → False",
              not _require_receipt(db, rcpt.id, approval_id=999999, tool_name="analyze_sales_drop"))
        check("门禁：不存在的 receipt → False",
              not _require_receipt(db, 99999999, approval_id=None, tool_name="x"))

        print("\n=== 3. Level3 审批批准：Receipt 强制留痕（actor=user） ===")
        admin_tok = _login(c, "admin", "123456")
        check("admin 登录成功", bool(admin_tok))
        HA = {"Authorization": f"Bearer {admin_tok}"} if admin_tok else {}
        if not admin_tok:
            print("  无法继续：admin 登录失败")
            print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
            return 1

        r3 = execute(ctx, "create_sales_task", {
            "customer_id": 1, "customer_name": "测试客户", "title": "Receipt 验收任务",
            "detail": "测试", "priority": "high", "owner": "王销", "due_date": "2026-09-30",
            "_reason": "验收测试", "_evidence": {"qty": 1},
        })
        check("Level3 直行被拦截（需审批）", (not r3.get("ok")) and r3.get("blocked"),
              str(r3))
        ap = db.query(Approval).filter(Approval.id == r3.get("approval_id")).first() if r3.get("approval_id") else None
        check("审批单已生成", ap is not None and ap.status == "Pending",
              f"approval#{ap.id if ap else '-'}")
        if ap:
            decided = decide_approval(db, ap.id, user=user, decision="approve",
                                      comment="验收：批准")
            check("批准后执行成功", decided.get("ok") and decided.get("status") == "Executed",
                  str(decided.get("error", "")))
            check("批准执行返回 receipt_id", bool(decided.get("receipt_id")),
                  str(decided.get("receipt_id")))
            rcpt2 = db.get(ActionReceipt, decided.get("receipt_id")) if decided.get("receipt_id") else None
            check("批准后 Receipt 已落库", rcpt2 is not None)
            if rcpt2:
                created_ids.append(rcpt2.id)
                check("Receipt.actor_type = user（人工批准执行）",
                      rcpt2.actor_type == "user", rcpt2.actor_type)
                check("Receipt.approval_id 关联审批单", rcpt2.approval_id == ap.id,
                      str(rcpt2.approval_id))
                check("门禁：批准路径凭证校验通过",
                      _require_receipt(db, rcpt2.id, approval_id=ap.id, tool_name="create_sales_task"))

            # 审批详情 API 含 receipts
            r_d = c.get(f"/api/approvals/{ap.id}", headers=HA)
            check("GET /api/approvals/{id} 200", r_d.status_code == 200, str(r_d.status_code))
            if r_d.status_code == 200:
                body = r_d.json().get("data", r_d.json())
                check("详情含 receipts 字段", "receipts" in body, str(sorted(body.keys())))
                check("详情 receipts 非空", len(body.get("receipts", [])) >= 1,
                      str(len(body.get("receipts", []))))

            # 清理：删测试产生的 sales_task + approval + receipt（保留基线前）
            for st in db.query(SalesTask).filter(SalesTask.approval_id == ap.id).all():
                db.delete(st)
            db.delete(ap)
            db.commit()

        print("\n=== 4. GET /api/admin/receipts 全局凭证查询 ===")
        r_l = c.get("/api/admin/receipts", headers=HA)
        check("GET /api/admin/receipts 200", r_l.status_code == 200, str(r_l.status_code))
        if r_l.status_code == 200:
            body = r_l.json().get("data", r_l.json())
            check("receipts 列表 total >= 新增数",
                  body.get("total", 0) >= len(created_ids),
                  f"total={body.get('total')} created={len(created_ids)}")
            r_f = c.get("/api/admin/receipts?tool=analyze_sales_drop", headers=HA)
            check("按 tool 过滤生效", r_f.status_code == 200 and
                  all(i["tool"] == "analyze_sales_drop" for i in r_f.json().get("data", {}).get("items", [])),
                  str(r_f.status_code))
            # 60-03 后端鉴权：admin 端点未带 token 一律 401（前端守卫只是体验层）
            r_n = c.get("/api/admin/receipts")
            check("无 token 访问 /admin/receipts 返回 401（后端强制）",
                  r_n.status_code == 401, str(r_n.status_code))

        # 清理本测试产生的直行 receipt
        for rid in created_ids:
            rc = db.get(ActionReceipt, rid)
            if rc:
                db.delete(rc)
        db.commit()
        after = db.query(ActionReceipt).count()
        check("清理完成：receipt 数回到起点", after == rcpt_baseline,
              f"{rcpt_baseline} -> {after}")

        db.close()

    print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
    if FAIL:
        print("失败：", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
