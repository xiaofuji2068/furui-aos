"""file / CSV 连接器验收（路线图第 3 步扩展：真实接入从 1 种扩到 2 种）。

相对 test_real_erp_drill.py（REST）的增量：
  1. 连接器类型 file：读取 base_dir 下的实体 CSV，按 mapping 归一化；
  2. 验证字符串 -> 类型转换（金额/数量/主键转为数值，日期保持文本）；
  3. 仍走生产接线 add_source -> pull_source（与 API /sync、bootstrap 门控同一函数）；
  4. 隔离临时库：monkeypatch data_gateway.ERP_DB_PATH，零污染共享库；
  5. 验证只读网关可读真实数据 + PII 脱敏 + 归因定位头号下滑客户；
  6. 守卫：不支持的类型（如 sap）仍被 pull_source 拒绝。

运行： backend 目录下  ./venv/Scripts/python.exe tests/test_file_connector.py
"""
from __future__ import annotations

import csv
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---- 0. 隔离临时库：必须在 import connector 之前打补丁 ----
_TMP = Path(tempfile.mkdtemp(prefix="drill_file_"))
_TMP_DB = _TMP / "erp_crm.db"
import app.data_gateway as dg  # noqa: E402

dg.ERP_DB_PATH = _TMP_DB
import app.connector as connector  # noqa: E402  —— 此时取到补丁值
import app.store_data_sources as sds  # noqa: E402
import app.data_gateway as _dg  # noqa: E402

connector.ERP_DB_PATH = _TMP_DB  # 防御性

PASS, FAIL = [], []


def check(name: str, ok: bool, extra: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  → ' + extra) if extra else ''}")


def _write_csv(path: Path, header, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def _build_csv_dir(base: Path) -> int:
    """写实体 CSV（异名字段头），并制造「远图智能」环比骤降。返回订单行数。"""
    # customers: 异名字段头
    _write_csv(base / "customers.csv",
               ["cust_id", "cust_name", "grade", "area", "sector", "contact", "phone", "rep_id", "since"],
               [
                   [1, "远图智能", "A", "华东", "装备制造", "周总", "13700001111", 1, "2023-03-11"],
                   [2, "海联医疗", "B", "华南", "医疗", "吴工", "13600002222", 1, "2023-05-02"],
                   [3, "鼎诚能源", "C", "华东", "能源", "郑主", "13500003333", 1, "2023-07-19"],
               ])
    # products
    _write_csv(base / "products.csv",
               ["pid", "pcode", "pname", "cat", "price", "cost"],
               [
                   [1, "P-01", "辐射监测数字孪生平台", "软件", 480000.0, 210000.0],
                   [2, "P-02", "VR 安全培训系统", "软件", 260000.0, 110000.0],
               ])
    # sales_reps
    _write_csv(base / "sales_reps.csv",
               ["rid", "rname", "area", "hired"],
               [[1, "李明", "华东", "2022-04-01"]])

    orders = []
    oid = 1

    def add(cid, pid, area, qty, amt, day):
        nonlocal oid
        orders.append([oid, f"SO-2026{day.replace('-', '')}{oid:04d}", cid, pid, 1, area, qty, amt, "已完成", day])
        oid += 1

    for i in range(20):
        add(1, 1, "华东", 1, 480000.0, f"2026-07-{i % 28 + 1:02d}")
    for i in range(10):
        add(2, 2, "华南", 1, 260000.0, f"2026-07-{i % 28 + 1:02d}")
    for i in range(10):
        add(3, 1, "华东", 1, 480000.0, f"2026-07-{i % 28 + 1:02d}")
    for i in range(4):
        add(1, 1, "华东", 1, 480000.0, f"2026-08-{i % 28 + 1:02d}")  # 远图智能 20 -> 4
    for i in range(10):
        add(2, 2, "华南", 1, 260000.0, f"2026-08-{i % 28 + 1:02d}")
    for i in range(10):
        add(3, 1, "华东", 1, 480000.0, f"2026-08-{i % 28 + 1:02d}")

    _write_csv(base / "orders.csv",
               ["oid", "so_no", "cid", "pid", "rid", "area", "qty", "amt", "st", "dt"], orders)
    return len(orders)


def main() -> int:
    base = _TMP / "erp_export"
    base.mkdir(parents=True, exist_ok=True)
    n_orders_expected = _build_csv_dir(base)

    ok_overall = True
    try:
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
        cfg = {"base_dir": str(base), "mapping": mapping}

        created = sds.add_source({
            "id": "file-erp-drill", "name": "CSV 文件源（演练）", "type": "file",
            "category": "文件", "desc": "演练用外部 ERP CSV 导出", "config": cfg,
        })
        check("add_source 注册 file 数据源成功", bool(created) and created["id"] == "file-erp-drill"
              and connector._CONNECTOR_TYPES == {"rest", "file"})

        res = sds.pull_source("file-erp-drill")
        check("pull_source 走真实同步且状态 connected",
              bool(res) and res.get("status") == "connected",
              f"records={res.get('records')} latency={res.get('latency_ms')}ms")

        # ① 真实数据经同一只读网关可见
        q = _dg.query("SELECT COUNT(*) AS c FROM orders")
        n = q["rows"][0]["c"]
        check("拉数后 orders 入表（真实 CSV 数据经网关可见）", n == n_orders_expected, f"{n} 笔 / 预期 {n_orders_expected}")

        # ② 字段映射 + 类型转换生效
        qn = _dg.query("SELECT name, level, region, owner_rep_id FROM customers WHERE id=1")
        row = qn["rows"][0]
        check("字段映射+类型转换生效", row["name"] == "远图智能" and row["level"] == "A"
              and row["region"] == "华东" and isinstance(row["owner_rep_id"], int),
              f"{row}")

        # ③ PII 脱敏在真实数据上照样生效
        qc = _dg.query("SELECT name, contact_phone FROM customers WHERE id=1")
        phone = qc["rows"][0]["contact_phone"]
        check("PII 脱敏在真实数据上照样生效", phone != "13700001111" and "****" in phone, phone)

        # ④ 真实数据可定位头号下滑客户 → 闭环可触发建单
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

        # ⑤ 守卫：不支持的类型（如 sap）仍被拒绝
        sds.add_source({"id": "bad-type", "name": "不支持类型", "type": "sap",
                        "config": {"base_dir": str(base)}})
        bad = sds.pull_source("bad-type")
        check("不支持的连接器类型被拒绝（守卫仍有效）",
              bool(bad) and bad.get("status") == "error", f"status={bad.get('status')}")
    except Exception as e:  # noqa: BLE001
        check(f"演练执行未抛异常（{e}）", False)
        ok_overall = False
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)

    print(f"\nPASS {len(PASS)} / FAIL {len(FAIL)} / SKIP 0")
    return 1 if (FAIL or not ok_overall) else 0


if __name__ == "__main__":
    sys.exit(main())
