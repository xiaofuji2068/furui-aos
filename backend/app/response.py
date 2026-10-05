"""统一 API 返回格式（TASK-001）。

所有接口统一返回：
    {"code": 0, "message": "ok", "data": ...}
非 0 表示业务失败；HTTP 状态码仍用于表达鉴权/资源语义。
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def ok(data: Any = None, message: str = "ok", code: int = 0) -> dict:
    return {"code": code, "message": message, "data": data}


def fail(message: str, code: int = 1, http_status: int = 400) -> None:
    """直接抛 HTTPException，附带统一结构（由异常处理器转换）。"""
    raise HTTPException(status_code=http_status, detail={"code": code, "message": message})
