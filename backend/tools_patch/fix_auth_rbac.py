# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_auth_rbac.py")
t = p.read_text(encoding="utf-8")

pairs = [
    # 1) 创建 tester 前幂等清理残留
    ('    # admin 有 user:manage，可创建\n    r = client.post("/api/org/users", headers=h_admin,',
     '    # admin 有 user:manage，可创建（幂等：先清历史残留 tester）\n'
     '    db.query(User).filter(User.username == "tester").delete(synchronize_session=False)\n'
     '    db.commit()\n'
     '    r = client.post("/api/org/users", headers=h_admin,'),
    # 2) 创建用户公司动态
    ('"company_id": 1, "department_id": 1, "role_ids": []}',
     '"company_id": cid, "department_id": 1, "role_ids": []}'),
    # 3) guest 查傅瑞部门：f-string 真参数
    ('r = client.get("/api/org/departments?company_id=cid", headers=h_guest)',
     'r = client.get(f"/api/org/departments?company_id={cid}", headers=h_guest)'),
    # 4) 超管查他企：动态第二企业
    ('    # 超管应能跨企业\n    r = client.get("/api/org/departments?company_id=2", headers=h_admin)',
     '    # 超管应能跨企业\n'
     '    _cos = db.query(Company).order_by(Company.id).all()\n'
     '    other_cid = _cos[1].id if len(_cos) > 1 else cid\n'
     '    r = client.get(f"/api/org/departments?company_id={other_cid}", headers=h_admin)'),
]
for old, new in pairs:
    if old in t:
        t = t.replace(old, new, 1)
        print("OK:", old.splitlines()[0][:50])
    else:
        print("MISS:", old.splitlines()[0][:50])
p.write_text(t, encoding="utf-8")
ast.parse(t)
print("SYNTAX OK")