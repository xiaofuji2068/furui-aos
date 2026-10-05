"""TASK-010 数据资产模型 + Connector Catalog（图谱 10-01/10-02）。

锁定：
- 新建资产（绑定 erp 源）→ 列表可见，source_name/source_status 来自数据源
- source_id 不存在 → 400
- sync → 行数增长、版本 v1→v2、health=healthy、last_sync_at 更新
- lineage → source→datasets 血缘链
- 权限：未登录 401；datasource:view 可读
- 清理：删除资产后列表回到起点

运行：
    backend/venv/Scripts/python.exe tests/test_data_assets.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client: TestClient | None = None
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
    global client
    with TestClient(app) as c:
        client = c
        h = bearer("admin")

        # ---- 基线：清理可能残留的测试资产 ----
        r0 = client.get("/api/data-assets", headers=h)
        baseline = r0.json()["data"].get("total", 0)
        check("列表接口 200", r0.status_code == 200, r0.text[:120])

        print("\n=== 新建资产（绑定 erp 源）===")
        r = client.post("/api/data-assets", headers=h, json={
            "name": "测试-ERP订单资产", "source_id": "erp", "kind": "table",
            "entity": "orders", "row_count": 1200, "version": "v1",
            "fields": ["order_id", "customer_id", "amount"],
            "lineage": {"upstream": ["erp:orders"], "downstream": ["kpi:orders"]},
        })
        check("POST 创建 200", r.status_code == 200, r.text[:200])
        asset = r.json()["data"]
        check("创建返回 name", asset.get("name") == "测试-ERP订单资产", str(asset)[:200])
        check("source_name 来自数据源", asset.get("source_name") == "ERP 系统", str(asset.get("source_name")))
        check("source_status 已连接", asset.get("source_status") == "connected", str(asset.get("source_status")))
        check("row_count=1200", asset.get("row_count") == 1200)
        check("fields 3 字段", isinstance(asset.get("fields"), list) and len(asset["fields"]) == 3)
        check("health=healthy", asset.get("health_status") == "healthy")
        asset_id = asset["id"]

        print("\n=== 列表 / 血缘 ===")
        r = client.get("/api/data-assets", headers=h)
        items = r.json()["data"].get("items", [])
        check("列表包含新建资产", any(a["id"] == asset_id for a in items), str(items)[:200])
        r = client.get("/api/data-assets/lineage", headers=h)
        lin = r.json()["data"].get("items", [])
        erp_lin = next((x for x in lin if x["source_id"] == "erp"), None)
        check("血缘含 erp 源", erp_lin is not None, str(lin)[:200])
        check("血缘下含该资产", bool(erp_lin) and any(d["id"] == asset_id for d in erp_lin.get("datasets", [])))

        print("\n=== 同步（模拟）===")
        r = client.post(f"/api/data-assets/{asset_id}/sync", headers=h)
        check("sync 200", r.status_code == 200, r.text[:200])
        s = r.json()["data"]
        check("sync 后行数增长", s.get("row_count", 0) > 1200, f"row_count={s.get('row_count')}")
        check("sync 后版本 v2", s.get("version") == "v2", str(s.get("version")))
        check("sync 后 health=healthy", s.get("health_status") == "healthy")
        check("sync 后 last_sync_at 存在", bool(s.get("last_sync_at")))

        print("\n=== 校验分支 ===")
        r = client.post("/api/data-assets", headers=h, json={
            "name": "坏源资产", "source_id": "no_such_source", "entity": "x",
        })
        check("source 不存在 → 400", r.status_code == 400, r.text[:200])
        r = client.post("/api/data-assets", headers=h, json={
            "name": "", "source_id": "erp",
        })
        check("name 为空 → 400", r.status_code == 400, r.text[:200])
        r = client.delete("/api/data-assets/999999", headers=h)
        check("删除不存在 → 404", r.status_code == 404, r.text[:200])

        print("\n=== 权限 ===")
        r = client.get("/api/data-assets")
        check("未登录 GET → 401/403", r.status_code in (401, 403), str(r.status_code))
        hs = bearer("sales")
        r = client.get("/api/data-assets", headers=hs)
        check("sales GET 200（datasource:view）", r.status_code == 200, r.text[:120])

        print("\n=== 清理 ===")
        r = client.delete(f"/api/data-assets/{asset_id}", headers=h)
        check("删除资产 200", r.status_code == 200, r.text[:200])
        r = client.get("/api/data-assets", headers=h)
        check("清理后 total 回到基线", r.json()["data"].get("total", 0) == baseline,
              f"now={r.json().get('total')}, baseline={baseline}")

        print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
        sys.exit(0 if not FAIL else 1)


if __name__ == "__main__":
    main()

