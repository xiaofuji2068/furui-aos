"""交付发布与边缘协同领域 — ORM 模型（TASK-017 / 70-03 + 80-01 + 80-02）。

与 AI 域、组织域分离的原因：这三张表管的是「怎么把东西发出去」，
而不是「谁在用它 / AI 在做什么」，演进节奏（每次发版动一次）完全不同。

覆盖差距清单三块短板：
  70-03 中心边缘与客户环境协作：EdgeSite（Hub-Spoke 站点注册 + 心跳 + 版本同步）
  80-01 Apollo 交付与发布：Release + ReleaseChange（Release/Channel/Change/SBOM/签名）
  80-02 发布到达各环境：Release.status 的 promote/recall 状态机（显式白名单，禁止非法跳态）

设计取舍：
  1. releases 是**系统级交付物目录**（跨租户共享，RLS 豁免，同 asset_bundles/permissions 先例）。
     一个 Release 是产品版本，不属于某一家客户；客户站点（EdgeSite）通过 release_id 引用它。
  2. edge_sites 是**租户所有**（属某家企业客户环境），RLS/FORCE 严格隔离。
  3. 注册令牌只存 sha256 哈希，明文 token 只在注册响应里出现一次，绝不二次落库。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.utcnow()


class Release(Base):
    """交付 Release（80-01/80-02）：版本 + 通道 + 变更 + SBOM 摘要 + 签名。

    Channel（通道）与 Status（状态）分离：
      channel = 这个版本被投放到哪条流水线（draft / staging / production）
      status  = 这个版本当前的生命周期（draft / promoted / recalled / superseded）
    两者正交，避免「staging 上的版本也叫 promoted」这种歧义。
    """

    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)  # 形如 2.0.0
    channel: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    # 组件清单摘要（由 tools/sbom.py 产出后回填）：{backend:[{name,version,purl}], frontend:[...]}
    sbom_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    # 对 sbom_json + version + manifest 算出的 64 位签名，交付审计用（防篡改）
    signature: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    # 发布说明 / 变更单引用
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    promoted_to: Mapped[str] = mapped_column(String(32), nullable=False, server_default="")
    released_by_company_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"), onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("version", name="uq_releases_version"),)


class ReleaseChange(Base):
    """Release 变更单（80-01 的 Change）：一个 Release 下的逐条变更项。

    独立成表而非塞进 releases.notes 里的 JSON：核电客户交付审计要能按条
    回溯「这个版本修了什么」，塞 JSON 就没法按 kind 过滤和计数。
    """

    __tablename__ = "release_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # feat | fix | config | security | migration
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="feat")
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (UniqueConstraint("release_id", "kind", "summary",
                                       name="uq_release_change"),)


class EdgeSite(Base):
    """边缘站点（70-03 Hub-Spoke）：客户侧边缘 Agent / 现场的注册与心跳。

    归属企业（company_id）所有 → RLS/FORCE 严格租户隔离。
    站点注册后由中心下发 release_id（当前应运行的版本），Spoke 侧按
    /api/edge-sites/{code}/sync 拉取该版本 manifest 完成升级。

    site_token_hash 只存 sha256(token)：心跳接口校验时比对哈希，
    明文令牌仅在注册响应中出现一次，库里不留可复用凭据。
    """

    __tablename__ = "edge_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, server_default="")
    site_type: Mapped[str] = mapped_column(String(24), nullable=False, server_default="edge")
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, server_default="1")
    release_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # registered | online | offline | syncing
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="registered")
    # sha256(token)，不存明文
    site_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="")
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"), onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("site_code", name="uq_edge_sites_code"),)
