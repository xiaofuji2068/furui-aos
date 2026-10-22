# -*- coding: utf-8 -*-
"""TASK-018-2 Watchdog 生产化：看门狗告警落 AuditLog 测试。

核心不变量：
  1. _watchdog_alerts 是纯决策函数 —— 给定探活结果，准确产出需要告警的条目
     （db_down / error_rate_high / edge_offline），不写库、不抛错。
  2. _emit_alert 把告警落 audit_logs（action=watchdog.alert, result=warning），
     失败静默、绝不连累 /api/health 本身。
  3. 冷却机制：同一类型告警在 WATCHDOG_ALERT_COOLDOWN_S 窗口内只落一次，防刷屏。
  4. /api/health 返回结构不变（新增告警是副作用，不影响响应体）。

运行：run_tests.py 强制 DATABASE_URL=furui_aios_test；本脚本自带兜底，可单独跑。
    backend/venv/Scripts/python.exe tests/test_watchdog_alert.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test",
)

import app.models  # noqa: E402
import app.models_ai  # noqa: E402
import app.models_release  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.api import health  # noqa: E402
from app.api.health import (  # noqa: E402
    _watchdog_alerts,
    _emit_alert,
    _ALERT_COOLDOWN,
    WATCHDOG_ALERT_COOLDOWN_S,
)
from app.models_ai import AuditLog  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")


def _keys(alerts):
    return {a["key"] for a in alerts}


def test_decision_db_down():
    print("[1] 纯决策：数据库失联 -> db_down")
    checks_bad = [{"name": "数据库", "status": "error", "detail": "连接失败：OperationalError"}]
    checks_ok = [{"name": "数据库", "status": "ok", "detail": "SQLite 连接正常"}]
    edge = {"ok": True, "stale_flipped_to_offline": 0}
    err = {"ok": True, "rate": 0.0}
    check("DB error 触发 db_down", "db_down" in _keys(_watchdog_alerts(checks_bad, edge, err)))
    check("DB ok 不触发 db_down", "db_down" not in _keys(_watchdog_alerts(checks_ok, edge, err)))


def test_decision_error_rate():
    print("[2] 纯决策：错误率超阈值 -> error_rate_high")
    checks = [{"name": "数据库", "status": "ok"}]
    edge = {"ok": True, "stale_flipped_to_offline": 0}
    check("rate=0.6 触发告警",
          "error_rate_high" in _keys(_watchdog_alerts(checks, edge, {"ok": True, "rate": 0.6, "total": 10, "errors": 6})))
    check("rate=0.1 不触发告警",
          "error_rate_high" not in _keys(_watchdog_alerts(checks, edge, {"ok": True, "rate": 0.1})))
    check("err 探测失败(ok=False) 不触发",
          "error_rate_high" not in _keys(_watchdog_alerts(checks, edge, {"ok": False, "rate": 0.9})))


def test_decision_edge_offline():
    print("[3] 纯决策：边缘站点掉线 -> edge_offline")
    checks = [{"name": "数据库", "status": "ok"}]
    err = {"ok": True, "rate": 0.0}
    check("flipped=2 触发告警",
          "edge_offline" in _keys(_watchdog_alerts(checks, {"ok": True, "stale_flipped_to_offline": 2}, err)))
    check("flipped=0 不触发告警",
          "edge_offline" not in _keys(_watchdog_alerts(checks, {"ok": True, "stale_flipped_to_offline": 0}, err)))


def test_emit_writes_audit():
    print("[4] 落库：emit 把告警写入 audit_logs（action=watchdog.alert, result=warning）")
    _ALERT_COOLDOWN.clear()
    db = SessionLocal()
    try:
        before = db.query(AuditLog).filter(AuditLog.action == "watchdog.alert").count()
    finally:
        db.close()

    _emit_alert({
        "key": "db_down",
        "target": "database",
        "detail": {"status": "error", "detail": "连接失败：OperationalError"},
    })

    db = SessionLocal()
    try:
        rows = db.query(AuditLog).filter(AuditLog.action == "watchdog.alert").all()
        after = len(rows)
        latest = rows[-1] if rows else None
        check("audit_logs 新增 1 条 watchdog.alert", after == before + 1)
        check("actor_type=system", latest is not None and latest.actor_type == "system")
        check("result=warning", latest is not None and latest.result == "warning")
        check("target=database", latest is not None and latest.target == "database")
        check("detail 含 alert 类型标记", latest is not None and '"db_down"' in (latest.detail or ""))
    finally:
        db.close()


def test_cooldown_blocks_resend():
    print("[5] 冷却：同一类型告警在冷却窗口内只落一次")
    _ALERT_COOLDOWN.clear()
    db = SessionLocal()
    try:
        before = db.query(AuditLog).filter(AuditLog.action == "watchdog.alert").count()
    finally:
        db.close()

    alert = {"key": "edge_offline", "target": "edge_sites",
             "detail": {"stale_flipped_to_offline": 3}}
    _emit_alert(alert)   # 第一次：落库
    _emit_alert(alert)   # 冷却中：跳过
    _emit_alert(alert)   # 冷却中：跳过

    db = SessionLocal()
    try:
        after = db.query(AuditLog).filter(AuditLog.action == "watchdog.alert").count()
        check("冷却窗口内同类型只新增 1 条", after == before + 1)
    finally:
        db.close()


def test_health_returns_unchanged_structure():
    print("[6] /api/health 返回结构不变（告警为副作用，不进响应体）")
    try:
        from fastapi.testclient import TestClient
        from app.main import app
    except Exception as e:  # noqa: BLE001
        check(f"可导入 app.main（{e}）", False)
        return
    client = TestClient(app)
    resp = client.get("/api/health")
    check("health 返回 200", resp.status_code == 200)
    payload = resp.json().get("data", resp.json())
    for f in ("status", "checks", "edge", "error_rate_5m", "ts"):
        check(f"响应含字段 {f}", f in payload)
    check("响应体不含 watchdog 专用字段（不改结构）", "watchdog_alerts" not in payload)


def main():
    print("=" * 62)
    print("TASK-018-2 Watchdog 告警落 AuditLog 测试")
    print("=" * 62)
    test_decision_db_down()
    test_decision_error_rate()
    test_decision_edge_offline()
    test_emit_writes_audit()
    test_cooldown_blocks_resend()
    test_health_returns_unchanged_structure()
    print("-" * 62)
    print(f"PASS {PASS} / FAIL {FAIL}")
    if FAIL:
        print("结果：存在失败项")
        sys.exit(1)
    print("结果：全部通过")


if __name__ == "__main__":
    main()
