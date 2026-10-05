# -*- coding: utf-8 -*-
"""模型 API Key 多提供方配置接口测试：
GET 状态（不回明文）/ POST 保存写 .env + 热更新 / 激活切换 / 自定义提供方 / 留空不覆盖。

安全：测试会临时写 backend/.env，用备份/还原保护真实配置。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 注册全部表
import app.models  # noqa: F401
import app.models_ontology  # noqa: F401
from fastapi.testclient import TestClient

from app.main import app
from app.api import admin as admin_mod
from app.config import LLM_PROVIDERS, settings

client = TestClient(app)

# 测试涉及的全部 settings 字段（还原用）
_FIELDS = ["deepseek_key", "kimi_key", "qwen_key", "glm_key", "openai_key",
           "custom_key", "custom_base_url", "custom_model_name",
           "active_llm_provider", "dashscope_api_key"]


def _parse_env(text: str) -> dict:
    d = {}
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s and not s.startswith("#") and "=" in s:
            k, _, v = s.partition("=")
            d[k.strip()] = v.strip()
    return d


def _unpack(r) -> dict:
    """统一响应包装为 {code, message, data}，取 data。"""
    j = r.json()
    if isinstance(j, dict) and "data" in j and "code" in j:
        return j["data"]
    return j


def _bearer() -> dict:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


HA = _bearer()


def test_admin_keys_flow():
    # 1. 备份真实 .env 与 settings 现场
    env_path = admin_mod._ENV_FILE
    backup_text = env_path.read_text(encoding="utf-8") if env_path.exists() else None
    orig = {f: getattr(settings, f) for f in _FIELDS}

    try:
        # 2. 无 token 被拒（60-03 后端鉴权）：GET/POST 一律 401
        assert client.get("/api/admin/model/keys").status_code == 401
        assert client.post("/api/admin/model/keys",
                           json={"provider": "deepseek", "api_key": "sk-x"}).status_code == 401

        # 3. GET 状态：6 个对话提供方 + embedding，字段齐全且不返回明文
        r = client.get("/api/admin/model/keys", headers=HA)
        assert r.status_code == 200, r.text
        body = _unpack(r)
        assert set(body.keys()) >= {"active", "providers", "llm_enabled", "embedding"}
        pids = [p["id"] for p in body["providers"]]
        assert set(pids) == set(LLM_PROVIDERS.keys()), pids
        for p in body["providers"]:
            assert {"id", "label", "model_name", "has_key", "active"} <= set(p.keys())
        raw = r.text
        for k in ("api_key", "deepseek_key", "kimi_key", "dashscope_api_key"):
            # 只允许出现 key 字样为 false/字段名，不允许出现 "sk-" 明文形态
            assert '": "sk-' not in raw, "泄漏明文 Key！"

        # 4. POST 保存 DeepSeek key
        r = client.post("/api/admin/model/keys", headers=HA,
                        json={"provider": "deepseek", "api_key": "sk-test-ds"})
        assert r.status_code == 200, r.text
        body = _unpack(r)
        assert body["ok"] is True and "deepseek" in body["saved"]
        assert settings.deepseek_key == "sk-test-ds"
        text = env_path.read_text(encoding="utf-8")
        assert "DEEPSEEK_API_KEY=sk-test-ds" in text
        assert "\ufeff" not in text, ".env 出现 BOM"

        # 5. 保存 Kimi 并设为当前对话模型 → 激活切换 + 热更新
        r = client.post("/api/admin/model/keys", headers=HA,
                        json={"provider": "kimi", "api_key": "sk-test-kimi", "set_active": True})
        assert r.status_code == 200, r.text
        body = _unpack(r)
        assert "kimi" in body["saved"] and "active" in body["saved"]
        assert body["active"] == "kimi"
        assert settings.active_llm_provider == "kimi"
        assert settings.llm_api_key == "sk-test-kimi"
        assert settings.llm_enabled is True
        assert settings.model_name == LLM_PROVIDERS["kimi"]["model_name"]
        text = env_path.read_text(encoding="utf-8")
        assert "KIMI_API_KEY=sk-test-kimi" in text
        assert "ACTIVE_LLM_PROVIDER=kimi" in text

        # 6. 自定义提供方：base_url + 模型名 + key
        r = client.post("/api/admin/model/keys", headers=HA, json={
            "provider": "custom",
            "api_key": "sk-test-custom",
            "set_active": True,
            "custom_base_url": "https://llm.example.com/v1",
            "custom_model_name": "my-model",
        })
        assert r.status_code == 200, r.text
        assert settings.active_provider == "custom"
        assert settings.custom_base_url == "https://llm.example.com/v1"
        assert settings.custom_model_name == "my-model"
        assert settings.model_name == "my-model"
        text = env_path.read_text(encoding="utf-8")
        assert "CUSTOM_BASE_URL=https://llm.example.com/v1" in text
        assert "CUSTOM_MODEL_NAME=my-model" in text

        # 7. 留空 key 不覆盖原值
        r = client.post("/api/admin/model/keys", headers=HA, json={"provider": "custom", "api_key": ""})
        assert r.status_code == 200, r.text
        assert settings.custom_key == "sk-test-custom"

        # 8. 非法 provider 被拒
        r = client.post("/api/admin/model/keys", headers=HA, json={"provider": "xxx", "api_key": "k"})
        assert r.status_code == 400
        r = client.post("/api/admin/model/keys/test", headers=HA, json={"provider": "xxx", "api_key": "k"})
        assert r.status_code == 400

        # 9. 自定义提供方缺 base_url/模型名时测试被拒
        settings.active_llm_provider = "deepseek"
        settings.custom_base_url = ""
        settings.custom_model_name = ""
        r = client.post("/api/admin/model/keys/test", headers=HA, json={"provider": "custom", "api_key": "k"})
        assert r.status_code == 400

        print("PASS 9/9 admin_keys 断言")
    finally:
        # 10. 还原 .env 与 settings 现场
        if backup_text is None:
            if env_path.exists():
                env_path.unlink()
        else:
            env_path.write_text(backup_text, encoding="utf-8", newline="\n")
        for f in _FIELDS:
            setattr(settings, f, orig[f])
        print("还原 .env 与配置完成")


if __name__ == "__main__":
    test_admin_keys_flow()
