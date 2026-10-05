# -*- coding: utf-8 -*-
"""SBOM 生成（TASK-017 / 80-01）。

从 requirements.txt（后端）+ package-lock.json（前端）生成 SPDX-lite 格式 SBOM，
供交付审计与 Release 签名使用（signature = sha256(bom 内容)，落 Release.manifest）。

用法：
  python tools/sbom.py                          # 输出到 docs/sbom.json（默认）
  python tools/sbom.py --out sbom.json          # 指定输出路径
  python tools/sbom.py --check                  # 仅校验依赖可解析（CI 用）
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def parse_req(path):
    """解析 requirements.txt：name==version / name>=x / name（无版本标 unknown）。"""
    out = []
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            m = re.match(r"^([A-Za-z0-9_.\-]+)\s*(?:==|>=|<=|~=)\s*([\w.\-]+)", line)
            if m:
                out.append({"name": m.group(1).lower(), "version": m.group(2)})
            else:
                out.append({"name": line.split(" ")[0].lower(), "version": "unknown"})
    return out


def parse_lock(path):
    """解析 package-lock.json packages 段（npm lockfile v2/v3）。"""
    out = []
    with io.open(path, encoding="utf-8") as f:
        lock = json.load(f)
    pkgs = lock.get("packages", {})
    for key, meta in pkgs.items():
        if not key or key == "":
            continue  # 跳过根包
        if key.count("node_modules/") != 1:
            continue  # 跳过嵌套展开（node_modules/a/node_modules/b）
        name = key.split("node_modules/")[-1]
        ver = meta.get("version", "unknown")
        if name and ver:
            out.append({"name": name, "version": ver})
    return out


def purl(kind, name, version):
    return "pkg:%s/%s@%s" % (kind, name, version)


def build_sbom():
    req_path = os.path.join(ROOT, "backend", "requirements.txt")
    lock_path = os.path.join(ROOT, "frontend", "package-lock.json")
    reqs = parse_req(req_path) if os.path.isfile(req_path) else []
    locks = parse_lock(lock_path) if os.path.isfile(lock_path) else []
    components = (
        [{"type": "library", "name": c["name"], "version": c["version"], "purl": purl("pypi", c["name"], c["version"])} for c in reqs]
        + [{"type": "library", "name": c["name"], "version": c["version"], "purl": purl("npm", c["name"], c["version"])} for c in locks]
    )
    doc = {
        "bomFormat": "SPDX",
        "specVersion": "SPDX-2.3",
        "version": "1.0",
        "documentNamespace": "https://furui.tech/sbom/furui-aios",
        "name": "furui-aios",
        "metadata": {
            "tool": {"name": "tools/sbom.py", "version": "1.0"},
            "component": {"name": "furui-aios", "version": "2.0.0", "type": "application"},
        },
        "components": components,
    }
    return doc, len(reqs), len(locks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "sbom.json"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    doc, n_req, n_lock = build_sbom()
    if args.check:
        print("SBOM CHECK: backend %d, frontend %d, total %d" % (n_req, n_lock, len(doc["components"])))
        return 0 if doc["components"] else 1

    out = args.out if os.path.isabs(args.out) else os.path.join(os.getcwd(), args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    body = json.dumps(doc, ensure_ascii=False, indent=2)
    with io.open(out, "w", encoding="utf-8") as f:
        f.write(body)
    sig = hashlib.sha256(body.encode("utf-8")).hexdigest()
    print("SBOM written: %s" % out)
    print("components: backend %d + frontend %d = %d" % (n_req, n_lock, len(doc["components"])))
    print("sha256: %s" % sig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
