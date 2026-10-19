"""最小真实连接器验收（路线图第 2 步）。

验证：连接器把真实 REST JSON 物化进 erp_crm.db 后——
  1. 同一只读网关 data_gateway.query()（销售主线用的就是它）能读到真实数据；
  2. PII 脱敏（contact_phone）在真实数据上照样生效；
  3. 真实数据上能定位头号下滑客户 → 销售归因主线可触发审批建单（闭环）。

全程不连外网：用本地 http.server 提供 fixture；不调 init_all，不依赖 PG。
结束时 init_erp_db(force=True) 还原 mock，避免污染共享的 erp_crm.db。

运行： backend 目录下  ./venv/Scripts/python.exe tests/test_connector.py
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.connector import sync_source                     # noqa: E402
from app.data_gateway import init_erp_db, query as gw_query  # noqa: E402

PASS, FAIL = [], []


def check(name: str, ok: bool, extra: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  → ' + extra) if extra else ''}")


# ---------- 真实数据 fixture：刻意制造「真实客户甲」的环比骤降 ----------
_FIXTURE = None


def _build_fixture() -> dict:
    customers = [
        {"id": 1, "name": "真实客户甲", "level": "A", "region": "华东", "industry": "装备制造",
         "contact_name": "陈总", "contact_phone": "13812345678", "owner_rep_id": 1, "created_at": "2023-03-11"},
        {"id": 2, "name": "真实客户乙", "level": "B", "region": "华南", "industry": "电子",
         "contact_name": "李工", "contact_phone": "13923456789", "owner_rep_id": 1, "created_at": "2023-05-02"},
        {"id": 3, "name": "真实客户丙", "level": "C", "region": "华东", "industry": "能源",
         "contact_name": "王主", "contact_phone": "13734567890", "owner_rep_id": 1, "created_at": "2023-07-19"},
    ]
    products = [
        {"id": 1, "code": "P-01", "name": "辐射监测数字孪生平台", "category": "软件", "unit_price": 480000.0, "cost": 210000.0},
        {"id": 2, "code": "P-02", "name": "VR 安全培训系统", "category": "软件", "unit_price": 260000.0, "cost": 110000.0},
    ]
    reps = [{"id": 1, "name": "李明", "region": "华东", "hire_date": "2022-04-01"}]
    orders, oid = [], 1
    for i in range(28):   # 2026-07 甲 28 单大额
        orders.append({"id": oid, "order_no": f"SO-202607{i:04d}", "customer_id": 1, "product_id": 1,
                       "rep_id": 1, "region": "华东", "qty": 1, "amount": 480000.0, "status": "已完成",
                       "order_date": f"2026-07-{i % 28 + 1:02d}"}); oid += 1
    for i in range(10):   # 2026-07 乙/丙 各 10 单
        orders.append({"id": oid, "order_no": f"SO-202607{i:04d}", "customer_id": 2, "product_id": 2,
                       "rep_id": 1, "region": "华南", "qty": 1, "amount": 260000.0, "status": "已完成",
                       "order_date": f"2026-07-{i % 28 + 1:02d}"}); oid += 1
    for i in range(10):
        orders.append({"id": oid, "order_no": f"SO-202607{i:04d}", "customer_id": 3, "product_id": 1,
                       "rep_id": 1, "region": "华东", "qty": 1, "amount": 480000.0, "status": "已完成",
                       "order_date": f"2026-07-{i % 28 + 1:02d}"}); oid += 1
    for i in range(6):    # 2026-08 甲 骤降至 6 单
        orders.append({"id": oid, "order_no": f"SO-202608{i:04d}", "customer_id": 1, "product_id": 1,
                       "rep_id": 1, "region": "华东", "qty": 1, "amount": 480000.0, "status": "已完成",
                       "order_date": f"2026-08-{i % 28 + 1:02d}"}); oid += 1
    for i in range(10):   # 2026-08 乙/丙 各 10 单（稳定）
        orders.append({"id": oid, "order_no": f"SO-202608{i:04d}", "customer_id": 2, "product_id": 2,
                       "rep_id": 1, "region": "华南", "qty": 1, "amount": 260000.0, "status": "已完成",
                       "order_date": f"2026-08-{i % 28 + 1:02d}"}); oid += 1
    for i in range(10):
        orders.append({"id": oid, "order_no": f"SO-202608{i:04d}", "customer_id": 3, "product_id": 1,
                       "rep_id": 1, "region": "华东", "qty": 1, "amount": 480000.0, "status": "已完成",
                       "order_date": f"2026-08-{i % 28 + 1:02d}"}); oid += 1
    return {"customers": customers, "products": products, "sales_reps": reps, "orders": orders}


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(_FIXTURE).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main() -> int:
    global _FIXTURE
    _FIXTURE = _build_fixture()
    # 起点：先还原成 mock 基线，保证本测试不受其它脚本残留影响
    init_erp_db(force=True)

    server = HTTPServer(("127.0.0.1", 0), _FixtureHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        source = {
            "id": "demo-erp", "type": "rest", "status": "connected",
            "config": {"endpoint": f"http://127.0.0.1:{port}/erp", "method": "GET"},
        }
        res = sync_source("demo-erp", source)
        check("sync 成功且状态 connected", res.get("ok") and res.get("status") == "connected",
              f"records={res.get('records')}")

        # ① 真实数据经同一只读网关可见
        q = gw_query("SELECT COUNT(*) AS c FROM orders")
        n = q["rows"][0]["c"]
        check("拉数后 orders 入表（真实数据经网关可见）", n == len(_FIXTURE["orders"]), f"{n} 笔")

        # ② PII 脱敏在真实数据上照样生效
        qc = gw_query("SELECT name, contact_phone FROM customers WHERE id=1")
        phone = qc["rows"][0]["contact_phone"]
        check("PII 脱敏在真实数据上照样生效", phone != "13812345678" and "****" in phone, phone)

        # ③ 真实数据上能定位头号下滑客户 → 归因主线可触发建单
        sql = (
            "SELECT c.name AS name, "
            "SUM(CASE WHEN substr(o.order_date,1,7)='2026-07' THEN o.amount ELSE 0 END) AS prev, "
            "SUM(CASE WHEN substr(o.order_date,1,7)='2026-08' THEN o.amount ELSE 0 END) AS curr "
            "FROM orders o JOIN customers c ON c.id=o.customer_id "
            "WHERE substr(o.order_date,1,7) IN ('2026-07','2026-08') "
            "GROUP BY c.id ORDER BY (prev-curr) DESC"
        )
        qr = gw_query(sql)
        top = qr["rows"][0]
        drop = (top["prev"] or 0) - (top["curr"] or 0)
        check("真实数据可定位头号下滑客户（闭环可触发建单）", top["name"] == "真实客户甲" and drop > 0,
              f"{top['name']} 降幅 {drop}")
    except Exception as e:  # noqa: BLE001
        check(f"测试执行未抛异常（{e}）", False)
    finally:
        server.shutdown()
        # 终点：还原 mock，避免污染共享的 erp_crm.db，影响后续脚本
        init_erp_db(force=True)

    print(f"\nPASS {len(PASS)} / FAIL {len(FAIL)} / SKIP 0")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
