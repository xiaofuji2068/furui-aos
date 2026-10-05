"""数据库层 — SQLAlchemy 2.x，SQLite 默认 + PostgreSQL 可切换（步骤 2.1）。

租户隔离（步骤 2.2）：set_tenant_context 在 PostgreSQL 上执行 SET LOCAL 注入
app.company_id，配合 RLS policy 实现行级租户隔离；SQLite 上为 no-op（不影响开发）。

MVP 默认 SQLite（零外部服务依赖，开箱即跑）；生产切 PostgreSQL 只需设置
环境变量 DATABASE_URL=postgresql://user:pass@host:5432/furui_aios，无需改代码。
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'app.db'}")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if IS_SQLITE:
    engine_kwargs["connect_args"] = {"check_same_thread": False,   # SQLite + FastAPI 多线程
                                   "isolation_level": None}     # autocommit：DDL 立即落库（Python 3.12+ sqlite3 默认把 DDL 包进延迟事务）

engine = create_engine(DATABASE_URL, **engine_kwargs)


if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_foreign_keys(dbapi_conn, _record):
        """SQLite 默认不强制外键：开启后 ON DELETE CASCADE/SET NULL 才真正生效。

        保证删除 Approval 后 ActionReceipt.approval_id 自动置空，
        避免悬空引用被自增 ID 复用后误匹配。
        """
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def set_tenant_context(db, company_id: int | None) -> None:
    """在事务内注入租户上下文（PostgreSQL RLS 生效；SQLite 无 RLS，跳过）。

    Phase 3（60-02）：RLS policy 按 current_setting('app.company_id') 过滤。
    - 有 company_id：SET LOCAL 注入真实租户；
    - 无（未登录/未带 token）：注入 0 —— FORCE RLS 下查不到任何租户行（安全兜底），
      且避免 current_setting 缺省报错。
    """
    if IS_SQLITE:
        return
    db.execute(text("SET LOCAL app.company_id = :cid"), {"cid": int(company_id) if company_id else 0})


def _company_id_from_authorization(authorization: str | None) -> int | None:
    """从请求头 Authorization: Bearer <token> 解析租户 company_id（供 get_db 注入）。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        from .security import decode_token
        payload = decode_token(authorization[7:])
        cid = payload.get("company_id") if payload else None
        return int(cid) if cid else None
    except Exception:
        return None


def get_db(request=None):
    """FastAPI 依赖：每个请求一个 session，并按请求租户注入上下文。"""
    db = SessionLocal()
    try:
        if request is not None:
            auth = getattr(request, "headers", None)
            if auth is not None:
                set_tenant_context(db, _company_id_from_authorization(auth.get("Authorization")))
        yield db
    finally:
        db.close()


def ensure_column(db, table: str, column: str, ddl: str) -> bool:
    """幂等加列（跨方言 SQLite/PG）：列缺失时 ALTER TABLE ADD COLUMN。

    返回是否执行了 ALTER。create_all 只建新表、不改已有表，
    因此对既有表的新增字段必须显式补齐（如 approvals.decision_lineage）。
    """
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(db.get_bind())
    cols = {c["name"] for c in insp.get_columns(table)}
    if column in cols:
        return False
    db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    db.commit()
    return True
