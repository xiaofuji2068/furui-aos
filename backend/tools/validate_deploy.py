# -*- coding: utf-8 -*-
"""部署编排静态校验（TASK-017 / 70-02）。

本机无 Docker，无法实测容器启动；本脚本对交付物做确定性结构校验：
- docker-compose.yml：YAML 可解析 + 服务/依赖/健康检查/端口/卷齐全
- Dockerfile.backend / Dockerfile.frontend：关键指令存在
- .env.production：模板存在
用法：python tools/validate_deploy.py
"""
import io
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})


def main():
    import yaml  # pyyaml（requirements 未含时用系统包，失败即报缺依赖）

    # 1) docker-compose.yml
    compose_path = os.path.join(ROOT, "docker-compose.yml")
    try:
        with io.open(compose_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        services = cfg.get("services", {})
        check("compose 可解析", isinstance(cfg, dict))
        need = {"postgres", "backend", "frontend"}
        check("compose 三服务齐全", need.issubset(services.keys()),
              "缺: %s" % (need - set(services.keys())) or "")
        if "backend" in services:
            b = services["backend"]
            check("backend 有 build", bool(b.get("build") and b.get("build", {}).get("dockerfile") == "backend/Dockerfile"),
                  str(b.get("build")))
            check("backend 依赖 postgres healthy",
                  b.get("depends_on", {}).get("postgres", {}).get("condition") == "service_healthy")
            check("backend 有 healthcheck", bool(b.get("healthcheck")))
        if "frontend" in services:
            f = services["frontend"]
            check("frontend 端口映射 3000", f.get("ports") == ["3000:3000"], str(f.get("ports")))
            check("frontend BACKEND_URL 注入",
                  f.get("environment", {}).get("BACKEND_URL") == "http://backend:8000")
        if "postgres" in services:
            p = services["postgres"]
            check("postgres 有 healthcheck", bool(p.get("healthcheck")))
            check("postgres 数据卷", bool(p.get("volumes")))
        check("compose 有数据卷声明", bool(cfg.get("volumes")))
    except Exception as e:
        check("compose 可解析", False, str(e))

    # 2) Dockerfile
    for rel, must in (
        ("backend/Dockerfile", ["FROM python", "uvicorn", "EXPOSE 8000", "requirements.txt"]),
        ("frontend/Dockerfile", ["FROM node:20-alpine", "next", "EXPOSE 3000"]),
    ):
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        try:
            txt = io.open(p, encoding="utf-8").read()
            miss = [m for m in must if m not in txt]
            check("Dockerfile %s 关键指令" % rel, not miss, "缺: %s" % miss)
        except Exception as e:
            check("Dockerfile %s 可读" % rel, False, str(e))

    # 3) .env.production 模板
    envp = os.path.join(ROOT, ".env.production")
    check(".env.production 存在", os.path.isfile(envp))

    # 4) 部署文档
    for doc in ("docs/DEPLOYMENT.md", "docs/UPGRADE.md"):
        p = os.path.join(ROOT, doc.replace("/", os.sep))
        check("文档 %s 存在" % doc, os.path.isfile(p))

    failed = [r for r in RESULTS if not r["ok"]]
    print("DEPLOY VALIDATION: %d checks, %d fail" % (len(RESULTS), len(failed)))
    for r in RESULTS:
        print(("  [PASS] " if r["ok"] else "  [FAIL] ") + r["name"] + ((" — " + r["detail"]) if r["detail"] else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
