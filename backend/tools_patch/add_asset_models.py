# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\models_ai.py")
t = p.read_text(encoding="utf-8")
anchor = '''    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_app_pages_company_code"),)'''
addition = '''    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_app_pages_company_code"),)


class AssetBundle(Base):
    """资产包（50-01 Bundle）：Manifest + 打包内容（pages/logic 资产定义）。

    系统级资产目录（RLS 豁免，类似 permissions/ontology_types 先例）：
    Bundle 由某企业作者创建（created_by_company_id），但目录本身跨租户只读共享；
    租户通过 install（派生优先）在自命名空间生成派生资产（asset_installations）。
    """
    __tablename__ = "asset_bundles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="1.0")
    kind: Mapped[str] = mapped_column(String(24), nullable=False, server_default="bundle")  # bundle|plugin
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    # {nav_entry:{href,icon,label,perm}, widget_types:[...], permissions:[...], requires:["pages","logic"]}
    content_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    # {pages:[{code,title,description,layout}], logic_graphs:[{code,name,description,nodes:[...]}]}
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")  # draft|published
    created_by_company_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"),
                                                 onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("code", name="uq_asset_bundles_code"),)


class AssetInstallation(Base):
    """租户安装记录（50-03 Installation，派生优先语义）。

    安装 = 把 Bundle 内容复制到租户命名空间生成派生资产（app_pages / logic_graphs），
    原 Bundle 只读；租户对同一 Bundle 只装一次（升级=更新 bundle_version 并可选重新派生）。
    """
    __tablename__ = "asset_installations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), default=1, index=True)
    bundle_id: Mapped[int] = mapped_column(ForeignKey("asset_bundles.id", ondelete="CASCADE"))
    bundle_code: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    bundle_version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="1.0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="installed")  # installed|uninstalled
    derived_pages_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")  # [{code,page_id,title}]
    derived_graphs_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")  # [{code,graph_id,name}]
    installed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                  server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"),
                                                 onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("company_id", "bundle_id", name="uq_asset_install_company_bundle"),)'''
assert anchor in t, "anchor not found"
t = t.replace(anchor, addition, 1)
p.write_text(t, encoding="utf-8")
ast.parse(t)
print("models added: AssetBundle + AssetInstallation")