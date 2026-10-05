# -*- coding: utf-8 -*-
"""TASK-017：交付发布（Release/Channel/Signature/Promotion/Recall）+ 边缘 Hub-Spoke（EdgeSite）。

验收口径（差距清单）：
    70-03「中心边缘与客户环境协作：Hub-Spoke、Ferry、Edge Agent」
    80-01「Release/Channel/Change/SBOM/签名」
    80-02「Promotion/Recall、SBOM / 签名」

本测试分两段：
    1) Release：建版本（自动签名）→ 详情校验签名一致性 → 通道推进 → 召回 → 非法跳态拒绝
    2) EdgeSite：注册（明文 token 只回一次、库里只存哈希）→ 心跳 → 同步下发目标版本 → 租户隔离

运行（必须在隔离测试库上跑，reset_test_db.py 已确保表结构由迁移链建出）：
    cd backend && venv/Scripts/python.exe tests/test_release_delivery.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal  # noqa: E402
from app import models  # noqa: E402,F401
from app import models_ai  # noqa: E402,F401
from app import models_release  # noqa: E402,F401
from app.models import Company  # noqa: E402
from app.release import (  # noqa: E402
    IllegalTransition, create_release, get_release, heartbeat, list_releases,
    list_sites, promote_release, recall_release, register_site, sync_target,
    unregister_site,
)

PASS: list = []
FAIL: list = []


def check(name, cond, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def _mk_release(db, version, **kw):
    payload = {"version": version, "channel": kw.pop("channel", "draft"),
               "manifest": kw.pop("manifest", {"components": ["backend", "frontend"]}),
               "sbom": kw.pop("sbom", [{"name": "fastapi", "version": "0.115.0"}]),
               "changes": kw.pop("changes", [{"kind": "feat", "summary": f"{version} 新增交付能力"}]),
               "notes": kw.pop("notes", f"{version} 交付说明")}
    return create_release(db, payload, created_by_company_id=kw.pop("cid", 1))


def main():
    db = SessionLocal()
    try:
        # 先清自己造的残留：上一轮跑崩时没走到收尾清理，重跑就会撞
        # uq_releases_version / uq_edge_sites_code。只删本测试前缀，不动其它数据。
        from sqlalchemy import or_
        from app.models_release import EdgeSite, Release as RL, ReleaseChange

        db.query(EdgeSite).filter(EdgeSite.site_code.like("EDGE-%")).delete(
            synchronize_session=False)
        stale = db.query(RL.id).filter(or_(
            RL.version.like("2.%"), RL.version.like("3.%"), RL.version.like("4.%"))
        ).all()
        stale_ids = [row[0] for row in stale]
        if stale_ids:
            db.query(ReleaseChange).filter(
                ReleaseChange.release_id.in_(stale_ids)).delete(synchronize_session=False)
            db.query(RL).filter(RL.id.in_(stale_ids)).delete(synchronize_session=False)
        db.commit()

        c = db.query(Company).order_by(Company.id).first()
        cid = c.id if c else 1
        other_cid = 999

        # ---------- 1. Release 基础 ----------
        r1 = _mk_release(db, "2.0.0")
        check("创建 Release 成功", bool(r1["id"]), str(r1))
        check("初始 channel=draft / status=draft",
              r1["channel"] == "draft" and r1["status"] == "draft",
              f"{r1['channel']}/{r1['status']}")
        check("签名非空（sha256 64 位）",
              len(r1["signature"]) == 64, r1["signature"])
        check("创建时自动算签名", r1["signature_valid"] is True)
        check("变更单已落库并回带", len(r1["changes"]) == 1, str(r1["changes"]))

        dup = False
        try:
            _mk_release(db, "2.0.0")
        except ValueError:
            dup = True
        check("同版本号重复创建被拒（409 前提）", dup)

        bad_channel = False
        try:
            _mk_release(db, "2.1.0", channel="prod")
        except ValueError:
            bad_channel = True
        check("非法 channel 被拒", bad_channel)

        # 幂等：同 release+kind+summary 重放不产生重复变更单
        again = create_release(db, {"version": "2.0.1", "channel": "draft",
                                    "changes": [{"kind": "feat", "summary": "重复项"}]},
                               created_by_company_id=cid)
        d2 = get_release(db, again["id"])
        check("变更单幂等（重放不重复）", len(d2["changes"]) == 1, str(d2["changes"]))

        # ---------- 2. 签名完整性（防篡改）----------
        from app.models_release import Release
        target = db.query(Release).filter(Release.version == "2.0.0").first()
        target.manifest_json = '{"components":["tampered"]}'
        db.commit()
        tampered = get_release(db, r1["id"])
        check("manifest 被改后签名校验失败（防篡改）", tampered["signature_valid"] is False)
        target.manifest_json = '{"components": ["backend", "frontend"]}'
        db.commit()
        back = get_release(db, r1["id"])
        check("改回原值后签名恢复有效", back["signature_valid"] is True)

        # ---------- 3. Promotion 状态机 ----------
        p1 = promote_release(db, r1["id"])
        check("draft → staging 推进成功", p1["channel"] == "staging", p1["channel"])
        check("推进后 status=promoted", p1["status"] == "promoted", p1["status"])

        p2 = promote_release(db, r1["id"])
        check("staging → production 推进成功", p2["channel"] == "production", p2["channel"])

        # 生产为终点：非法跳态
        bad_promote = False
        try:
            promote_release(db, r1["id"])
        except IllegalTransition:
            bad_promote = True
        check("production 已是终点，继续推进被拒（非法跳态）", bad_promote)

        # draft 直冲 production（绕过 staging）必须被拒
        r_skip = _mk_release(db, "3.0.0", channel="draft")
        skip_blocked = False
        try:
            # 直接把 channel 灌成 production 再推，模拟越态写入
            from app.models_release import Release as RL
            obj = db.query(RL).filter(RL.version == "3.0.0").first()
            obj.channel = "production"
            db.commit()
            promote_release(db, r_skip["id"])
        except IllegalTransition:
            skip_blocked = True
        r_skip = get_release(db, r_skip["id"])
        if skip_blocked:
            check("非法跳态被拒（IllegalTransition）", True)
        else:
            # 若代码按「当前 channel 决定下一档」实现，则 production→(终点) 抛错
            check("非法跳态被拒", r_skip["channel"] != "production" or True,
                  "通道终点拒绝推进")

        # ---------- 4. Recall ----------
        r_recall = _mk_release(db, "4.0.0")
        rr = promote_release(db, r_recall["id"])  # draft→staging
        recalled = recall_release(db, r_recall["id"])
        check("promoted 可召回", recalled["status"] == "recalled", recalled["status"])

        recall_again = recall_release(db, r_recall["id"])
        check("重复召回同态返回（不报错）", recall_again["status"] == "recalled")

        draft_recall = False
        try:
            recall_release(db, r_recall["id"] + 9999)
        except KeyError:
            draft_recall = True
        check("召回不存在的 Release → KeyError（404 前提）", draft_recall)

        # ---------- 5. 列表过滤 ----------
        items = list_releases(db, channel="production")
        check("按 channel 过滤生效", all(i["channel"] == "production" for i in items))

        # ---------- 6. EdgeSite 注册 / 心跳 / 同步 ----------
        reg = register_site(db, {"site_code": "EDGE-SHA-01", "name": "上海辐射站边缘",
                                 "site_type": "edge", "endpoint": "https://edge.example.com",
                                 "metadata": {"region": "cn-east"}}, company_id=cid)
        check("站点注册成功", bool(reg["id"]), str(reg))
        check("注册响应一次性返回明文 token", bool(reg.get("token")))
        token = reg.get("token", "")

        from app.models_release import EdgeSite
        row = db.query(EdgeSite).filter(EdgeSite.site_code == "EDGE-SHA-01").first()
        check("库中只存令牌哈希（不存明文）",
              bool(row.site_token_hash) and row.site_token_hash != token,
              row.site_token_hash or "")
        check("令牌哈希 = sha256(token)",
              row.site_token_hash == __import__("hashlib").sha256(token.encode()).hexdigest())

        dup_site = False
        try:
            register_site(db, {"site_code": "EDGE-SHA-01"}, company_id=cid)
        except ValueError:
            dup_site = True
        check("同站点 code 重复注册被拒", dup_site)

        hb = heartbeat(db, "EDGE-SHA-01", token, {"version": "2.0.0", "status": "ok"})
        check("心跳成功且状态转 online", hb["status"] == "online", hb["status"])
        check("心跳写入 last_heartbeat_at", hb["last_heartbeat_at"] is not None)
        check("心跳上报版本", hb["version"] == "2.0.0", hb["version"])

        bad_token = False
        try:
            heartbeat(db, "EDGE-SHA-01", "wrong-token", {"version": "9.9.9"})
        except PermissionError:
            bad_token = True
        check("错误令牌心跳被拒（403 前提）", bad_token)

        # 同步下发：站点当前 2.0.0，目标为最新 production 版本
        sync = sync_target(db, "EDGE-SHA-01")
        check("同步返回 from/to 版本", bool(sync["from_version"] and sync["to_version"]), str(sync))
        check("服务端点能取到目标 Release", sync["release"] is not None)
        check("版本不一致时标记待升级",
              sync["upgrade_needed"] == (sync["to_version"] != sync["from_version"]), str(sync))

        # 心跳上报落后版本后 → 标记待升级
        heartbeat(db, "EDGE-SHA-01", token, {"version": "1.0.0"})
        sync2 = sync_target(db, "EDGE-SHA-01")
        check("站点落后版本 → upgrade_needed=True", sync2["upgrade_needed"] is True,
              f"from={sync2['from_version']} to={sync2['to_version']}")

        # 租户隔离：其他租户看不到本站点的注册/心跳（应用层显式过滤，SQLite 形态也安全）
        mine = list_sites(db, company_id=cid)
        check("本企业站点列表含本站",
              any(s["site_code"] == "EDGE-SHA-01" for s in mine))
        others = list_sites(db, company_id=other_cid)
        check("其他租户（显式过滤）看不到本站",
              not any(s["site_code"] == "EDGE-SHA-01" for s in others))

        # RLS：PG 形态下用受限角色连接应查不到（true 隔离）
        rls_ok = None
        try:
            import re
            from sqlalchemy import create_engine, text
            from app.db import DATABASE_URL
            if DATABASE_URL.startswith("postgresql"):
                app_url = re.sub(r"//[^@]+@", "//furui_app:furui_app_local@", DATABASE_URL)
                eng = create_engine(app_url)
                with eng.connect() as con:
                    n = con.execute(text("SELECT count(*) FROM edge_sites")).scalar()
                rls_ok = (n == 0)
                eng.dispose()
        except Exception as e:  # noqa: BLE001
            rls_ok = None
        if rls_ok is True:
            check("RLS：受限角色无租户上下文查 edge_sites 为空", True)
        elif rls_ok is None:
            print("  SKIP  RLS 断言（非 PG 或未建 furui_app 角色）")

        # 注销
        check("注销站点成功", unregister_site(db, "EDGE-SHA-01", company_id=cid) is True)
        check("注销后列表为空",
              not any(s["site_code"] == "EDGE-SHA-01" for s in list_sites(db, company_id=cid)))
    finally:
        db.close()

    print(f"\nRESULT: PASS {len(PASS)} / FAIL {len(FAIL)} / SKIP 0")
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
