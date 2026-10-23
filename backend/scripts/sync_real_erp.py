"""真实 ERP 同步脚本（env 驱动，一键切换演练 / 上线）。

所有敏感配置优先从环境变量读取，密钥绝不落盘到配置文件。
支持两种用法：
  A. 纯 env 驱动（默认）：ERP_ENDPOINT / ERP_AUTH_TYPE / ERP_API_KEY / ERP_MAPPING_JSON ...
  B. 模板配置驱动：--config erp_source_template.json（填好端点/鉴权/映射），env 仍可覆盖。

安全约束：
  - 默认 DRY-RUN：只拉取并打印将写入的记录数，不落库；
  - 加 --yes 才真正 materialize 进 backend/data/erp_crm.db（幂等全量覆盖四张销售表）；
  - 复用 connector.sync_source，与 API /sync、bootstrap 门控逻辑完全一致；
  - 下游只读网关的 PII 脱敏 + 只读闸门在真实数据上照样生效。

运行（演练，纯 env）：
  ERP_ENDPOINT=https://erp.xxx.com/api/sales ERP_AUTH_TYPE=bearer ERP_API_KEY=xxxx \\
  python scripts/sync_real_erp.py

运行（演练，模板驱动）：
  python scripts/sync_real_erp.py --config scripts/erp_source_template.json

真实落库（确认字段映射无误后）：在以上命令末尾追加  --yes
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.connector as connector  # noqa: E402


def _load_base_config(config_path: str | None) -> dict:
    """加载基础配置：--config 优先；否则要求 ERP_ENDPOINT 在 env 中。"""
    if config_path:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 丢弃模板里的 _说明 等说明键（connector 本就忽略，但保持干净）
        cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
        # 模板里的 auth 可能写 {"type":"bearer","env":"ERP_API_KEY"}，运行时由 connector 取 env；
        # 若 env 同时给了 ERP_API_KEY，下面 _apply_env_overrides 会用 token 覆盖。
        return cfg
    endpoint = (os.environ.get("ERP_ENDPOINT") or "").strip()
    if not endpoint:
        raise SystemExit("ERROR: 未指定 --config 且未设置环境变量 ERP_ENDPOINT")
    return {"endpoint": endpoint, "method": "GET"}


def _apply_env_overrides(cfg: dict) -> dict:
    """env 覆盖模板：endpiont / 鉴权 / method / 超时 / 重试 / 映射。"""
    endpoint = (os.environ.get("ERP_ENDPOINT") or "").strip()
    if endpoint:
        cfg["endpoint"] = endpoint
    auth_type = (os.environ.get("ERP_AUTH_TYPE") or "").lower()
    api_key = os.environ.get("ERP_API_KEY") or os.environ.get("ERP_TOKEN")
    if auth_type or api_key:
        if not auth_type:
            auth_type = (cfg.get("auth") or {}).get("type", "bearer")
        cfg["auth"] = {"type": auth_type, "token": api_key or ""}
    if os.environ.get("ERP_METHOD"):
        cfg["method"] = os.environ["ERP_METHOD"].upper()
    if os.environ.get("ERP_TIMEOUT_SEC"):
        cfg["timeout_sec"] = int(os.environ["ERP_TIMEOUT_SEC"])
    if os.environ.get("ERP_RETRIES"):
        cfg["retries"] = int(os.environ["ERP_RETRIES"])
    if os.environ.get("ERP_BACKOFF_SEC"):
        cfg["backoff_sec"] = float(os.environ["ERP_BACKOFF_SEC"])
    if os.environ.get("ERP_MAPPING_JSON"):
        cfg["mapping"] = json.loads(os.environ["ERP_MAPPING_JSON"])
    return cfg


def _validate(cfg: dict) -> None:
    if not (cfg.get("endpoint") or "").strip():
        raise SystemExit("ERROR: 最终配置缺少 endpoint")
    auth = cfg.get("auth") or {}
    if auth.get("type") in ("bearer", "apikey"):
        token = auth.get("token") or os.environ.get(auth.get("env", ""), "")
        if not token:
            print(f"WARN: auth.type={auth['type']} 但未提供密钥，将以匿名方式请求"
                  f"（多数 ERP 会返回 401）")


def main() -> int:
    ap = argparse.ArgumentParser(description="真实 ERP 同步（env / 模板驱动，默认 DRY-RUN）")
    ap.add_argument("--config", help="模板配置文件路径（如 scripts/erp_source_template.json）")
    ap.add_argument("--yes", action="store_true", help="真正落库；不加则仅 DRY-RUN 打印记录数")
    args = ap.parse_args()

    try:
        cfg = _apply_env_overrides(_load_base_config(args.config))
        _validate(cfg)
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
