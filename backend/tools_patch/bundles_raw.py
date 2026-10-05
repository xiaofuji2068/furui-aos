# -*- coding: utf-8 -*-
import json, urllib.request
BASE = "http://127.0.0.1:8000/api"
out = []
req = urllib.request.Request(BASE + "/auth/login", method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req, data=json.dumps({"username": "admin", "password": "123456"}).encode(), timeout=20) as r:
    token = json.loads(r.read().decode())["data"]["token"]
out.append("LOGIN OK")
req2 = urllib.request.Request(BASE + "/assets/bundles")
req2.add_header("Authorization", "Bearer " + token)
with urllib.request.urlopen(req2, timeout=20) as r:
    out.append("BUNDLES RAW: " + r.read().decode()[:1500])
open(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tools_patch\bundles_raw.txt", "w", encoding="utf-8").write("\n".join(out))
