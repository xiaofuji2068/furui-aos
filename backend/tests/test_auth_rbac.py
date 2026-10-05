"""P0-001 / P0-002 验收测试。

覆盖：
- TASK-002 用户与企业体系：登录 / 退出 / 用户信息 / 企业隔离 / 部门隔离
- TASK-003 权限系统 RBAC：权限点守卫 / 数据范围 / 角色权限编辑

运行：
    backend/venv/Scripts/python.exe tests/test_auth_rbac.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Company, User  # noqa: E402

client: TestClient | None = None

PASS, FAIL = [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def login(username: str, password: str = "123456"):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    return r


def bearer(username: str) -> dict:
    r = login(username)
    assert r.status_code == 200, f"登录失败 {username}: {r.text}"
    token = r.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def main():
    """用 with 触发 lifespan，确保建表与种子数据已执行。"""
    global client
    with TestClient(app) as c:
        client = c
        return _run()


def _run():
    db = SessionLocal()
    cid = getattr(db.query(Company).order_by(Company.id).first(), "id", 1)
    print("\n=== TASK-002 用户登录 / 信息 / 退出 ===")

    r = login("admin")
    check("admin 登录成功", r.status_code == 200, r.text[:120])
    body = r.json()
    check("统一返回格式 code=0", body.get("code") == 0)
    check("返回 token", bool(body["data"].get("token")))
    check("返回用户信息", body["data"]["user"]["username"] == "admin")

    check("错误密码被拒绝", login("admin", "wrong-password").status_code == 401)
    check("不存在用户被拒绝", login("nobody").status_code == 401)

    h_admin = bearer("admin")
    r = client.get("/api/auth/me", headers=h_admin)
    check("GET /auth/me 返回当前用户", r.status_code == 200 and r.json()["data"]["username"] == "admin")
    check("me 含企业信息", r.json()["data"]["company"]["code"] == "FURUI")
    check("me 含权限清单", len(r.json()["data"]["permissions"]) > 0)

    check("未带 token 访问 /auth/me 返回 401", client.get("/api/auth/me").status_code == 401)
    check("伪造 token 被拒绝",
          client.get("/api/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401)

    print("\n=== TASK-002 数据隔离：不同用户看到不同企业 / 部门 ===")

    h_guest = bearer("guest")            # 演示企业A 的管理员
    h_sales = bearer("sales")            # 傅瑞 销售部 业务负责人
    h_analyst = bearer("analyst")        # 傅瑞 财务部 数据分析师

    r_admin = client.get("/api/org/companies", headers=h_admin).json()["data"]["items"]
    r_guest = client.get("/api/org/companies", headers=h_guest).json()["data"]["items"]
    check("admin 可见全部企业(2家)", len(r_admin) == 2, str(len(r_admin)))
    check("guest 仅可见本企业(1家)", len(r_guest) == 1, str(len(r_guest)))
    check("guest 看到的是演示企业A", r_guest[0]["code"] == "DEMO-A")

    r_admin_u = client.get("/api/org/users", headers=h_admin).json()["data"]["items"]
    r_guest_u = client.get("/api/org/users", headers=h_guest).json()["data"]["items"]
    check("admin 可见全部用户(5)", len(r_admin_u) == 5, str(len(r_admin_u)))
    check("guest 仅可见本企业用户(1)", len(r_guest_u) == 1, str(len(r_guest_u)))

    r_guest_d = client.get("/api/org/departments", headers=h_guest).json()["data"]["items"]
    check("guest 仅可见本企业部门", all(d["company_id"] != 1 for d in r_guest_d))

    print("\n=== TASK-003 RBAC 权限守卫 ===")

    # analyst 无 user:manage，不能创建用户
    r = client.post("/api/org/users", headers=h_analyst,
                    json={"username": "hacker", "password": "123456"})
    check("无 user:manage 时创建用户被拒(403)", r.status_code == 403, f"{r.status_code} {r.text[:100]}")

    # admin 有 user:manage，可创建（幂等：先清历史残留 tester）
    db.query(User).filter(User.username == "tester").delete(synchronize_session=False)
    db.commit()
    r = client.post("/api/org/users", headers=h_admin,
                    json={"username": "tester", "password": "123456", "name": "测试员",
                          "company_id": cid, "department_id": 1, "role_ids": []})
    check("admin 创建用户成功", r.status_code == 200, r.text[:120])
    new_uid = r.json()["data"]["id"] if r.status_code == 200 else None

    # 重名冲突
    r = client.post("/api/org/users", headers=h_admin,
                    json={"username": "tester", "password": "123456"})
    check("重名用户返回 409", r.status_code == 409)

    # 无权限不能改角色权限
    r = client.put("/api/org/roles/1", headers=h_analyst,
                   json={"code": "x", "name": "x", "permission_codes": []})
    check("无 role:manage 时改角色被拒(403)", r.status_code == 403, str(r.status_code))

    # 权限目录
    r = client.get("/api/org/permissions", headers=h_analyst).json()["data"]
    check("权限目录按 scope 分组", len(r["catalog"]) >= 5, str(list(r["catalog"].keys())))
    check("返回当前用户权限 mine", len(r["mine"]) > 0)

    print("\n=== TASK-003 权限差异化：不同角色功能权限不同 ===")

    pa = set(client.get("/api/auth/me", headers=h_admin).json()["data"]["permissions"])
    ps = set(client.get("/api/auth/me", headers=h_sales).json()["data"]["permissions"])
    pn = set(client.get("/api/auth/me", headers=h_analyst).json()["data"]["permissions"])
    check("admin 权限 > sales 权限", pa > ps, f"{len(pa)} vs {len(ps)}")
    check("sales 与 analyst 权限不同", ps != pn)
    check("sales(owner) 有执行权", "employee:execute" in ps)
    check("sales(owner) 无用户管理权", "user:manage" not in ps)
    check("analyst 无知识写入权", "knowledge:write" not in pn)

    print("\n=== 跨企业越权访问阻断 ===")
    # 用 PUT 越权改傅瑞企业（该路径只有 PUT/DELETE，GET 不存在会返回 405）
    r = client.put("/api/org/companies/1", headers=h_guest,
                   json={"name": "被篡改", "code": "HACK", "status": "active"})
    check("guest 篡改傅瑞企业被拒(403)", r.status_code == 403, str(r.status_code))

    r = client.get(f"/api/org/departments?company_id={cid}", headers=h_guest)
    check("guest 查询傅瑞部门被拒(403)", r.status_code == 403, str(r.status_code))

    # 超管应能跨企业
    _cos = db.query(Company).order_by(Company.id).all()
    other_cid = _cos[1].id if len(_cos) > 1 else cid
    r = client.get(f"/api/org/departments?company_id={other_cid}", headers=h_admin)
    check("超管可查询其他企业部门", r.status_code == 200, str(r.status_code))

    print("\n=== 清理 ===")
    if new_uid:
        r = client.delete(f"/api/org/users/{new_uid}", headers=h_admin)
        check("删除测试用户成功", r.status_code == 200, r.text[:100])

    print("\n" + "=" * 56)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print(f"  - {f}")
    print("=" * 56)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
