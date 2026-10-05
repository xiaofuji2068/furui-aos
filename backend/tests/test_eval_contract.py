"""3.X.2 动作表 #5：EvalContract 评估合同 + Approval.decision_lineage（图谱决策治理）。

验收口径（差距清单原文）：
    「审批页可见 lineage；EvalContract 通过 admin 配置生效」

锁定：
- 默认 seed 3 条 EvalContract 基线（accuracy≥0.9 / fairness≥0.8 / latency≤30s）
- GET /api/admin/eval-contracts 一览；POST 幂等 upsert（新增/停用生效）
- approve / reject 决策后写 Approval.decision_lineage（input_hash / output_hash / 决策人 / 时间）
- lineage 可复算：对同一审批单重算 input_hash 一致（证据域未篡改）
- 审批详情 GET /api/approvals/{id} 返回 decision_lineage（前端审批页可见）

依赖：admin / sales 用户存在；create_sales_task 为 Level3。

运行：
    backend/venv/Scripts/python.exe tests/test_eval_contract.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Company, User  # noqa: E402
from app.models_ai import (  # noqa: E402
    Agent, Approval, EvalContract, SalesTask,
)
from app.tool_gateway import (  # noqa: E402
    ToolContext, _decision_input_hash, decide_approval, execute,
)

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
        agent = (db.query(Agent).filter(Agent.code == "sales-agent").first()
                or db.query(Agent).filter(Agent.code == "sales-analyst").first()
                or db.query(Agent).order_by(Agent.id).first())
        check("admin 用户存在", user is not None)
        check("agent 存在", agent is not None)
        if not user or not agent:
            print("  无法继续：种子用户/Agent 缺失")
            print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
            return 1

        print("\n=== 1. EvalContract 默认基线（seed 生效） ===")
        seeded = {r.name: r for r in db.query(EvalContract).all()}
        check("seed 含 accuracy@agent", "accuracy@agent" in seeded)
        check("seed 含 fairness@approval", "fairness@approval" in seeded)
        check("seed 含 latency@toolcall", "latency@toolcall" in seeded)
        if "accuracy@agent" in seeded:
            acc = seeded["accuracy@agent"]
            check("accuracy 阈值 0.9 / gte / enabled",
                  acc.threshold == 0.9 and acc.operator == "gte" and acc.enabled,
                  f"{acc.threshold} {acc.operator} enabled={acc.enabled}")

        admin_tok = _login(c, "admin", "123456")
        check("admin 登录成功", bool(admin_tok))
        HA = {"Authorization": f"Bearer {admin_tok}"} if admin_tok else {}
        if not admin_tok:
            print("  无法继续：admin 登录失败")
            print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
            return 1

        print("\n=== 2. GET /api/admin/eval-contracts 一览 ===")
        r_l = c.get("/api/admin/eval-contracts", headers=HA)
        check("GET 200", r_l.status_code == 200, str(r_l.status_code))
        items = r_l.json().get("data", r_l.json()).get("items", []) if r_l.status_code == 200 else []
        check("列表 ≥ 3 条基线", len(items) >= 3, str(len(items)))
        check("每条含 metric/operator/threshold/enabled",
              all({"metric", "operator", "threshold", "enabled"} <= set(i.keys()) for i in items),
              str(items[0]) if items else "empty")

        print("\n=== 3. POST 幂等 upsert：新增 + 停用生效 ===")
        r_c = c.post("/api/admin/eval-contracts", headers=HA, json={
            "name": "test-contract-demo", "description": "测试合同",
            "metric": "accuracy", "operator": "gte", "threshold": 0.95, "enabled": True,
        })
        check("POST 新建 200", r_c.status_code == 200, str(r_c.status_code))
        if r_c.status_code == 200:
            ctr = r_c.json().get("data", {}).get("contract", {})
            check("新合同含 id/name/threshold", bool(ctr.get("id")) and ctr.get("threshold") == 0.95,
                  str(ctr))
        # 幂等：同 name 再 POST（改阈值）→ 更新而非重复
        r_c2 = c.post("/api/admin/eval-contracts", headers=HA, json={
            "name": "test-contract-demo", "description": "测试合同(改)",
            "metric": "accuracy", "operator": "gte", "threshold": 0.97, "enabled": False,
        })
        check("POST 同 name 更新 200", r_c2.status_code == 200, str(r_c2.status_code))
        row = db.query(EvalContract).filter(EvalContract.name == "test-contract-demo").first()
        check("更新生效：threshold=0.97", row is not None and row.threshold == 0.97,
              f"threshold={row.threshold if row else None}")
        check("停用生效：enabled=False", row is not None and not row.enabled,
              f"enabled={row.enabled if row else None}")
        check("未重复插入（仍 1 条）",
              db.query(EvalContract).filter(EvalContract.name == "test-contract-demo").count() == 1)
        # 参数校验
        r_bad = c.post("/api/admin/eval-contracts", headers=HA, json={
            "name": "bad", "metric": "f1", "operator": "gte", "threshold": 0.5, "enabled": True,
        })
        check("非法 metric 400", r_bad.status_code == 400, str(r_bad.status_code))

        print("\n=== 4. 审批决策写 lineage（reject 路径） ===")
        ctx = ToolContext(db=db, agent=agent, user=user, company_id=cid)
        r3 = execute(ctx, "create_sales_task", {
            "customer_id": 1, "customer_name": "Lineage 测试客户", "title": "Lineage 拒绝测试",
            "detail": "测试", "priority": "medium", "owner": "王销", "due_date": "2026-10-01",
            "_reason": "验收测试", "_evidence": {"qty": 2},
        })
        ap1 = db.query(Approval).filter(Approval.id == r3.get("approval_id")).first() if r3.get("approval_id") else None
        check("生成了 Level3 审批单", ap1 is not None and ap1.status == "Pending",
              f"approval#{ap1.id if ap1 else '-'}")
        if ap1:
            rd = decide_approval(db, ap1.id, user=user, decision="reject", comment="数据不足以支持")
            check("reject 成功", rd.get("ok") and rd.get("status") == "Rejected", str(rd))
            db.refresh(ap1)
            lg = json.loads(ap1.decision_lineage or "{}")
            check("reject 写 decision_lineage", bool(lg), str(ap1.decision_lineage)[:80])
            check("lineage.decision=reject", lg.get("decision") == "reject", str(lg.get("decision")))
            check("lineage 含 input_hash", bool(lg.get("input_hash")), str(lg.get("input_hash", ""))[:12])
            check("lineage 含决策人", lg.get("decided_by") == user.name, str(lg.get("decided_by")))
            check("lineage 含决策时间", bool(lg.get("decided_at")), str(lg.get("decided_at")))
            # 可复算：同一审批单重算 input_hash 一致（证据域未篡改）
            check("input_hash 可复算一致",
                  lg.get("input_hash") == _decision_input_hash(ap1),
                  f"{lg.get('input_hash', '')[:12]} vs {_decision_input_hash(ap1)[:12]}")
            # 清理 reject 审批单（避免跨测试残留）
            db.delete(ap1)
            db.commit()

        print("\n=== 5. 审批决策写 lineage（approve 路径 + 输出哈希） ===")
        r4 = execute(ctx, "create_sales_task", {
            "customer_id": 1, "customer_name": "Lineage 测试客户", "title": "Lineage 批准测试",
            "detail": "测试", "priority": "high", "owner": "王销", "due_date": "2026-10-05",
            "_reason": "验收测试", "_evidence": {"qty": 3},
        })
        ap2 = db.query(Approval).filter(Approval.id == r4.get("approval_id")).first() if r4.get("approval_id") else None
        check("生成了第二个审批单", ap2 is not None, f"approval#{ap2.id if ap2 else '-'}")
        if ap2:
            rd2 = decide_approval(db, ap2.id, user=user, decision="approve", comment="同意执行")
            check("approve 成功", rd2.get("ok") and rd2.get("status") == "Executed", str(rd2))
            db.refresh(ap2)
            lg2 = json.loads(ap2.decision_lineage or "{}")
            check("lineage.decision=approve", lg2.get("decision") == "approve",
                  str(lg2.get("decision")))
            check("lineage 含 output_hash（执行结果指纹）", bool(lg2.get("output_hash")),
                  str(lg2.get("output_hash", ""))[:12])
            check("lineage 含 receipt_id（凭证关联）", bool(lg2.get("receipt_id")),
                  str(lg2.get("receipt_id")))
            check("lineage 含 input_hash", bool(lg2.get("input_hash")))
            check("lineage.input_hash 可复算一致",
                  lg2.get("input_hash") == _decision_input_hash(ap2))

            # 审批详情 API 返回 lineage（前端审批页可见）
            r_d = c.get(f"/api/approvals/{ap2.id}", headers=HA)
            check("GET /api/approvals/{id} 200", r_d.status_code == 200, str(r_d.status_code))
            if r_d.status_code == 200:
                body = r_d.json().get("data", r_d.json())
                check("详情含 decision_lineage", "decision_lineage" in body,
                      str(sorted(body.keys())))
                dl = body.get("decision_lineage") or {}
                check("详情 lineage.decision=approve",
                      dl.get("decision") == "approve", str(dl.get("decision")))

            # 清理：删测试 sales_task + approval + 关联 receipt（避免跨测试残留）
            from app.models_ai import ActionReceipt

            for st in db.query(SalesTask).filter(SalesTask.approval_id == ap2.id).all():
                db.delete(st)
            for rc in db.query(ActionReceipt).filter(ActionReceipt.approval_id == ap2.id).all():
                db.delete(rc)
            db.delete(ap2)
            db.commit()

        print("\n=== 6. 清理测试数据 ===")
        db.query(EvalContract).filter(EvalContract.name == "test-contract-demo").delete(synchronize_session=False)
        db.commit()
        check("测试合同已清理",
              db.query(EvalContract).filter(EvalContract.name == "test-contract-demo").count() == 0)
        db.close()

    print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
    if FAIL:
        print("失败：", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
