"""真实 ERP 源接入演练（路线图第 3 步，安全隔离版）。

相对 test_connector.py 的增量覆盖（前者只测连接器单元，直接调 sync_source、无鉴权、无映射）：
  1. 走「数据源目录」生产接线：store_data_sources.add_source -> pull_source
     —— 这正是 API POST /api/data-sources/{id}/sync 与 bootstrap 的
        FURUI_SYNC_ERP_SOURCE_ID 环境变量门控调用的同一函数；
  2. 验证鉴权：连接器带 Bearer Token，本地 ERP 服务校验，错 token 返回 401；
  3. 验证字段映射：ERP 返回的 JSON 字段名与表列不同，靠 config.mapping 归一化；
  4. 隔离临时库：monkeypatch data_gateway.ERP_DB_PATH 到临时文件，
     绝不污染共享的 backend/data/erp_crm.db（也不调 init_erp_db）；
  5. 验证只读网关可读真实数据 + PII 脱敏 + 归因定位头号下滑客户（闭环可触发建单）；
  6. 负向用例：错 token 时 sync_source 返回 ok=False / error，不破坏既有数据。

运行： backend 目录下  ./venv/Scripts/python.exe tests/test_real_erp_drill.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---- 0. 隔离临时库：必须在 import connector 之前打补丁 ----
_TMP = Path(tempfile.mkdtemp(prefix="drill_erp_"))
_TMP_DB = _TMP / "erp_crm.db"
import app.data_gateway as dg  # noqa: E402

dg.ERP_DB_PATH = _TMP_DB
import app.connector as connector  # noqa: E402  —— 此时 from .data_gateway import ERP_DB_PATH 取到补丁值
import app.store_data_sources as sds  # noqa: E402
import app.data_gateway as _dg  # noqa: E402

connector.ERP_DB_PATH = _TMP_DB  # 防御性：确保 materialize 用临时库

PASS, FAIL = [], []


def check(name: str, ok: bool, extra: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  → ' + extra) if extra else ''}")


# ---- 1. 模拟「真实外部 ERP」REST 服务：Bearer 鉴权 + 异名字段 ----
_TOKEN = "drill-secret-2026"


def _build_fixture() -> dict:
    """ERP 返回的 JSON 字段名刻意与表列不同，强制走字段映射。"""
    customers = [
        {"cust_id": 1, "cust_name": "远图智能", "grade": "A", "area": "华东", "sector": "装备制造",
         "contact": "周总", "phone": "13700001111", "rep_id": 1, "since": "2023-03-11"},
        {"cust_id": 2, "cust_name": "海联医疗", "grade": "B", "area": "华南", "sector": "医疗",
         "contact": "吴工", "phone": "13600002222", "rep_id": 1, "since": "2023-05-02"},
        {"cust_id": 3, "cust_name": "鼎诚能源", "grade": "C", "area": "华东", "sector": "能源",
         "contact": "郑主", "phone": "13500003333", "rep_id": 1, "since": "2023-07-19"},
    ]
    products = [
        {"pid": 1, "pcode": "P-01", "pname": "辐射监测数字孪生平台", "cat": "软件", "price": 480000.0, "cost": 210000.0},
        {"pid": 2, "pcode": "P-02", "pname": "VR 安全培训系统", "cat": "软件", "price": 260000.0, "cost": 110000.0},
    ]
    reps = [{"rid": 1, "rname": "李明", "area": "华东", "hired": "2022-04-01"}]

    orders, oid = [], 1
    def add(cid, pid, area, qty, amt, day):
        nonlocal oid
        orders.append({"oid": oid, "so_no": f"SO-2026{day.replace('-', '')}{oid:04d}",
                       "cid": cid, "pid": pid, "rid": 1, "area": area, "qty": qty,
                       "amt": amt, "st": "已完成", "dt": day})
        oid += 1

    # 2026-07 基线月
    for i in range(20):                       # 远图智能 20 单大额
        add(1, 1, "华东", 1, 480000.0, f"2026-07-{i % 28 + 1:02d}")
    for i in range(10):
        add(2, 2, "华南", 1, 260000.0, f"2026-07-{i % 28 + 1:02d}")
    for i in range(10):
        add(3, 1, "华东", 1, 480000.0, f"2026-07-{i % 28 + 1:02d}")
    # 2026-08 分析月：远图智能骤降 20 -> 4（主因），海联/鼎诚稳定
    for i in range(4):
        add(1, 1, "华东", 1, 480000.0, f"2026-08-{i % 28 + 1:02d}")
    for i in range(10):
        add(2, 2, "华南", 1, 260000.0, f"2026-08-{i % 28 + 1:02d}")
    for i in range(10):
        add(3, 1, "华东", 1, 480000.0, f"2026-08-{i % 28 + 1:02d}")
    return {"customers": customers, "products": products, "sales_reps": reps, "orders": orders}


class _ErpHandler(BaseHTTPRequestHandler):
    def _auth_ok(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {_TOKEN}"

    def do_GET(self):
        if not self._auth_ok():
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
            return
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
    n_orders_expected = len(_FIXTURE["orders"])

    server = HTTPServer(("127.0.0.1", 0), _ErpHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    ok_overall = True
    try:
        # ---- 字段映射：ERP 异名字段 -> 表列 ----
        mapping = {
            "customers": {"cust_id": "id", "cust_name": "name", "grade": "level", "area": "region",
                          "sector": "industry", "contact": "contact_name", "phone": "contact_phone",
                          "rep_id": "owner_rep_id", "since": "created_at"},
            "products": {"pid": "id", "pcode": "code", "pname": "name", "cat": "category",
                         "price": "unit_price", "cost": "cost"},
            "sales_reps": {"rid": "id", "rname": "name", "area": "region", "hired": "hire_date"},
            "orders": {"oid": "id", "so_no": "order_no", "cid": "customer_id", "pid": "product_id",
                       "rid": "rep_id", "area": "region", "qty": "qty", "amt": "amount",
                       "st": "status", "dt": "order_date"},
        }
        cfg = {
            "endpoint": f"http://127.0.0.1:{port}/erp",
            "method": "GET",
            "auth": {"type": "bearer", "token": _TOKEN},
            "mapping": mapping,
        }
        # 走生产接线：add_source -> pull_source（与 API /sync、bootstrap 门控同一函数）
        created = sds.add_source({
            "id": "real-erp-drill", "name": "真实 ERP（演练）", "type": "rest",
            "category": "业务系统", "desc": "演练用外部 ERP REST 源",
            "config": cfg,
        })
        check("add_source 注册 rest 数据源成功", bool(created) and created["id"] == "real-erp-drill")

        res = sds.pull_source("real-erp-drill")
        # pull_source 返回数据源对象，成功信号是 status=="connected"（内部 ok 不对外暴露）
        check("pull_source 走真实同步且状态 connected",
              bool(res) and res.get("status") == "connected",
              f"records={res.get('records')} latency={res.get('latency_ms')}ms")

        # ① 真实数据经同一只读网关可见
        q = _dg.query("SELECT COUNT(*) AS c FROM orders")
        n = q["rows"][0]["c"]
        check("拉数后 orders 入表（真实数据经网关可见）", n == n_orders_expected, f"{n} 笔 / 预期 {n_orders_expected}")

        # ② 字段映射生效：ERP 异名字段被正确写入表列
        qn = _dg.query("SELECT name, level, region FROM customers WHERE id=1")
        row = qn["rows"][0]
        check("字段映射生效（异名字段 -> 表列）",
              row["name"] == "远图智能" and row["level"] == "A" and row["region"] == "华东",
              f"{row}")

        # ③ PII 脱敏在真实数据上照样生效
        qc = _dg.query("SELECT name, contact_phone FROM customers WHERE id=1")
        phone = qc["rows"][0]["contact_phone"]
        check("PII 脱敏在真实数据上照样生效", phone != "13700001111" and "****" in phone, phone)

        # ④ 真实数据上能定位头号下滑客户 → 销售归因主线可触发审批建单（闭环）
        sql = (
            "SELECT c.name AS name, "
            "SUM(CASE WHEN substr(o.order_date,1,7)='2026-07' THEN o.amount ELSE 0 END) AS prev, "
            "SUM(CASE WHEN substr(o.order_date,1,7)='2026-08' THEN o.amount ELSE 0 END) AS curr "
            "FROM orders o JOIN customers c ON c.id=o.customer_id "
            "WHERE substr(o.order_date,1,7) IN ('2026-07','2026-08') "
            "GROUP BY c.id ORDER BY (prev-curr) DESC"
        )
        qr = _dg.query(sql)
        top = qr["rows"][0]
        drop = (top["prev"] or 0) - (top["curr"] or 0)
        check("真实数据可定位头号下滑客户（闭环可触发建单）",
              top["name"] == "远图智能" and drop > 0, f"{top['name']} 降幅 {drop}")

        # ⑤ 负向用例：错 token 时连接器应被网关 401 拒绝，sync_source 返回 error，不破坏既有数据
        sds.add_source({
            "id": "real-erp-badtoken", "name": "错误令牌源", "type": "rest",
            "config": {"endpoint": f"http://127.0.0.1:{port}/erp", "auth": {"type": "bearer", "token": "wrong"}},
        })
        bad = sds.pull_source("real-erp-badtoken")
        # 错 token → 401 → sync_source 捕获异常返回 error，pull_source 回写 status="error"
        check("错 token 被 401 拒绝且同步状态置为 error",
              bool(bad) and bad.get("status") == "error",
              f"status={bad.get('status')}")
        # 既有真实数据不应被错误同步破坏
        q_after = _dg.query("SELECT COUNT(*) AS c FROM orders")
        check("错误同步不破坏既有真实数据", q_after["rows"][0]["c"] == n_orders_expected,
              f"{q_after['rows'][0]['c']} 笔")
    except Exception as e:  # noqa: BLE001
        check(f"演练执行未抛异常（{e}）", False)
        ok_overall = False
    finally:
        server.shutdown()
        shutil.rmtree(_TMP, ignore_errors=True)

    print(f"\nPASS {len(PASS)} / FAIL {len(FAIL)} / SKIP 0")
    return 1 if (FAIL or not ok_overall) else 0


if __name__ == "__main__":
    sys.exit(main())
