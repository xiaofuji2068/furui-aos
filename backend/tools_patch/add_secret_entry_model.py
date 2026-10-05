# -*- coding: utf-8 -*-
"""TASK-013：在 models_ai.py 末尾（write_audit 前）插入 SecretEntry 模型。"""
import io

p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\models_ai.py"
with io.open(p, "r", encoding="utf-8") as f:
    src = f.read()

anchor = "\n# ---------------- 审计便捷方法 ----------------\n"
block = '''


# ---------------- SecretRef / Keychain（60-04 密钥引用） ----------------

class SecretEntry(Base):
    """密钥引用（60-04 SecretRef + Keychain）。

    告别 `.env` 明文：密钥以 SecretEntry 落库（按租户隔离 + RLS），
    对外只暴露脱敏视图，任何日志 / API 响应不回显明文。

    字段语义：
    - ref_key：稳定引用名（如 `llm:deepseek` / `ds:erp` / `webhook:alert`），
      业务代码通过 ref_key 解析，不直接接触明文。
    - kind：llm / datasource / webhook / custom（用途归类）。
    - pii_level：none / low / high（PII 敏感度标注）。
    - retention_days：保留期（天），治理与过期清理依据。
    - region：数据驻留区域标注（如 cn / us / eu）。
    """
    __tablename__ = "secret_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    ref_key: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="custom")      # llm/datasource/webhook/custom
    secret_value: Mapped[str] = mapped_column(Text, default="")
    pii_level: Mapped[str] = mapped_column(String(20), default="none")   # none/low/high
    retention_days: Mapped[int] = mapped_column(Integer, default=365)
    region: Mapped[str] = mapped_column(String(20), default="cn")
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow,
                                                 server_default=text("CURRENT_TIMESTAMP"))

'''
if "class SecretEntry" in src:
    print("SKIP: SecretEntry already exists")
elif anchor in src:
    src = src.replace(anchor, block + anchor, 1)
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(src)
    print("OK: SecretEntry inserted")
else:
    print("WARN: anchor not found")
