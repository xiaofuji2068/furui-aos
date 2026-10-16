"""Trace 链路 ID 上下文（TASK-018-2）。

一次 HTTP 请求 = 一条 trace。入口中间件生成 trace_id（或透传客户端
X-Trace-Id），存入 ContextVar，供审计日志 / 工具执行等跨函数调用统一携带，
无需层层透传参数。运维可按 trace_id 把「同一请求触发的全部动作」串起来查。
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

# 默认 None —— 非请求上下文（脚本 / 后台任务）下写入审计 / 工具日志时 trace_id 为空，不报错。
TRACE_ID: ContextVar[str | None] = ContextVar("trace_id", default=None)


def get_trace_id() -> str | None:
    """读取当前请求链路的 trace_id（无则为 None）。"""
    return TRACE_ID.get()


def set_trace_id(value: str | None):
    """设置当前链路的 trace_id，返回 token 供重置。"""
    return TRACE_ID.set(value)


def new_trace_id() -> str:
    """生成新的 trace_id（32 位 hex，足够做请求级唯一标识）。"""
    return uuid.uuid4().hex
