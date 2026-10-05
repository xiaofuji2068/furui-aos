# -*- coding: utf-8 -*-
import json, urllib.request
B = "http://127.0.0.1:8000"

def call(path, method="GET", body=None, token=None, timeout=20):
    req = urllib.request.Request(B + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        try:
            return getattr(e, "code", "ERR"), str(e.read().decode("utf-8", "replace")[:300] if hasattr(e, "read") else e)
        except Exception:
            return "ERR", str(e)

out = []
s, b = call("/api/health"); out.append(("health", s, b[:300]))
s, b = call("/api/auth/login", "POST", {"username": "admin", "password": "123456"}); out.append(("login", s, b[:120]))
token = None
try:
    token = json.loads(b)["data"]["token"]
except Exception as e:
    out.append(("token-parse", "ERR", repr(e)[:200]))
if token:
    for path in ("/api/pages/widget-types", "/api/pages", "/api/logic/graphs"):
        s, b = call(path, token=token)
        out.append((path, s, b[:700]))
else:
    out.append(("pages", "NO_TOKEN", ""))
with open(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tools_patch\verify_pg_result.txt", "w", encoding="utf-8") as f:
    for name, s, b in out:
        f.write(f"===== {name} [{s}] =====\n{b}\n")
print("DONE")