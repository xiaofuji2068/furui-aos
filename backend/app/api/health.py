"""系统健康检查（图谱 90-01 可观测）。

    GET /api/health  — DB / 对话模型 / 语义检索 / 系统 四维健康度。
    设计取舍：
    - 实时探测会拖慢请求（尤其 LLM 连通性），所以 DB 做实连、LLM/Embedding
      做"配置 + 最近一次真实调用的结果缓存"，展示为可读状态，前端可一键刷新。
    - 不暴露任何密钥与内网信息，只返回状态与摘要。
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter
from sqlalchemy import text

from ..config import settings
from ..db import IS_SQLITE, SessionLocal
from ..models_release import EdgeSite
from ..models_ai import ToolExecution


router = APIRouter(tags=["健康检查"])

# 进程启动时间（模块加载时记一次，用于 uptime）
_START_TS = time.time()

# 最近一次真实 LLM / Embedding 调用结果（由 chat-stream / knowledge search 打点）
_LLM_LAST: Dict[str, Any] = {"ok": False, "at": "", "note": "尚未有真实调用"}
_EMB_LAST: Dict[str, Any] = {"ok": False, "at": "", "note": "尚未有真实调用"}


def mark_llm_call(ok: bool, note: str = "") -> None:
    """对话模型真实调用成功后打点（供 /api/health 展示）。"""
    _LLM_LAST.update({"ok": ok, "at": datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"), "note": note})


def mark_embedding_call(ok: bool, note: str = "") -> None:
    """语义检索真实调用打点。"""
    _EMB_LAST.update({"ok": ok, "at": datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"), "note": note})


def _db_check() -> Dict[str, Any]:
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        return {"name": "数据库", "status": "ok", "detail": ("SQLite 连接正常" if IS_SQLITE else "PostgreSQL 连接正常")}
    except Exception as e:  # noqa: BLE001
        return {"name": "数据库", "status": "error", "detail": f"连接失败：{e.__class__.__name__}"}


def _llm_check() -> Dict[str, Any]:
    if not settings.llm_enabled:
        return {"name": "对话模型", "status": "disconnected",
                "detail": "未配置 API Key（当前 Mock 演示态）"}
    status = "ok" if _LLM_LAST.get("ok") else "warning"
    detail = f"{settings.model_name}（{settings.active_provider}）"
    if _LLM_LAST.get("at"):
        detail += f" · 最近调用 {_LLM_LAST['at']} · {_LLM_LAST.get('note', '')}"
    else:
        detail += " · 配置就绪，尚未发起真实调用"
    return {"name": "对话模型", "status": status, "detail": detail}


def _embedding_check() -> Dict[str, Any]:
    if not settings.embedding_enabled:
        return {"name": "语义检索", "status": "warning",
                "detail": "未配置 DashScope Key（本地哈希向量兜底）"}
    status = "ok" if _EMB_LAST.get("ok") else "warning"
    detail = f"text-embedding-v3"
    if _EMB_LAST.get("at"):
        detail += f" · 最近调用 {_EMB_LAST['at']}"
    else:
        detail += " · 配置就绪，尚未发起真实调用"
    return {"name": "语义检索", "status": status, "detail": detail}


def _system_check() -> Dict[str, Any]:
    return {
        "name": "系统",
        "status": "ok",
        "detail": f"{settings.version} · 已运行 {int(time.time() - _START_TS) // 60} 分钟",
    }


def _edge_watchdog(threshold_seconds: int = 300) -> Dict[str, Any]:
    """边缘站点看门狗（TASK-018-2 / 90-01 生产化轴）。

    心跳超过 threshold_seconds 未续约的 online / syncing 站点判 offline。

    注意：edge_sites 在 PG 上是 FORCE RLS；本接口用裸 SessionLocal（无租户上下文），
    PG 查询会被 RLS 过滤为 0 行 → 优雅降级（flipped=0，不报错）。dev 默认 SQLite 无
    RLS，看门狗真实生效。生产 PG 要真正跨租户扫描，需 BYPASSRLS 服务角色或按 company
    逐租户 sweep，留作后续生产化任务。
    """
    try:
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=threshold_seconds)
            sites = db.query(EdgeSite).all()
            counts: Dict[str, int] = {}
            flipped = 0
            for s in sites:
                counts[s.status] = counts.get(s.status, 0) + 1
                if s.status in ("online", "syncing") and (
                    s.last_heartbeat_at is None or s.last_heartbeat_at < cutoff
                ):
                    s.status = "offline"
                    flipped += 1
            if flipped:
                db.commit()
            return {
                "ok": True,
                "threshold_seconds": threshold_seconds,
                "counts": counts,
                "stale_flipped_to_offline": flipped,
            }
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"{e.__class__.__name__}: {e}"}


def _error_rate_5m(window_seconds: int = 300) -> Dict[str, Any]:
    """近 window_seconds 内工具调用错误率（failed / blocked 占比）。"""
    try:
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
            rows = db.query(ToolExecution).filter(ToolExecution.created_at >= cutoff).all()
            total = len(rows)
            errors = sum(1 for r in rows if r.status in ("failed", "blocked"))
            rate = round(errors / total, 4) if total else 0.0
            return {
                "ok": True,
                "window_seconds": window_seconds,
                "total": total,
                "errors": errors,
                "rate": rate,
            }
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"{e.__class__.__name__}: {e}"}


@router.get("/health")
def health() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = [
        _db_check(),
        _llm_check(),
        _embedding_check(),
        _system_check(),
    ]
    failed = [c for c in checks if c["status"] == "error"]
    edge = _edge_watchdog()
    err = _error_rate_5m()
    return {
        "status": "ok" if not failed else "degraded",
        "checks": checks,
        "edge": edge,
        "error_rate_5m": err,
        "llm_enabled": settings.llm_enabled,
        "embedding_enabled": settings.embedding_enabled,
        "ts": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    }
