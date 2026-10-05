# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tools_patch\run_all_tests.py")
t = p.read_text(encoding="utf-8")
old = '''ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "venv" / "Scripts" / "python.exe"
TESTS = sorted((ROOT / "tests").glob("test_*.py"))

results = []
for t in TESTS:
    print(f"\\n===== {t.name} =====", flush=True)'''
new = '''ROOT = Path(__file__).resolve().parent.parent
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
    print(f"\\n===== {t.name} =====", flush=True)
    _reset_agents()'''
if old in t:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8")
    print("run_all_tests.py: PATCHED")
else:
    print("run_all_tests.py: MISS")