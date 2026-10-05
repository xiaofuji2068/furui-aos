# -*- coding: utf-8 -*-
"""TASK-014：Logic 图 seed / 读回 / 节点编辑 / 激活 / 引擎读图执行。

覆盖：
1. seed 幂等创建两张图（sales-drop / inspection-anomaly，各 6 节点，active）
2. get_active_plan 与代码 PLAN 结构一致（seq/kind/tool）
3. 节点编辑（label/tool/params）落库可读
4. 激活切换状态
5. 引擎读 DB 图计划，行为与代码 PLAN 一致
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal, engine, Base
from app import models  # noqa: F401
from app import models_ai  # noqa: F401
from app.logic import seed_graphs, list_graphs, get_graph, update_node, activate_graph, get_active_plan
from app.mainline import PLAN
from app.models import Company

PASS: list = []
FAIL: list = []


def check(name, cond):
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}")


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)
    try:
        c = db.query(Company).order_by(Company.id).first()
        cid = c.id if c else 1

        created = seed_graphs(db, cid)
        check("seed 创建 2 张图（或已幂等存在）", len(created) in (0, 2))
        items = list_graphs(db, cid)
        check("图列表 2 张", len(items) == 2)
        codes = {i["code"] for i in items}
        check("图 code 集合", codes == {"sales-drop", "inspection-anomaly"})
        check("图均 active", all(i["status"] == "active" for i in items))
        check("图各 6 节点", all(i["node_count"] == 6 for i in items))

        again = seed_graphs(db, cid)
        check("seed 幂等（再次为空）", again == [])

        plan = get_active_plan(db, cid, "sales-analyst")
        check("读图计划非空", plan is not None)
        check("seq 序列 1..6", [p["seq"] for p in plan] == [1, 2, 3, 4, 5, 6])
        check("step4 工具=analyze_sales_drop", plan[3]["tool"] == "analyze_sales_drop")
        check("step6 工具=create_sales_task", plan[5]["tool"] == "create_sales_task")
        same = all(p["seq"] == cp["seq"] and p["kind"] == cp["kind"]
                   and p.get("tool", "") == cp.get("tool", "")
                   for p, cp in zip(plan, PLAN))
        check("图计划与代码 PLAN 结构一致", same)

        g0 = list_graphs(db, cid)[0]
        detail = get_graph(db, cid, g0["id"])
        nid = detail["nodes"][1]["id"]
        updated = update_node(db, cid, nid, {"label": "查询 CRM 客户（已启用）"})
        check("节点更新返回图", updated is not None)
        node = [n for n in updated["nodes"] if n["id"] == nid][0]
        check("节点 label 已改", node["label"] == "查询 CRM 客户（已启用）")

        target = items[1]["id"]
        g = activate_graph(db, cid, target)
        check("激活返回图", g is not None and g["status"] == "active")
        items2 = list_graphs(db, cid)
        check("激活后目标图 active", g["status"] == "active")
        t2 = list_graphs(db, cid)
        tg = [i for i in t2 if i["id"] == target][0]
        check("目标图状态持久", tg["status"] == "active")
        check("另一链路图仍 active（互不影响）",
              len([i for i in t2 if i["code"] == "sales-drop" and i["status"] == "active"]) == 1)

        db2 = SessionLocal()
        try:
            gplan = get_active_plan(db2, cid, "sales-analyst")
        finally:
            db2.close()
        check("引擎读图计划 6 步", len(gplan or []) == 6 and gplan is not None)
        check("引擎读图 step5 report", gplan[4]["kind"] == "report")
    finally:
        db.close()

    print(f"\nRESULT: PASS {len(PASS)} / FAIL {len(FAIL)} / SKIP 0")
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
