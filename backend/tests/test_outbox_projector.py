"""3.X.2 动作表 #2：Outbox + Projector（图谱 20-04 权威写链 / 图快照）。

验收口径（差距清单原文）：
    「tests/test_outbox_projector.py 通过：写 100 条 Link，5s 内图快照全量可见」

锁定：
- 每次写 Object/Link（走 ontology._upsert_db_object / _upsert_db_link 统一入口）
  同步落一条 OntologyOutboxRow（status=pending，与写入同事务）
- GET /api/ontology/snapshot 读取时自动投影：pending → GraphSnapshot 全量重建
- 写 100 条 Link 后调用 snapshot，link_count 增量可见（验收核心）
- POST /api/ontology/snapshot/project 手动触发投影（权限 knowledge:manage）
- outbox 行消费后 status=processed（可审计、可重放）

依赖：admin / sales 用户存在（bootstrap 默认种子）。

运行：
    backend/venv/Scripts/python.exe tests/test_outbox_projector.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Company  # noqa: E402
from app.models_ontology import (  # noqa: E402
    OntologyGraphSnapshot,
    OntologyLinkRow,
    OntologyObjectRow,
    OntologyOutboxRow,
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
        # 清理历史测试残留（幂等；lifespan 已建表）
        db.query(OntologyLinkRow).filter(OntologyLinkRow.type == "TestLink").delete(synchronize_session=False)
        db.query(OntologyObjectRow).filter(OntologyObjectRow.type == "TestNode").delete(synchronize_session=False)
        db.query(OntologyOutboxRow).filter(OntologyOutboxRow.obj_type == "TestLink").delete(synchronize_session=False)
        db.commit()

        baseline_links = db.query(OntologyLinkRow).filter(OntologyLinkRow.company_id == cid).count()
        baseline_nodes = db.query(OntologyObjectRow).filter(OntologyObjectRow.company_id == cid).count()
        baseline_outbox = db.query(OntologyOutboxRow).count()
        print(f"baseline: links={baseline_links} nodes={baseline_nodes} outbox={baseline_outbox}")

        print("\n=== 未登录访问被拒 ===")
        r = c.get("/api/ontology/snapshot")
        check("GET snapshot 无 token 401", r.status_code == 401, str(r.status_code))
        r = c.post("/api/ontology/snapshot/project")
        check("POST project 无 token 401", r.status_code == 401, str(r.status_code))

        print("\n=== admin 登录 ===")
        admin_tok = _login(c, "admin", "123456")
        check("admin 登录成功", bool(admin_tok))
        HA = {"Authorization": f"Bearer {admin_tok}"} if admin_tok else {}
        if not admin_tok:
            print("  无法继续：admin 登录失败")
            print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
            return 1

        # ---- 核心：写 100 条 Link（走统一写入口，同步落 outbox）----
        print("\n=== 写 100 条 TestLink（outbox 落账） ===")
        from app.ontology import OntologyLink, _upsert_db_link

        t0 = time.time()
        for i in range(100):
            src = f"N{i:03d}"
            dst = f"N{i + 1:03d}"
            link = OntologyLink(type="TestLink", source_id=src, target_id=dst,
                                properties={"idx": i, "ts": time.time()})
            _upsert_db_link(db, link, company_id=cid)
        db.commit()
        write_s = time.time() - t0
        print(f"  写 100 条耗时 {write_s:.2f}s")

        outbox_pending = db.query(OntologyOutboxRow).filter(
            OntologyOutboxRow.status == "pending",
            OntologyOutboxRow.obj_type == "TestLink").count()
        check("100 条 Link 全部落 outbox(pending)", outbox_pending == 100, str(outbox_pending))

        links_now = db.query(OntologyLinkRow).filter(
            OntologyLinkRow.type == "TestLink").count()
        check("DB 中 TestLink = 100", links_now == 100, str(links_now))

        # ---- 验收核心：5s 内图快照全量可见 ----
        print("\n=== GET /api/ontology/snapshot（读取即投影） ===")
        snap_t0 = time.time()
        r = c.get("/api/ontology/snapshot", headers=HA)
        snap_s = time.time() - snap_t0
        check("GET snapshot 200", r.status_code == 200, str(r.status_code))
        check("读取耗时 < 5s（验收口径）", snap_s < 5, f"{snap_s:.2f}s")
        body = r.json().get("data", r.json()) if r.status_code == 200 else {}
        check("快照 link_count 含 100 条新增",
              body.get("link_count", 0) >= baseline_links + 100,
              f"baseline={baseline_links} now={body.get('link_count')}")
        check("快照 edges 数 = link_count",
              len(body.get("edges", [])) == body.get("link_count", -1),
              f"edges={len(body.get('edges', []))}")
        check("快照含 nodes 与 edges 字段",
              "nodes" in body and "edges" in body, str(sorted(body.keys())))
        check("快照含 revision 字段", "revision" in body, str(body.get("revision")))
        check("快照 pending=0（已投影）", body.get("pending", -1) == 0,
              f"pending={body.get('pending')}")

        # outbox 已消费
        db.expire_all()
        processed = db.query(OntologyOutboxRow).filter(
            OntologyOutboxRow.status == "processed",
            OntologyOutboxRow.obj_type == "TestLink").count()
        check("outbox 100 条全部 processed", processed == 100, str(processed))

        # snapshot 落库
        snap_row = db.query(OntologyGraphSnapshot).filter_by(
            company_id=cid, snapshot_key="graph-full").order_by(
            OntologyGraphSnapshot.id.desc()).first()
        check("GraphSnapshot 已落库", snap_row is not None)
        if snap_row:
            check("snapshot link_count 与 DB 一致",
                  snap_row.link_count == baseline_links + 100,
                  f"{snap_row.link_count} vs {baseline_links + 100}")

        # ---- 幂等：无 pending 时投影跳过 ----
        print("\n=== 幂等性：再投影一次 ===")
        r2 = c.post("/api/ontology/snapshot/project", headers=HA)
        check("POST project 200", r2.status_code == 200, str(r2.status_code))
        p2 = r2.json().get("data", r2.json()) if r2.status_code == 200 else {}
        check("无 pending 时 projected=0", p2.get("projected", -1) == 0, str(p2))

        # ---- 权限：sales 可读 snapshot，不可 project ----
        print("\n=== sales 权限 ===")
        sales_tok = _login(c, "sales", "123456")
        check("sales 登录成功", bool(sales_tok))
        HS = {"Authorization": f"Bearer {sales_tok}"} if sales_tok else {}
        if sales_tok:
            r3 = c.get("/api/ontology/snapshot", headers=HS)
            check("sales GET snapshot 200（datasource:view）",
                  r3.status_code == 200, str(r3.status_code))
            r4 = c.post("/api/ontology/snapshot/project", headers=HS)
            check("sales POST project 403（knowledge:manage 缺失）",
                  r4.status_code == 403, str(r4.status_code))

        # ---- 清理测试数据（保留 baseline 与业务快照）----
        print("\n（清理测试产生的 Link / Node / Outbox / Snapshot 行）")
        db.query(OntologyLinkRow).filter(
            OntologyLinkRow.type == "TestLink").delete(synchronize_session=False)
        db.query(OntologyObjectRow).filter(
            OntologyObjectRow.type == "TestNode").delete(synchronize_session=False)
        db.query(OntologyOutboxRow).filter(
            OntologyOutboxRow.obj_type == "TestLink").delete(synchronize_session=False)
        db.commit()
        # 快照回滚为全量投影（不含 TestLink）
        from app.ontology import project_outbox

        project_outbox(db, force=True, company_id=cid)
        snap_after = db.query(OntologyGraphSnapshot).filter_by(
            company_id=cid, snapshot_key="graph-full").order_by(
            OntologyGraphSnapshot.id.desc()).first()
        check("清理后快照 link_count 回到 baseline",
              snap_after is not None and snap_after.link_count == baseline_links,
              f"now={snap_after.link_count if snap_after else None}")

    print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
    if FAIL:
        print("失败：", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
