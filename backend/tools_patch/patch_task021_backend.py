# -*- coding: utf-8 -*-
"""TASK-021 后端补丁 A：SystemSetting 模型 + admin settings 落库 + 迁移文件。

1) models.py 追加 SystemSetting（system_settings 表，company_id+key 唯一）
2) admin.py：
   - _settings_payload(company_id) 从 DB 读租户设置覆盖默认
   - admin_page 路由对 settings 传 user.company_id
   - save_settings 改为 DB upsert（落库，不再"重启即丢失"）
3) 新建迁移 e5f6a7b8c9d0_system_settings.py（建表 + PG RLS 直列表）
"""
import io
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")

# ---------- 1) models.py 追加 SystemSetting ----------
mp = ROOT / "app" / "models.py"
src = mp.read_text(encoding="utf-8")

anchor = "\n\ndef init_db() -> None:"
model_block = '''

class SystemSetting(Base):
    """系统设置（按租户持久化；TASK-021 替代内存暂存，保存重启不丢）。"""
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), default=1, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (UniqueConstraint("company_id", "key", name="uq_system_settings_company_key"),)

'''
assert anchor in src, "models anchor"
src = src.replace(anchor, model_block + anchor, 1)
# 确保 UniqueConstraint 已导入
if "UniqueConstraint" not in src.split("\n", 0)[0] and "from sqlalchemy import" in src:
    src = src.replace(
        "from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Table, Column, Text, text",
        "from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Table, Column, Text, text, UniqueConstraint", 1)
mp.write_text(src, encoding="utf-8")
print("OK: models.py + SystemSetting")

# ---------- 2) admin.py settings 落库 ----------
ap = ROOT / "app" / "api" / "admin.py"
src = ap.read_text(encoding="utf-8")

# 2a) _settings_payload 支持 company_id 参数 + DB 读取
old = '''def _settings_payload() -> Dict[str, Any]:
    defaults = [
        {"key": "system_name", "label": "系统名称", "value": settings.system_name, "type": "text"},
        {"key": "org_name", "label": "所属组织", "value": "傅瑞科技", "type": "text"},
        {"key": "llm_enabled", "label": "启用真实大模型", "value": settings.llm_enabled, "type": "toggle"},
        {"key": "model_name", "label": "模型名称", "value": settings.model_name, "type": "text"},
        {"key": "auto_confirm", "label": "允许 AI 自动执行写入", "value": False, "type": "toggle"},
    ]
    # 用暂存值覆盖默认
    for f in defaults:
        if f["key"] in _SETTINGS:
            f["value"] = _SETTINGS[f["key"]]
    return {'''
new = '''def _load_settings_db(company_id: int | None) -> Dict[str, Any]:
    """从 system_settings 表读取该租户已保存的设置（无则空）。"""
    if company_id is None:
        return {}
    try:
        from ..db import SessionLocal
        from ..models import SystemSetting
        db = SessionLocal()
        try:
            rows = db.query(SystemSetting).filter(SystemSetting.company_id == company_id).all()
            return {r.key: r.value for r in rows}
        finally:
            db.close()
    except Exception:  # noqa: BLE001 表未就绪/迁移未跑时回退空
        return {}


def _settings_payload(company_id: int | None = None) -> Dict[str, Any]:
    defaults = [
        {"key": "system_name", "label": "系统名称", "value": settings.system_name, "type": "text"},
        {"key": "org_name", "label": "所属组织", "value": "傅瑞科技", "type": "text"},
        {"key": "llm_enabled", "label": "启用真实大模型", "value": settings.llm_enabled, "type": "toggle"},
        {"key": "model_name", "label": "模型名称", "value": settings.model_name, "type": "text"},
        {"key": "auto_confirm", "label": "允许 AI 自动执行写入", "value": False, "type": "toggle"},
    ]
    saved = _load_settings_db(company_id)
    for f in defaults:
        if f["key"] in saved:
            v = saved[f["key"]]
            if f["type"] == "toggle":
                f["value"] = str(v).lower() in ("1", "true", "yes", "on")
            else:
                f["value"] = v
    return {'''
assert old in src, "settings_payload anchor"
src = src.replace(old, new, 1)

# 2b) admin_page 对 settings 传 company_id
old = '''    need = _SLUG_PERM[slug]
    if not user.has_perm(need):
        raise HTTPException(status_code=403, detail=f"缺少权限：{need}")
    return _BUILDERS[slug]()'''
new = '''    need = _SLUG_PERM[slug]
    if not user.has_perm(need):
        raise HTTPException(status_code=403, detail=f"缺少权限：{need}")
    if slug == "settings":
        return _settings_payload(user.company_id)
    return _BUILDERS[slug]()'''
assert old in src, "admin_page anchor"
src = src.replace(old, new, 1)

# 2c) save_settings 落库
old = '''def save_settings(req: SettingsReq, _auth: User = Depends(require_perm("company:manage"))):
    for f in req.fields:
        _SETTINGS[f["key"]] = f["value"]
    return {"ok": True}'''
new = '''def save_settings(req: SettingsReq, user: User = Depends(require_perm("company:manage"))):
    """保存设置到 system_settings 表（按租户幂等 upsert，重启不丢）。"""
    from ..db import SessionLocal
    from ..models import SystemSetting

    db = SessionLocal()
    try:
        for f in req.fields:
            key = str(f.get("key", ""))
            if not key:
                continue
            value = "" if f.get("value") is None else str(f.get("value"))
            row = db.query(SystemSetting).filter(
                SystemSetting.company_id == user.company_id,
                SystemSetting.key == key).first()
            if row:
                row.value = value
            else:
                db.add(SystemSetting(company_id=user.company_id, key=key, value=value))
        db.commit()
    finally:
        db.close()
    return {"ok": True, "persisted": True}'''
assert old in src, "save_settings anchor"
src = src.replace(old, new, 1)

ap.write_text(src, encoding="utf-8")
print("OK: admin.py settings persisted")

# ---------- 3) 迁移文件 ----------
vp = ROOT / "alembic" / "versions" / "e5f6a7b8c9d0_system_settings.py"
migration = '''# -*- coding: utf-8 -*-
"""TASK-021：system_settings 表（设置落库，替代内存暂存）+ RLS 收口

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-23 16:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('system_settings'):
        op.create_table(
            'system_settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(),
                      sa.ForeignKey('companies.id', ondelete='CASCADE'),
                      nullable=False, server_default='1'),
            sa.Column('key', sa.String(64), nullable=False),
            sa.Column('value', sa.Text(), nullable=False, server_default=''),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('company_id', 'key', name='uq_system_settings_company_key'),
        )
    if bind.dialect.name == 'postgresql':
        cond = "company_id = NULLIF(current_setting('app.company_id', true), '')::int"
        op.execute("ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE system_settings FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON system_settings;")
        op.execute(f"CREATE POLICY tenant_isolation ON system_settings USING ({cond}) WITH CHECK ({cond});")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON system_settings;")
        op.execute("ALTER TABLE system_settings DISABLE ROW LEVEL SECURITY;")
    if sa.inspect(bind).has_table('system_settings'):
        op.drop_table('system_settings')
'''
vp.write_text(migration, encoding="utf-8")
print("OK: migration e5f6a7b8c9d0_system_settings.py")
