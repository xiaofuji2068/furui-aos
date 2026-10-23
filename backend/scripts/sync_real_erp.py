"""真实 ERP 同步脚本（env 驱动，一键切换演练 / 上线）。

所有配置从环境变量读取，密钥绝不落盘到配置文件。

必填：
  ERP_ENDPOINT      真实 ERP 的 REST 地址（如 https://erp.xxx.com/api/sales）

可选：
  ERP_AUTH_TYPE     bearer（默认）| apikey
  ERP_API_KEY       鉴权密钥（bearer 走 Authorization 头；apikey 走 X-API-Key 头）
  ERP_METHOD        GET（默认）| POST
  ERP_TIMEOUT_SEC   单请求超时秒（默认 30）
  ERP_RETRIES       网络 / 5xx 重试次数（默认 2）
  ERP_BACKOFF_SEC   退避基数（默认 0.5，第 n 次等待 0.5*2^n 秒）
  ERP_MAPPING_JSON  JSON 字符串，{entity:{json_field:column}}，ERP 字段与表列不同时必填

安全约束：
  - 默认 DRY-RUN：只拉取并打印将写入的记录数，不落库；
  - 加 --yes 才真正 materialize 进 backend/data/erp_crm.db（幂等全量覆盖四张销售表）；
  - 复用 connector.sync_source，与 API /sync、bootstrap 门控逻辑完全一致；
  - 下游只读网关的 PII 脱敏 + 只读闸门在真实数据上照样生效。

运行（演练）：
  ERP_ENDPOINT=https://erp.xxx.com/api/sales ERP_AUTH_TYPE=bearer ERP_API_KEY=xxxx \\
  python scripts/sync_real_erp.py

真实落库（确认字段映射无误后）：
  在以上命令末尾追加  --yes
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.connector as connector  # noqa: E402


def _build_config() -> dict:
    endpoint = (os.environ.get("ERP_ENDPOINT") or "").strip()
    if not endpoint:
        raise SystemExit("ERROR: 必须设置环境变量 ERP_ENDPOINT")
    auth_type = (os.environ.get("ERP_AUTH_TYPE") or "bearer").lower()
    api_key = os.environ.get("ERP_API_KEY") or os.environ.get("ERP_TOKEN") or ""
    method = (os.environ.get("ERP_METHOD") or "GET").upper()
    timeout = int(os.environ.get("ERP_TIMEOUT_SEC") or "30")
    retries = int(os.environ.get("ERP_RETRIES") or "2")
    backoff = float(os.environ.get("ERP_BACKOFF_SEC") or "0.5")
    mapping = json.loads(os.environ.get("ERP_MAPPING_JSON") or "{}")

    cfg: dict = {
        "endpoint": endpoint,
        "method": method,
        "timeout_sec": timeout,
        "retries": retries,
        "backoff_sec": backoff,
        "mapping": mapping,
    }
    if auth_type in ("bearer", "apikey"):
        if not api_key:
            print(f"WARN: ERP_AUTH_TYPE={auth_type} 但未设置 ERP_API_KEY，将以匿名方式请求"
                  f"（多数 ERP 会返回 401）")
        cfg["auth"] = {"type": auth_type, "token": api_key}
    else:
        print(f"WARN: 未知 ERP_AUTH_TYPE={auth_type}，忽略鉴权配置")
    return cfg


def main() -> int:
    ap = argparse.ArgumentParser(description="真实 ERP 同步（env 驱动，默认 DRY-RUN）")
    ap.add_argument("--yes", action="store_true", help="真正落库；不加则仅 DRY-RUN 打印记录数")
    args = ap.parse_args()

    try:
        cfg = _build_config()
    except SystemExit as e:
        print(e)
        return 2
    src_id = "real-erp"

    # ---- DRY-RUN：只拉取，不物化 ----
    if not args.yes:
        try:
            c = connector.build_connector("rest", cfg)
            records = c.pull()
        except Exception as e:  # noqa: BLE001
            print(f"DRY-RUN 拉取失败：{e}")
            return 1
        total = sum(len(v) for v in records.values())
        print(f"[DRY-RUN] 端点 {cfg['endpoint']} 拉取成功，共 {total} 条记录：")
        for k, v in records.items():
            print(f"    - {k}: {len(v)} 条")
        print("未落库。确认字段映射与记录数无误后，在命令末尾追加 --yes 执行真实 materialize"
              "（幂等全量覆盖 erp_crm.db 四张销售表）。")
        return 0

    # ---- 真实落库 ----
    source = {"id": src_id, "name": "真实 ERP", "type": "rest", "config": cfg}
    res = connector.sync_source(src_id, source)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get("ok"):
        print("同步失败：既有数据未被改动。请检查端点 / 凭证 / 字段映射后重试。")
        return 1
    print(f"已 materialize 进 erp_crm.db：{res.get('counts')}")
    print("下游销售主线 / 只读网关 / PII 脱敏在真实数据上自动复用，无需额外改动。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
