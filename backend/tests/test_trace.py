# -*- coding: utf-8 -*-
"""TASK-018-2：Trace 链路 ID 锁定测试。

核心不变量：一次请求（= 一个 trace 上下文）内，审计日志（audit_logs）
与工具执行记录（tool_executions）写入**同一个 trace_id**，运维可按 trace_id
把「同一请求触发的全部动作」串起来查。

运行方式：run_tests.py 强制 DATABASE_URL=furui_aios_test（与生产同结构），
本脚本也自带兜底环境变量，可单独跑：
    backend/venv/Scripts/python.exe tests/test_trace.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test",
)

# 必须在 import app.db 之前就位（app/db.py 第 21 行读取 DATABASE_URL 兜底）
import app.models  # noqa: E402  (注册组织域模型)
import app.models_ai  # noqa: E402
import app.models_ontology  # noqa: E402
import app.models_release  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.trace_ctx import get_trace_id, set_trace_id, TRACE_ID  # noqa: E402
from app.models_ai import AuditLog, ToolExecution, write_audit  # noqa: E402
from app.tool_gateway import ToolContext, _log, Tool  # noqa: E402

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


def test_contextvar_roundtrip():
    print("[1] ContextVar 兜底默认 None + 写入/读取/重置")
    check("默认值为 None", get_trace_id() is None)
    tok = TRACE_ID.set("abc")
    try:
        check("set 后可读取", get_trace_id() == "abc")
    finally:
        TRACE_ID.reset(tok)
    check("reset 后回到 None", get_trace_id() is None)


def test_write_audit_picks_contextvar():
    print("[2] write_audit 默认从上下文取 trace_id")
    db = SessionLocal()
    try:
        tok = TRACE_ID.set("trace-audit-001")
        try:
            log = write_audit(db, action="tool.call", actor_type="user", company_id=1)
            db.commit()
            row = db.query(AuditLog).filter(AuditLog.id == log.id).first()
            check("审计日志写入上下文 trace_id", row is not None and row.trace_id == "trace-audit-001")
        finally:
            TRACE_ID.reset(tok)
        # 显式覆盖：调用方主动传入时优先于上下文
        log2 = write_audit(db, action="tool.call", actor_type="user", company_id=1,
                           trace_id="explicit-xyz")
        db.commit()
        row2 = db.query(AuditLog).filter(AuditLog.id == log2.id).first()
        check("显式 trace_id 覆盖上下文", row2.trace_id == "explicit-xyz")
    finally:
        db.close()


def test_log_picks_contextvar():
    print("[3] tool_gateway._log 从上下文取 trace_id")
    db = SessionLocal()
    try:
        tool = db.query(Tool).filter(Tool.company_id == 1).first()
        if tool is None:
            check("存在种子工具可供测试", False)
            return
        ctx = ToolContext(db=db, company_id=1)
        tok = TRACE_ID.set("trace-tool-001")
        try:
            rec = _log(db, ctx, tool, {"x": 1}, status="success", permission="pass", ms=time.time())
            db.commit()
            row = db.query(ToolExecution).filter(ToolExecution.id == rec.id).first()
            check("工具执行记录写入上下文 trace_id", row is not None and row.trace_id == "trace-tool-001")
        finally:
            TRACE_ID.reset(tok)
    finally:
        db.close()


def test_same_trace_links_both_tables():
    print("[4] 一次上下文 → 两表同 trace_id（核心不变量）")
    db = SessionLocal()
    try:
        tool = db.query(Tool).filter(Tool.company_id == 1).first()
        if tool is None:
            check("存在种子工具可供测试", False)
            return
        ctx = ToolContext(db=db, company_id=1)
        tok = TRACE_ID.set("trace-both-001")
        try:
            # 同一 trace 上下文内：审计 sink + 工具 sink
            log = write_audit(db, action="tool.call", actor_type="agent", company_id=1, target="q")
            rec = _log(db, ctx, tool, {"x": 1}, status="success", permission="pass", ms=time.time())
            db.commit()
            # 直接用已插入行的主键反查（不依赖 trace_id 唯一性，避免多次回归后残留同名行干扰）
            a = db.query(AuditLog).filter(AuditLog.id == log.id).first()
            t = db.query(ToolExecution).filter(ToolExecution.id == rec.id).first()
            check("audit_logs 落同一 trace_id", a is not None and a.trace_id == "trace-both-001")
            check("tool_executions 落同一 trace_id", t is not None and t.trace_id == "trace-both-001")
            check("两表 trace_id 一致", a is not None and t is not None and a.trace_id == t.trace_id)
        finally:
            TRACE_ID.reset(tok)
    finally:
        db.close()


def test_http_middleware_injects_header():
    print("[5] HTTP 中间件注入 X-Trace-Id 响应头 + health 暴露看门狗字段")
    try:
        from fastapi.testclient import TestClient  # lazy import
        from app.main import app
    except Exception as e:  # noqa: BLE001
        check(f"可导入 app.main（{e}）", False)
        return
    # 不触发 lifespan（init_all 较重），/api/health 仅做 SELECT 1，无需初始化数据
    client = TestClient(app)
    resp = client.get("/api/health", headers={"X-Trace-Id": "trace-http-009"})
    check("health 返回 200", resp.status_code == 200)
    check("响应头回写 X-Trace-Id", resp.headers.get("X-Trace-Id") == "trace-http-009")
    body = resp.json()
    # wrap_response 中间件把路由返回值包进 {"code":0,"message":"ok","data":<health>}
    payload = body.get("data", body)
    check("响应含 edge 看门狗字段", "edge" in payload)
    check("响应含 error_rate_5m 字段", "error_rate_5m" in payload)


def main():
    print("=" * 62)
    print("TASK-018-2 Trace 链路 ID 测试")
    print("=" * 62)
    test_contextvar_roundtrip()
    test_write_audit_picks_contextvar()
    test_log_picks_contextvar()
    test_same_trace_links_both_tables()
    test_http_middleware_injects_header()
    print("-" * 62)
    print(f"PASS {PASS} / FAIL {FAIL}")
    if FAIL:
        print("结果：存在失败项")
        sys.exit(1)
    print("结果：全部通过")


if __name__ == "__main__":
    main()
