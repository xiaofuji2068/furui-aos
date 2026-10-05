# -*- coding: utf-8 -*-
"""全量回归 v2：完整保留失败测试的 stderr 尾部（异常类型行）。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "venv" / "Scripts" / "python.exe"
TESTS = sorted((ROOT / "tests").glob("test_*.py"))

def _reset_agents() -> None:
    """测试隔离：每个测试前把 Agent 状态恢复种子值（mainline 失败会置 Error 污染后续测试）。"""
    import sys
    sys.path.insert(0, str(ROOT))
    try:
        from app.db import SessionLocal
        from app.models_ai import Agent
        db = SessionLocal()
        try:
            for code, st in (("sales-analyst", "Published"),
                             ("knowledge-assistant", "Published"),
                             ("inspection-analyst", "Published"),
                             ("ops-engineer", "Testing")):
                db.query(Agent).filter(Agent.code == code).update({Agent.status: st})
            db.commit()
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        print(f"[reset_agents] skip: {e}")

results = []
for t in TESTS:
    print(f"\n===== {t.name} =====", flush=True)
    _reset_agents()
    p = subprocess.run([str(PY), str(t)], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    ok = p.returncode == 0
    if ok:
        tail = (p.stdout or "").strip().splitlines()[-2:]
        print("\n".join(tail))
    else:
        # 失败：输出 stderr 尾部 25 行 + stdout 尾部 8 行
        print("--- STDERR (tail 25):")
        err = (p.stderr or "").strip().splitlines()
        print("\n".join(err[-25:]))
        print("--- STDOUT (tail 8):")
        out = (p.stdout or "").strip().splitlines()
        print("\n".join(out[-8:]))
    print(f"--- {t.name}: {'PASS' if ok else 'FAIL'} (exit={p.returncode})", flush=True)
    results.append((t.name, ok))

print("\n\n========== 汇总 ==========")
for name, ok in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
print(f"\nTOTAL: PASS {sum(1 for _, ok in results if ok)} / FAIL {sum(1 for _, ok in results if not ok)} / {len(results)} files")
