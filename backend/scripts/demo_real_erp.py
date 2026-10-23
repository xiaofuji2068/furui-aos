"""标准 ERP 对接 · 本地 Demo（无需真实端点即可验证完整接线）。

做什么：
  1. 起一个本地 mock「标准 ERP（用友 U8 风格）」REST 服务，返回**异名字段** JSON；
  2. 读取 scripts/erp_source_template.json 的字段映射（即真实对接时你要填的那份）；
  3. 走生产接线 connector.sync_source（与 API /sync、bootstrap 门控同一函数）；
  4. 经**只读网关** data_gateway.query() 验证：真实数据可见 + PII 脱敏 + 归因定位头号下滑客户
     （证明销售主线闭环可触发建单）。

安全：全程使用临时库（monkeypatch ERP_DB_PATH），**绝不触碰 backend/data/erp_crm.db**。
目的：让你在没有真实 ERP 凭证时，也能跑通「模板映射 → 物化 → 网关 → 脱敏 → 归因」全链路，
      确认映射写对后，把 endpoint 换成真实地址 + --yes 即可上真数据。

运行： backend 目录下  ./venv/Scripts/python.exe scripts/demo_real_erp.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---- 0. 隔离临时库：必须在 import connector 之前打补丁 ----
_TMP = Path(tempfile.mkdtemp(prefix="demo_erp_"))
_TMP_DB = _TMP / "erp_crm.db"
import app.data_gateway as dg  # noqa: E402

dg.ERP_DB_PATH = _TMP_DB
import app.connector as connector  # noqa: E402
import app.data_gateway as _dg  # noqa: E402

connector.ERP_DB_PATH = _TMP_DB  # 确保 materialize 用临时库

_DEMO_TOKEN = "demo-token"


def _build_fixture() -> dict:
    """用友 U8 风格异名字段：cCusCode / cInvCode / cOrderNo / iQty / fAmount ..."""
    customers = [
        {"cCusCode": 1, "cCusName": "远图智能", "cCusGrade": "A", "cProvince": "华东", "cTrade": "装备制造",
         "cConPerson": "周总", "cConPhone": "13700001111", "cPersonCode": 1, "dCusReg": "2023-03-11"},
        {"cCusCode": 2, "cCusName": "海联医疗", "cCusGrade": "B", "cProvince": "华南", "cTrade": "医疗",
         "cConPerson": "吴工", "cConPhone": "13600002222", "cPersonCode": 1, "dCusReg": "2023-05-02"},
        {"cCusCode": 3, "cCusName": "鼎诚能源", "cCusGrade": "C", "cProvince": "华东", "cTrade": "能源",
         "cConPerson": "郑主", "cConPhone": "13500003333", "cPersonCode": 1, "dCusReg": "2023-07-19"},
    ]
    products = [
        {"iAutoID": 1, "cInvCode": "P-01", "cInvName": "辐射监测数字孪生平台", "cGroupName": "软件", "iUnitPrice": 480000.0, "iCost": 210000.0},
        {"iAutoID": 2, "cInvCode": "P-02", "cInvName": "VR 安全培训系统", "cGroupName": "软件", "iUnitPrice": 260000.0, "iCost": 110000.0},
    ]
    reps = [{"cPersonCode": 1, "cPersonName": "李明", "cDeptName": "华东", "dHireDate": "2022-04-01"}]

    orders, oid = [], 1

    def add(cid, pid, area, qty, amt, day):
        nonlocal oid
        orders.append({"iSOID": oid, "cOrderNo": f"SO-2026{day.replace('-', '')}{oid:04d}", "cCusCode": cid,
                       "cInvCode": pid, "cPersonCode": 1, "cWhName": area, "iQty": qty,
                       "fAmount": amt, "cState": "已完成", "dDate": day})
        oid += 1

    # 2026-07 基线月
    for i in range(20):
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
    def do_GET(self):
        if self.headers.get("Authorization") != f"Bearer {_DEMO_TOKEN}":
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

    # 读取模板映射（真实对接时你要填的那份）
    tpl = json.loads((Path(__file__).resolve().parent / "erp_source_template.json").read_text(encoding="utf-8"))
    mapping = {k: v for k, v in tpl.get("mapping", {}).items() if not k.startswith("_")}

    server = HTTPServer(("127.0.0.1", 0), _ErpHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        cfg = {
            "endpoint": f"http://127.0.0.1:{port}/erp",
            "method": "GET",
            "auth": {"type": "bearer", "token": _DEMO_TOKEN},
            "mapping": mapping,
            "retries": 1, "backoff_sec": 0.01,
        }
        source = {"id": "demo-erp", "name": "标准 ERP 模板 Demo", "type": "rest", "config": cfg}
        res = connector.sync_source("demo-erp", source)
        print(f"[1] 同步结果：ok={res.get('ok')} status={res.get('status')} "
              f"records={res.get('records')} counts={res.get('counts')} latency={res.get('latency_ms')}ms")
        if not res.get("ok"):
            print(f"    失败：{res.get('error')}")
            return 1

        # ① 真实数据经同一只读网关可见
        q = _dg.query("SELECT COUNT(*) AS c FROM orders")
        print(f"[2] 只读网关可读真实数据：orders 入表 {q['rows'][0]['c']} 笔")

        # ② PII 脱敏在真实数据上照样生效
        qc = _dg.query("SELECT name, contact_phone FROM customers WHERE id=1")
        row = qc["rows"][0]
        print(f"[3] PII 脱敏生效：{row['name']} 电话 {row['contact_phone']}（原始 13700001111）")

        # ③ 真实数据上定位头号下滑客户 → 销售归因主线可触发审批建单（闭环）
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
        print(f"[4] 归因定位头号下滑客户：{top['name']}（7月 {top['prev']} → 8月 {top['curr']}，降幅 {drop}）"
              f" → 销售主线可触发审批建单")

        print("\n✅ 模板映射 + 物化 + 只读网关 + 脱敏 + 归因闭环全部跑通。")
        print("   拿到真实 ERP 端点/凭证后：把 erp_source_template.json 的 endpoint/auth 填好，")
        print("   运行  python scripts/sync_real_erp.py --config scripts/erp_source_template.json --yes")
        return 0
    finally:
        server.shutdown()
        import shutil
        shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
