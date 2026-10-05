from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 内置 LLM 对话提供方：id -> 默认接入点与模型（均可被 .env / 页面配置覆盖）
# context_window / price_per_1k 为展示型元数据（模型 Catalog 用），不影响调用
LLM_PROVIDERS: Dict[str, Dict[str, str]] = {
    "deepseek": {"label": "DeepSeek",         "base_url": "https://api.deepseek.com/v1",
                 "model_name": "deepseek-chat", "context_window": "64K", "price_per_1k": "¥0.001/0.002"},
    "kimi":     {"label": "Kimi（Moonshot）",  "base_url": "https://api.moonshot.cn/v1",
                 "model_name": "moonshot-v1-8k", "context_window": "8K", "price_per_1k": "¥0.012/0.012"},
    "qwen":     {"label": "通义千问",          "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                 "model_name": "qwen-plus", "context_window": "128K", "price_per_1k": "¥0.0008/0.002"},
    "glm":      {"label": "智谱 GLM",          "base_url": "https://open.bigmodel.cn/api/paas/v4",
                 "model_name": "glm-4-flash", "context_window": "128K", "price_per_1k": "免费"},
    "openai":   {"label": "OpenAI",            "base_url": "https://api.openai.com/v1",
                 "model_name": "gpt-4o-mini", "context_window": "128K", "price_per_1k": "$0.00015/0.0006"},
    "custom":   {"label": "自定义（兼容 OpenAI）", "base_url": "", "model_name": "",
                 "context_window": "—", "price_per_1k": "—"},
}


class Settings(BaseSettings):
    """全局配置。

    设计要点：
    - 对话模型支持多家（DeepSeek / Kimi / 通义 / 智谱 / OpenAI / 自定义），
      每家独立 Key，单选「当前激活提供方」；核心代码只读兼容代理属性
      （openai_api_key / openai_base_url / model_name），自动跟随激活项，切模型零改代码。
    - Embedding 语义检索固定走通义 DashScope（text-embedding-v3）。
    - Ontology 类型注册、Skill 允许列表等通过开关控制演示/生产模式。
    """

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=("settings_", "model_"),
    )

    # ---- 对话模型：多提供方（每家独立 key；.env 键名由 validation_alias 指定）----
    deepseek_key: str = Field("", validation_alias="DEEPSEEK_API_KEY")
    kimi_key: str = Field("", validation_alias="KIMI_API_KEY")
    qwen_key: str = Field("", validation_alias="QWEN_API_KEY")
    glm_key: str = Field("", validation_alias="GLM_API_KEY")
    openai_key: str = Field("", validation_alias="OPENAI_API_KEY")
    custom_key: str = Field("", validation_alias="CUSTOM_API_KEY")
    custom_base_url: str = Field("", validation_alias="CUSTOM_BASE_URL")
    custom_model_name: str = Field("", validation_alias="CUSTOM_MODEL_NAME")
    active_llm_provider: str = Field("deepseek", validation_alias="ACTIVE_LLM_PROVIDER")

    # ---- 语义检索（Embedding）— 通义 DashScope ----
    dashscope_api_key: str = Field("", validation_alias="DASHSCOPE_API_KEY")
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024

    # 系统
    system_name: str = "傅瑞科技 · 企业 AI 操作系统"
    version: str = "v2.0"

    # AOP / Ontology
    enable_real_llm: bool = True
    enable_human_confirmation: bool = True

    # ---------------- 兼容代理（核心代码零改动，自动跟随激活提供方） ----------------

    @property
    def active_provider(self) -> str:
        """当前激活的对话提供方 id（非法值回退 deepseek）。"""
        p = getattr(self, "active_llm_provider", "") or ""
        return p if p in LLM_PROVIDERS else "deepseek"

    @property
    def llm_api_key(self) -> str:
        """当前激活对话提供方的 Key（唯一推荐读取点）。"""
        return getattr(self, f"{self.active_provider}_key", "") or ""

    @property
    def openai_api_key(self) -> str:
        """兼容旧引用：当前激活对话模型的 Key。"""
        return self.llm_api_key

    @property
    def openai_base_url(self) -> str:
        """兼容旧引用：当前激活对话模型的接入点。"""
        if self.active_provider == "custom":
            return self.custom_base_url or "https://api.deepseek.com/v1"
        return LLM_PROVIDERS[self.active_provider]["base_url"]

    @property
    def model_name(self) -> str:
        """兼容旧引用：当前激活对话模型的模型名。"""
        if self.active_provider == "custom":
            return self.custom_model_name or ""
        return LLM_PROVIDERS[self.active_provider]["model_name"]

    @property
    def llm_enabled(self) -> bool:
        return self.enable_real_llm and bool(self.llm_api_key)

    @property
    def embedding_enabled(self) -> bool:
        """有 key 走通义真实语义向量；无 key 自动降级为本地哈希向量（离线兜底）。"""
        return bool(self.dashscope_api_key)


settings = Settings()
