"""P0-018 本体持久化（Phase 1 P0）—— 内存→DB 回归（Task #26）。

锁定：
- 启动后本体对象落库（Order/Product/Device/WorkOrder/Ticket/Customer），重启不丢。
- list_objects 优先读 DB 并返回 OntologyObject；DB 不可用时回退内存注册表。
- seed_ontology 幂等（重复调用行数不变）。
- create_workorder 等写入型动作落库，可被 list_objects 查到。
- SchemaRevision 基线 r1 存在（图谱 20-02）。
- Link 关系落库（P0-019 步骤 1.1）：Order→Customer / Device→Product / WorkOrder→Device / Ticket→WorkOrder，幂等且可查。

运行：
    backend/venv/Scripts/python.exe tests/test_ontology_persistence.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.ontology import (  # noqa: E402
    list_objects, search_objects, call_function, list_links, seed_ontology, ONTO,
)
from app.models import Company  # noqa: E402
from app.models_ontology import (  # noqa: E402
    OntologyLinkRow, OntologyObjectRow, OntologySchemaRevision, bump_revision,
)

PASS, FAIL = [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def main():
    with TestClient(app) as c:  # 触发 lifespan → init_all → seed_ontology
        db = SessionLocal()
        cid = db.query(Company).order_by(Company.id).first().id
        try:
            print("=== DB 持久化落库 ===")
            n_order = db.query(OntologyObjectRow).filter_by(company_id=cid, type="Order").count()
            check("Order 落库 = 5", n_order == 5, str(n_order))
            n_prod = db.query(OntologyObjectRow).filter_by(company_id=cid, type="Product").count()
            check("Product 落库 = 3", n_prod == 3, str(n_prod))
            n_dev = db.query(OntologyObjectRow).filter_by(company_id=cid, type="Device").count()
            check("Device 落库 = 8（3 销售硬件 + 5 核电监测终端）", n_dev == 8, str(n_dev))
            n_station = db.query(OntologyObjectRow).filter_by(company_id=cid, type="MonitoringStation").count()
            check("MonitoringStation 落库 = 5", n_station == 5, str(n_station))
            n_area = db.query(OntologyObjectRow).filter_by(company_id=cid, type="Area").count()
            check("Area 落库 = 3", n_area == 3, str(n_area))
            n_metric = db.query(OntologyObjectRow).filter_by(company_id=cid, type="MetricRecord").count()
            check("MetricRecord 落库 = 5", n_metric == 5, str(n_metric))
            n_insp = db.query(OntologyObjectRow).filter_by(company_id=cid, type="InspectionRecord").count()
            check("InspectionRecord 落库 = 5", n_insp == 5, str(n_insp))
            # 种子工单固定为 WO-001 / WO-002；create_workorder 动作可能产生额外残留，故按种子 ID 断言
            n_wo_seed = (db.query(OntologyObjectRow)
                         .filter(OntologyObjectRow.company_id == cid, OntologyObjectRow.type == "WorkOrder",
                                 OntologyObjectRow.object_id.in_(["WO-001", "WO-002"]))
                         .count())
            check("WorkOrder 种子 = 2", n_wo_seed == 2, str(n_wo_seed))
            n_rev = db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).count()
            check("SchemaRevision 基线存在", n_rev >= 1, str(n_rev))

            print("\n=== list_objects 走 DB 且类型正确 ===")
            orders = list_objects("Order")
            check("list_objects 返回非空", len(orders) > 0, str(len(orders)))
            check("返回的是 OntologyObject", hasattr(orders[0], "properties"))
            check("Order 数量与 DB 一致 = 5", len(orders) == 5, str(len(orders)))
            amt = orders[0].properties.get("amount")
            check("属性正确反序列化(amount 为数字)", isinstance(amt, (int, float)), str(amt))

            print("\n=== 幂等：重复 seed 行数不变 ===")
            before = db.query(OntologyObjectRow).filter(OntologyObjectRow.company_id == cid).count()
            seed_ontology(db, company_id=cid)
            after = db.query(OntologyObjectRow).filter(OntologyObjectRow.company_id == cid).count()
            check("seed 幂等(行数不变)", before == after, f"{before} -> {after}")

            print("\n=== search_objects 过滤生效 ===")
            hi = search_objects("Order", lambda o: o.properties.get("amount", 0) > 30000)
            check("能筛出大额订单", len(hi) >= 1, str(len(hi)))

            print("\n=== Link 关系落库（步骤 1.1）===")
            n_link = db.query(OntologyLinkRow).filter(OntologyLinkRow.company_id == cid).count()
            check("Link 落库 = 32（销售 11 + 核电巡检 21）", n_link == 32, str(n_link))
            link_ids = {(r.type, r.source_id, r.target_id) for r in db.query(OntologyLinkRow).filter(OntologyLinkRow.company_id == cid).all()}
            check("WorkOrder→Device 关系存在",
                  ("WorkOrderToDevice", "WO-001", "DEV-SKU-C33") in link_ids)
            check("Order→Customer 关系存在",
                  ("OrderToCustomer", "ORD-2026-0817", "CUS-001") in link_ids)
            check("Ticket→WorkOrder 关系存在",
                  ("TicketToWorkOrder", "T-002", "WO-002") in link_ids)
            before_links = db.query(OntologyLinkRow).filter(OntologyLinkRow.company_id == cid).count()
            seed_ontology(db, company_id=cid)
            after_links = db.query(OntologyLinkRow).filter(OntologyLinkRow.company_id == cid).count()
            check("Link seed 幂等(行数不变)", before_links == after_links,
                  f"{before_links} -> {after_links}")
            wods = list_links(type_name="WorkOrderToDevice")
            check("list_links 按类型过滤 = 2", len(wods) == 2, str(len(wods)))
            wo1 = list_links(source_id="WO-001")
            check("list_links 按源过滤", len(wo1) == 1 and wo1[0]["target_id"] == "DEV-SKU-C33",
                  str(wo1))

            print("\n=== SchemaRevision 演进（步骤 1.2）===")
            baseline_revs = {r.revision for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all()}
            r_new = bump_revision(db, "test bump", company_id=cid)
            bump_revision(db, "test bump 2", company_id=cid)
            revs_now = sorted(r.revision for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all())
            check("bump 生成新版本号", r_new is not None and r_new not in baseline_revs, str(r_new))
            check("版本号递增且唯一", len(revs_now) == len(set(revs_now)), str(revs_now))
            check("新版本数 = 基线 + 2", len(revs_now) == len(baseline_revs) + 2, str(revs_now))
            # 清理测试产生的 revision（保留 r1 基线）
            for r in db.query(OntologySchemaRevision).filter(OntologySchemaRevision.company_id == cid).all():
                if r.revision not in baseline_revs:
                    db.delete(r)
            db.commit()

            print("\n=== 写入型动作落库 ===")
            res = call_function("create_workorder", title="持久化回归测试工单", priority="high")
            wid = res.get("created")
            check("create_workorder 返回 id", bool(wid), str(res))
            db2 = SessionLocal()
            row = db2.query(OntologyObjectRow).filter_by(type="WorkOrder", object_id=wid).first()
            check("新建工单已落库", row is not None)
            # 清理测试工单及其关系，避免残留导致下次运行失败
            row = db2.query(OntologyObjectRow).filter_by(type="WorkOrder", object_id=wid).first()
            if row:
                db2.delete(row)
            db2.query(OntologyLinkRow).filter(OntologyLinkRow.source_id == wid).delete()
            if row or True:
                db2.commit()
            db2.close()

            print("\n=== 重启不丢（重新开 session 仍可读到种子）===")
            db3 = SessionLocal()
            check("重启后 Order 仍在 = 5", db3.query(OntologyObjectRow).filter_by(company_id=cid, type="Order").count() == 5)
            db3.close()

            print("\n=== 内存注册表仍可用（兜底路径）===")
            check("ONTO['types'] 含 10 类（含核电巡检 4 类）", len(ONTO["types"]) == 10, str(len(ONTO["types"])))
            check("ONTO['links'] 含 32 条", len(ONTO.get("links", [])) == 32, str(len(ONTO.get("links", []))))
            check("call_function 可用", isinstance(call_function("draft_report", topic="x"), dict))
        finally:
            db.close()

    print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
    if FAIL:
        print("失败项：", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
