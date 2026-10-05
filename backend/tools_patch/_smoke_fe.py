import os, sys, json, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import SessionLocal
from app.auth import authenticate, issue_token
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
B = "http://127.0.0.1:8000/api"

def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(B + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with OP.open(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:160]

db = SessionLocal()
_u = authenticate(db, "admin", "123456")
token = issue_token(_u)
user = _u
print("login company_id =", user.company_id)
st, d = call("GET", "/releases", token)
rs = (d.get("data") or {}).get("items", [])
print("GET /releases ->", st, "count =", len(rs))
for r in rs[:4]:
    print("   v%s ch=%s st=%s sig_valid=%s changes=%d" % (r["version"], r["channel"], r["status"], r["signature_valid"], len(r["changes"] or [])))

st, d = call("GET", "/edge-sites", token)
sites = (d.get("data") or {}).get("items", [])
print("GET /edge-sites ->", st, "count =", len(sites))
for s in sites[:3]:
    print("   %s status=%s version=%s hb=%s" % (s["site_code"], s["status"], s["version"], "yes" if s["last_heartbeat_at"] else "no"))

if sites:
    code = sites[0]["site_code"]
    st, d = call("GET", "/edge-sites/%s/sync" % code, token)
    dd = d.get("data") or {}
    print("GET sync(%s) ->" % code, st, "from=%s to=%s need=%s" % (dd.get("from_version"), dd.get("to_version"), dd.get("upgrade_needed")))
    st, d = call("DELETE", "/edge-sites/%s" % code, token)
    print("DELETE site(%s) ->" % code, st, (d.get("data") if isinstance(d, dict) else d))
    st, d = call("GET", "/edge-sites", token)
    print("after delete count =", len((d.get("data") or {}).get("items", [])))
