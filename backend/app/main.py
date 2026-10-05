"""FastAPI 入口。"""
from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# 让 app.* 可作为包被 import
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.api import router  # noqa: E402
from app.bootstrap import init_all  # noqa: E402
from app.config import settings  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时建表 + 建模拟外部库 + 灌入种子数据 + 建知识索引（幂等）。"""
    init_all()
    # 步骤 2.4：无 key 启动给出清晰提示（不静默降级）
    if not settings.llm_enabled:
        print("[startup] 未配置当前对话模型的 API Key，对话走内置 Mock 回复；"
              "可在「模型管理」页配置 DeepSeek/Kimi/通义/GLM/OpenAI 任一 Key 并设为当前模型")
    if not settings.embedding_enabled:
        print("[startup] 未配置 DASHSCOPE_API_KEY，知识检索走本地哈希向量（离线兜底）；"
              "可在「模型管理」页配置，或写入 backend/.env 后重启生效")
    yield


app = FastAPI(title=settings.system_name, version=settings.version, lifespan=lifespan)


# ---------------- 统一 API 返回格式（TASK-001） ----------------
# 成功响应统一包装为 {"code": 0, "message": "ok", "data": ...}
# 异常响应统一包装为 {"code": non-zero, "message": "...", "data": null}
#
# 用中间件而不是在每个路由里手写 ok()：路由只关心业务数据，
# 格式一致性由中间件保证，避免"有的接口包了、有的没包"这种最容易腐化的不一致。

@app.middleware("http")
async def wrap_response(request: Request, call_next):
    response = await call_next(request)

    # 只处理 /api 下的 JSON 响应；SSE 流与静态资源原样透传
    if not request.url.path.startswith("/api/"):
        return response
    ctype = response.headers.get("content-type", "")
    if "application/json" not in ctype:
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    try:
        payload = json.loads(body) if body else None
    except Exception:                                            # noqa: BLE001
        payload = None

    # 已是统一结构（含 code 字段）的不重复包裹
    if isinstance(payload, dict) and "code" in payload:
        wrapped = payload
    else:
        wrapped = {"code": 0, "message": "ok", "data": payload}

    return JSONResponse(
        status_code=response.status_code,
        content=wrapped,
        headers={k: v for k, v in response.headers.items()
                 if k.lower() not in ("content-length", "content-type")},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code = detail.get("code", exc.status_code)
        message = detail.get("message", "")
    else:
        code, message = exc.status_code, str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": code, "message": message, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "参数校验失败",
            "data": {"errors": exc.errors()[:5]},
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": f"服务器内部错误：{exc}", "data": None},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
        "http://localhost:3002", "http://127.0.0.1:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return JSONResponse({
        "system": settings.system_name,
        "version": settings.version,
        "llm_enabled": settings.llm_enabled,
        "model": settings.model_name if settings.llm_enabled else "(mock mode)",
        "routes": [
            "POST /api/auth/login",
            "POST /api/auth/logout",
            "GET  /api/auth/me",
            "POST /api/auth/password",
            "GET/POST /api/org/companies",
            "PUT/DELETE /api/org/companies/{id}",
            "GET/POST /api/org/departments",
            "PUT/DELETE /api/org/departments/{id}",
            "GET/POST /api/org/users",
            "PUT/DELETE /api/org/users/{id}",
            "GET/POST /api/org/roles",
            "PUT  /api/org/roles/{id}",
            "GET  /api/org/permissions",
            "GET  /api/overview",
            "GET  /api/agents",
            "GET  /api/employees",
            "GET  /api/employees/{name}",
            "GET  /api/tasks",
            "POST /api/tasks/confirm",
            "GET  /api/activities",
            "GET  /api/workbench",
            "GET  /api/knowledge",
            "GET  /api/scenes",
            "GET  /api/data-sources",
            "GET  /api/data-sources/catalog",
            "GET  /api/data-sources/{id}",
            "POST /api/data-sources",
            "DELETE /api/data-sources/{id}",
            "POST /api/data-sources/{id}/toggle",
            "POST /api/chat-stream",
        ],
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
