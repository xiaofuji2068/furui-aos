"""连接器重试 / 退避验收（生产化加固，test_connector.py 的增量）。

覆盖：
  1. 5xx 瞬时错误：前 2 次 500、第 3 次 200 → 重试成功，请求次数 = 失败数 + 1；
  2. 4xx 鉴权错（401）：不重试，立即报错（请求次数 = 1）；
  3. 网络不可达 / 连接失败：重试耗尽后 sync_source 安全返回 error（不炸启动流程）。

不连外网：本地 http.server 模拟。

运行： backend 目录下  ./venv/Scripts/python.exe tests/test_connector_retry.py
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.connector import RestJsonConnector, sync_source  # noqa: E402

PASS, FAIL = [], []


def check(name: str, ok: bool, extra: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  → ' + extra) if extra else ''}")


# ---- 用例 1：前 fail_times 次 5xx，之后 200 ----
def _make_flaky_handler(fail_times: int):
    counter = {"n": 0}

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            counter["n"] += 1
            if counter["n"] <= fail_times:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error":"boom"}')
                return
            body = json.dumps({
                "orders": [{
                    "id": 1, "order_no": "SO-1", "customer_id": 1, "product_id": 1,
                    "rep_id": 1, "region": "华东", "qty": 1, "amount": 100.0,
                    "status": "已完成", "order_date": "2026-08-01",
                }]
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return _H, counter


class _UnauthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":"unauthorized"}')

    def log_message(self, *args):
        pass


def main() -> int:
    # 用例 1：5xx 重试成功
    _H, counter = _make_flaky_handler(fail_times=2)
    srv = HTTPServer(("127.0.0.1", 0), _H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        cfg = {"endpoint": f"http://127.0.0.1:{port}/erp", "method": "GET",
               "retries": 2, "backoff_sec": 0.01}
        c = RestJsonConnector(cfg)
        data = c.pull()
        check("5xx 后重试成功拉到数据", len(data.get("orders", [])) == 1,
              f"orders={len(data.get('orders', []))}")
        # 请求次数 = 失败 2 次 + 成功 1 次 = 3
        check("5xx 触发了 retries 次重试（请求数 = 失败数 + 1）",
              counter["n"] == 1 + 2, f"requests={counter['n']}")
    except Exception as e:  # noqa: BLE001
        check("5xx 重试用例未抛异常", False, str(e))
    finally:
        srv.shutdown()

    # 用例 2：401 不重试（立即报错，仅 1 次请求）
    ctr2 = {"n": 0}

    class _Count401(_UnauthHandler):
        def do_GET(self):
            ctr2["n"] += 1
            super().do_GET()

    srv2 = HTTPServer(("127.0.0.1", 0), _Count401)
    port2 = srv2.server_address[1]
    threading.Thread(target=srv2.serve_forever, daemon=True).start()
    try:
        cfg = {"endpoint": f"http://127.0.0.1:{port2}/erp", "method": "GET",
               "retries": 3, "backoff_sec": 0.01}
        c = RestJsonConnector(cfg)
        raised = False
        try:
            c.pull()
        except Exception:
            raised = True
        check("401 立即报错且未重试", raised and ctr2["n"] == 1,
              f"requests={ctr2['n']} raised={raised}")
    finally:
        srv2.shutdown()

    # 用例 3：网络不可达 → sync_source 安全返回 error（不抛、不炸）
    res = sync_source("bad-net", {
        "id": "bad-net", "type": "rest",
        "config": {"endpoint": "http://127.0.0.1:1/erp", "retries": 1,
                   "backoff_sec": 0.01, "timeout_sec": 1},
    })
    check("网络不可达时 sync_source 安全返回 error",
          res.get("ok") is False and res.get("status") == "error",
          f"error={res.get('error')}")

    print(f"\nPASS {len(PASS)} / FAIL {len(FAIL)} / SKIP 0")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
