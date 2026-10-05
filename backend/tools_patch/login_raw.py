# -*- coding: utf-8 -*-
import json, urllib.request
BASE = "http://127.0.0.1:8000/api"
out = []
req = urllib.request.Request(BASE + "/auth/login", method="POST")
req.add_header("Content-Type", "application/json")
data = json.dumps({"username": "admin", "password": "123456"}).encode()
try:
    with urllib.request.urlopen(req, data=data, timeout=20) as r:
        body = r.read().decode()
        out.append("STATUS %s" % r.status)
        out.append("BODY: %s" % body[:800])
except urllib.error.HTTPError as e:
    out.append("HTTP %s BODY %s" % (e.code, e.read().decode()[:800]))
open(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tools_patch\login_raw.txt", "w", encoding="utf-8").write("\n".join(out))
