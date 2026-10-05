"""安全工具 — 密码哈希 + JWT（零第三方依赖，仅标准库）。

不引 bcrypt/passlib：避免 Windows 上编译失败；
不引 PyJWT：HS256 用 hmac 手写即可，减少部署依赖。
密码用 PBKDF2-HMAC-SHA256 + 随机盐，迭代 120k 次。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Optional

from .config import settings

# JWT 密钥：优先读环境变量，缺省派生一个稳定值（开发模式）
JWT_SECRET = os.getenv("JWT_SECRET") or (settings.openai_api_key or "furui-aios-dev-secret") + "::jwt"
JWT_TTL_SECONDS = 60 * 60 * 12          # 12 小时
PBKDF2_ITERATIONS = 120_000


# ---------------- 密码 ----------------

def hash_password(raw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(raw: str, encoded: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = encoded.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", raw.encode("utf-8"), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ---------------- JWT (HS256) ----------------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(header_b64: str, payload_b64: str) -> str:
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return _b64url(sig)


def create_token(payload: Dict[str, Any], ttl: int = JWT_TTL_SECONDS) -> str:
    now = int(time.time())
    full = {"iat": now, "exp": now + ttl, **payload}
    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url(json.dumps(full, separators=(",", ":"), default=str).encode("utf-8"))
    return f"{h_b64}.{p_b64}.{_sign(h_b64, p_b64)}"


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """校验签名与过期时间；失败返回 None。"""
    try:
        h_b64, p_b64, sig = token.split(".")
        if not hmac.compare_digest(_sign(h_b64, p_b64), sig):
            return None
        payload = json.loads(_b64url_decode(p_b64))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None
