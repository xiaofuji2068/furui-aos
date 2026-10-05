# -*- coding: utf-8 -*-
import json, urllib.request

BASE = "http://127.0.0.1:8000/api"
out = []

def call(method, path, body=None, token=None, timeout=20):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"detail": str(e)}

def unwrap(resp):
    if isinstance(resp, dict) and "data" in resp:
        return resp["data"]
    return resp

# 1) 登录
st, resp = call("POST", "/auth/login", {"username": "admin", "password": "123456"})
data = unwrap(resp)
token = data.get("token", "") if isinstance(data, dict) else ""
out.append("LOGIN %s token=%s" % (st, bool(token)))

# 2) 资产目录
st, resp = call("GET", "/assets/bundles", token=token)
items = (unwrap(resp) or {}).get("items", []) if isinstance(unwrap(resp), dict) else []
out.append("BUNDLES %s count=%d" % (st, len(items)))
for b in items:
    out.append("  - %s %s v%s %s installed=%s nav=%s" % (
        b.get("code"), b.get("name"), b.get("version"), b.get("status"),
        b.get("installed"), (b.get("nav_entry") or {}).get("label")))

# 3) 安装第一个 published 未装 bundle
target = next((b for b in items if b.get("status") == "published" and not b.get("installed")), None)
if target:
    st, resp = call("POST", "/assets/install", {"bundle_id": target["id"]}, token=token)
    inst = unwrap(resp)
    out.append("INSTALL %s code=%s created=%s pages=%d graphs=%d" % (
        st, target["code"], inst.get("created"), len(inst.get("derived_pages", [])), len(inst.get("derived_graphs", []))))
    # 4) installed-nav
    st, resp = call("GET", "/assets/installed-nav", token=token)
    navs = (unwrap(resp) or {}).get("items", []) if isinstance(unwrap(resp), dict) else []
    out.append("INSTALLED-NAV %s count=%d" % (st, len(navs)))
    for n in navs:
        out.append("  - %s %s href=%s" % (n.get("icon"), n.get("label"), n.get("href")))
    # 5) 派生页可访问（运行时页）
    if navs:
        href = navs[0].get("href", "")
        if href.startswith("/pages/"):
            code = href.rsplit("/", 1)[-1]
            st, resp = call("GET", "/pages/by-code/" + code, token=token)
            pg = unwrap(resp)
            out.append("DERIVED-PAGE %s code=%s title=%s widgets=%d" % (
                st, code, pg.get("title"), len(pg.get("layout", []))))
    # 6) 已安装列表
    st, resp = call("GET", "/assets/installed", token=token)
    instl = (unwrap(resp) or {}).get("items", []) if isinstance(unwrap(resp), dict) else []
    out.append("INSTALLED %s count=%d" % (st, len(instl)))
else:
    out.append("NO TARGET BUNDLE (全部已装)")

open(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tools_patch\api_e2e.txt", "w", encoding="utf-8").write("\n".join(out))
