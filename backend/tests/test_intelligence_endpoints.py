"""P1 智能化中心端点回归（Task #25/#27）。

锁定：
- GET /api/meta       运行态（产品态/演示态、本体持久化、agent/skill 计数）
- GET /api/skills     Skills 注册表清单（含写入型标记 write）

运行：
    backend/venv/Scripts/python.exe tests/test_intelligence_endpoints.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client: TestClient | None = None
PASS, FAIL = [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def main():
    global client
    with TestClient(app) as c:
        client = c

        print("\n=== /api/meta 运行态 ===")
        r = client.get("/api/meta")
        check("meta 200", r.status_code == 200, r.text[:120])
        m = r.json()["data"]
        check("meta.llm_mode 存在", bool(m.get("llm_mode")))
        check("meta.version 存在", bool(m.get("version")))
        check("meta.ontology_mode 存在", bool(m.get("ontology_mode")))
        check("meta.multi_agent 是布尔", isinstance(m.get("multi_agent"), bool))
        check("meta.agent_count 是整数", isinstance(m.get("agent_count"), int))
        check("meta.skill_count 是整数", isinstance(m.get("skill_count"), int))
        check("meta.llm_enabled 是布尔", isinstance(m.get("llm_enabled"), bool))

        print("\n=== /api/skills 注册表 ===")
        r = client.get("/api/skills")
        check("skills 200", r.status_code == 200, r.text[:120])
        sk = r.json()["data"]["items"]
        check("skills 是列表且非空", isinstance(sk, list) and len(sk) > 0, f"len={len(sk) if isinstance(sk, list) else 'NA'}")
        if sk:
            s0 = sk[0]
            check("skill 含 name", bool(s0.get("name")))
            check("skill 含 description", bool(s0.get("description")))
            check("skill 含 write(布尔)", isinstance(s0.get("write"), bool))
            check("skill 含 param_count(整数)", isinstance(s0.get("param_count"), int))
            # 写入型 Skills 必须被标记
            write_names = {s["name"] for s in sk if s["write"]}
            check("存在写入型 Skill(create_workorder)",
                  "create_workorder" in write_names, str(write_names))

        print("\n=== meta.skill_count 与 skills 清单交叉校验 ===")
        if sk:
            check("meta.skill_count == len(skills)",
                  m.get("skill_count") == len(sk),
                  f"{m.get('skill_count')} vs {len(sk)}")

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
