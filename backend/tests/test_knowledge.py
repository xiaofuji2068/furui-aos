"""知识中心验收（TASK-012 ~ TASK-015）。

重点：所有统计必须来自真实数据 —— 健康度四维、提醒项、分类数量都要能算得出来，
不能是写死的字符串（改造前 knowledge.py 里全是硬编码的"238 条""82 分"）。

运行：backend/venv/Scripts/python.exe tests/test_knowledge.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.bootstrap import init_all
from app.db import SessionLocal
from app.main import app
from app.models_ai import KnowledgeBase, KnowledgeDocument

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  → {detail}" if detail else ""))


client_ctx = None


def _run() -> int:
    db = SessionLocal()
    try:
        init_all()

        print("\n=== 登录 ===")
        r = client_ctx.post("/api/auth/login", json={"username": "sales", "password": "123456"})
        check("登录成功", r.status_code == 200, str(r.status_code))
        token = r.json()["data"]["token"]
        H = {"Authorization": f"Bearer {token}"}

        print("\n=== 未登录访问被拒 ===")
        check("无 token 访问知识中心被拒(401)",
              client_ctx.get("/api/knowledge").status_code == 401)

        print("\n=== 总览：真实统计 ===")
        r = client_ctx.get("/api/knowledge", headers=H)
        check("总览返回 200", r.status_code == 200, str(r.status_code))
        d = r.json()["data"]

        bases = db.query(KnowledgeBase).all()
        docs = db.query(KnowledgeDocument).all()
        kpi = {k["label"]: k["value"] for k in d["kpis"]}
        print(f"  KPI: {kpi}")
        check("知识库数量与数据库一致",
              kpi.get("知识库") == str(len(bases)), f"{kpi.get('知识库')} vs {len(bases)}")
        check("知识文档数量与数据库一致",
              kpi.get("知识文档") == str(len(docs)), f"{kpi.get('知识文档')} vs {len(docs)}")
        check("存在知识分片", int(kpi.get("知识分片", "0")) > 0, kpi.get("知识分片", "0"))
        check("累计字数 > 0", kpi.get("累计字数", "0") != "0", kpi.get("累计字数"))

        print("\n=== 健康度：由真实数据算出 ===")
        h = d["health"]
        basis = h.get("basis", {})
        print(f"  评分 {h['score']} ({h['level']})  维度: "
              f"{[(x['label'], x['value']) for x in h['dimensions']]}")
        print(f"  计算依据: {basis}")
        check("健康度有计算依据（非硬编码）", bool(basis))
        check("完整性维度有值", h["dimensions"][0]["value"] >= 0)
        check("评分在 0~100 之间", 0 <= h["score"] <= 100, str(h["score"]))
        # 反向验算：完整性应等于 有正文且分片数>0 的文档占比
        total = basis.get("docs", 0)
        if total:
            expect = int(round(basis["complete"] / total * 100))
            check("完整性可由依据反向验算",
                  h["dimensions"][0]["value"] == expect,
                  f"{h['dimensions'][0]['value']} vs {expect}")

        print("\n=== 提醒项：由数据扫描生成 ===")
        print(f"  {[x['text'] for x in d['reminders']]}")
        check("提醒项带分类标签",
              all(x.get("tag") for x in d["reminders"]))

        print("\n=== 分类：按知识库 category 聚合 ===")
        cats = {c["name"]: c["value"] for c in d["categories"]}
        print(f"  {cats}")
        expect_cats: dict[str, int] = {}
        for kb in bases:
            n = sum(1 for x in docs if x.kb_id == kb.id)
            expect_cats[kb.category] = expect_cats.get(kb.category, 0) + n
        check("分类聚合与数据库一致", cats == expect_cats, f"{cats} vs {expect_cats}")

        print("\n=== 知识库列表 ===")
        r = client_ctx.get("/api/knowledge/bases", headers=H)
        check("知识库列表返回 200", r.status_code == 200)
        items = r.json()["data"]["items"]
        check("返回了知识库", len(items) > 0, f"{len(items)} 个")
        kb_id = items[0]["id"]

        print("\n=== 权限边界：无 knowledge:manage 者不得上传 ===")
        long_text = "。".join(
            [f"第{i}条：核安全巡检需在辐射监测点位完成双人复核并留存影像记录" for i in range(1, 40)]
        )
        r = client_ctx.post("/api/knowledge/documents", headers=H, json={
            "kb_id": kb_id, "title": "越权上传测试", "content": long_text,
        })
        check("sales 无 manage 权限被拒(403)", r.status_code == 403,
              f"{r.status_code} {r.json().get('message', '')}")

        print("\n=== 上传文档：解析 → 分块 → 入库（admin）===")
        r = client_ctx.post("/api/auth/login",
                            json={"username": "admin", "password": "123456"})
        check("admin 登录成功", r.status_code == 200, str(r.status_code))
        HA = {"Authorization": f"Bearer {r.json()['data']['token']}"}

        r = client_ctx.post("/api/knowledge/documents", headers=HA, json={
            "kb_id": kb_id,
            "title": "核安全巡检补充规范（测试）",
            "content": long_text,
            "source": "质量管理部 · 2026 修订版",
            "file_type": "txt",
            "valid_days": 365,
        })
        check("上传返回 200", r.status_code == 200, str(r.status_code) + " " + r.text[:120])
        up = r.json()["data"]
        print(f"  分片数 {up['chunk_count']}，字数 {up['char_count']}")
        check("生成了多个分片（分块生效）", up["chunk_count"] > 1, str(up["chunk_count"]))
        new_doc_id = up["id"]

        print("\n=== 门禁：上传强制草稿，发布走 submit → publish ===")
        r = client_ctx.get("/api/knowledge/documents", headers=HA)
        st = [d for d in r.json()["data"]["items"] if d["id"] == new_doc_id]
        check("上传后状态为草稿",
              bool(st) and st[0]["status"] == "草稿",
              str(st[0]["status"] if st else None))

        print("\n=== 草稿不可被检索 ===")
        r = client_ctx.post("/api/knowledge/search", headers=H,
                            json={"query": "核安全巡检双人复核", "top_k": 3})
        hits = r.json()["data"]["hits"]
        check("草稿未被检索到",
              not any(h["doc_id"] == new_doc_id for h in hits),
              str([h["doc_title"] for h in hits][:3]))

        print("\n=== 提交审核 → 发布 → 可检索 ===")
        r = client_ctx.post(f"/api/knowledge/documents/{new_doc_id}/submit", headers=HA)
        check("submit 返回 200", r.status_code == 200, str(r.status_code))
        check("submit 后为审核中", r.json()["data"]["status"] == "审核中",
              str(r.json().get("data", {}).get("status")))
        r = client_ctx.post(f"/api/knowledge/documents/{new_doc_id}/publish", headers=HA)
        check("publish 返回 200", r.status_code == 200, str(r.status_code))
        check("publish 后为已发布", r.json()["data"]["status"] == "已发布",
              str(r.json().get("data", {}).get("status")))
        r = client_ctx.post("/api/knowledge/search", headers=H,
                            json={"query": "核安全巡检双人复核", "top_k": 3})
        hits = r.json()["data"]["hits"]
        print(f"  命中: {[h['doc_title'] for h in hits]}")
        check("发布后可检索到",
              any(h["doc_id"] == new_doc_id for h in hits),
              str([h["doc_title"] for h in hits][:3]))
        check("检索结果带来源文档", bool(hits) and bool(hits[0].get("doc_title")))

        print("\n=== 分片内容可查 ===")
        r = client_ctx.get(f"/api/knowledge/chunks?doc_id={new_doc_id}", headers=H)
        check("分片接口返回 200", r.status_code == 200)
        chunks = r.json()["data"]["items"]
        check("分片数一致", len(chunks) == up["chunk_count"],
              f"{len(chunks)} vs {up['chunk_count']}")

        print("\n=== 健康度随新文档变化（证明非写死）===")
        r2 = client_ctx.get("/api/knowledge", headers=H)
        h2 = r2.json()["data"]["health"]
        print(f"  上传前 {h['score']} 分 / 依据 {basis}")
        print(f"  上传后 {h2['score']} 分 / 依据 {h2.get('basis')}")
        check("文档总数已增加",
              h2["basis"]["docs"] == basis["docs"] + 1,
              f"{h2['basis']['docs']} vs {basis['docs'] + 1}")

        print("\n=== 清理：删除测试文档 ===")
        d_obj = db.get(KnowledgeDocument, new_doc_id)
        if d_obj:
            db.delete(d_obj)
            db.commit()
        check("测试文档已清理", db.get(KnowledgeDocument, new_doc_id) is None)

    finally:
        db.close()

    print("\n" + "=" * 56)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    for f in FAIL:
        print(f"  ✗ {f}")
    print("=" * 56)
    return 1 if FAIL else 0


def main() -> int:
    global client_ctx
    with TestClient(app) as c:
        client_ctx = c
        return _run()


if __name__ == "__main__":
    sys.exit(main())
