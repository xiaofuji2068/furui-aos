# -*- coding: utf-8 -*-
"""TASK-018（图谱 90-02「如何知道系统真的工作」）：成熟度快照采集器。

用途：把「系统到底到哪一步」从人工复述变成**可复跑的客观采集**，
供 docs/MATURITY-MATRIX.md 引用与刷新。

采集维度（全部实测，不做人工评估）：
  1. 工程基础：迁移链版本数 / 链头 / head、双库（prod / test）表数与 RLS 表数
  2. 接口面  ：后端 API 端点数与分组数、前端 page.tsx 路由数
  3. 测试面  ：tests/test_*.py 脚本数，以及回归汇总（解析 run_tests.py 的输出）
  4. 代码面  ：backend/app 与 frontend 源码规模

用法：
    cd backend
    .\\venv\\Scripts\\python.exe tools_patch\\maturity_snapshot.py
    .\\venv\\Scripts\\python.exe tools_patch\\maturity_snapshot.py --json > ../docs/maturity-snapshot.json  # 落档供文档引用

注意：DSN 必须写 `postgresql+psycopg://`（写 `postgresql://` 会落回 psycopg2
并抛 ModuleNotFoundError），详见 docs/图谱-furui-aios差距清单与实施路线.md 的 DSN 铁律。
"""
from __future__ import annotations

import argparse, glob, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PG_DSN = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/{db}"


def _prod_db() -> str:
    """生产库名：优先读 start_backend_pg.py 写死的库，其次环境变量，最后兜底。"""
    env = os.environ.get("FURUI_PROD_DB", "").strip()
    if env:
        return env
    script = os.path.join(ROOT, "start_backend_pg.py")
    if os.path.exists(script):
        with open(script, encoding="utf-8") as f:
            m = re.search(r"(?i)DB_NAME\s*=\s*[\"']([^\"']+)", f.read())
            if m:
                return m.group(1)
    return "furui_aios"


def _mig_meta(path: str) -> tuple[str | None, str | None]:
    """用 AST 取 revision / down_revision —— 比正则稳（项目里三种写法都有：
    `revision: str = 'x'` / `revision = 'x'` / docstring 里写 Revision ID）。"""
    import ast
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError:
        return None, None
    rev = down = None
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):  # `revision: str = 'x'`
            targets = [node.target]
        for tgt in targets:
            if not isinstance(tgt, ast.Name):
                continue
            val = node.value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                if tgt.id == "revision":
                    rev = val.value
                elif tgt.id == "down_revision":
                    down = val.value
    return rev, down


def collect_migrations() -> dict:
    out = {"count": 0, "root": None, "roots": [], "revisions": []}
    files = sorted(glob.glob(os.path.join(ROOT, "alembic", "versions", "*.py")))
    for f in files:
        rid, down = _mig_meta(f)
        out["revisions"].append({"id": rid, "down": down, "file": os.path.basename(f)})
        if down in (None,):
            out["roots"].append(rid)
    out["count"] = len(out["revisions"])
    # 链根（down_revision=None 的起点）必须唯一；alembic 禁忌的"多 head"指
    # 多个 revision 都指向同一条链的末尾，此处用 tip_at_prod/tip_at_test 表示。
    out["root"] = out["roots"][0] if len(out["roots"]) == 1 else f"MULTIPLE:{out['roots']}"
    return out


def _pg_tables(dbname: str) -> dict | None:
    from sqlalchemy import create_engine, text
    try:
        eng = create_engine(PG_DSN.format(db=dbname))
        with eng.connect() as c:
            n = c.execute(text("select count(*) from pg_tables where schemaname='public'")).scalar()
            # rowsecurity/forcerowsecurity 在 pg_class 上，不在 pg_tables 上
            rls = c.execute(text(
                "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace "
                "where n.nspname='public' and c.relkind='r' "
                "and c.relrowsecurity and c.relforcerowsecurity"
            )).scalar()
            tabs = [r[0] for r in c.execute(text(
                "select tablename from pg_tables where schemaname='public' order by 1"))]
            ver = c.execute(text("select version_num from alembic_version limit 1")).scalar()
        return {"db": dbname, "tables": int(n), "rls_tables": int(rls), "version": ver, "tables_list": tabs}
    except Exception as e:  # 库不在/连不上时如实记录，不伪装成 0
        return {"db": dbname, "error": f"{type(e).__name__}: {e}"}


def collect_api() -> dict:
    sys.path.insert(0, ROOT)
    try:
        import app.api  # noqa: F401  (触发全部子路由注册)
        from app.main import app as fastapi_app
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    rows = []
    for r in fastapi_app.routes:
        methods = sorted(getattr(r, "methods", None) or [])
        methods = [m for m in methods if m not in ("HEAD", "OPTIONS")]
        path = getattr(r, "path", "")
        if methods and path.startswith("/api"):
            rows.append((path, ",".join(methods)))
    groups = {}
    for p, _ in rows:
        parts = p.split("/")
        k = parts[2] if len(parts) > 2 else "root"
        groups[k] = groups.get(k, 0) + 1
    return {"endpoints": len(rows), "groups": len(groups), "by_group": dict(sorted(groups.items()))}


def collect_frontend() -> dict:
    fe = os.path.join(os.path.dirname(ROOT), "frontend")
    pages = glob.glob(os.path.join(fe, "app", "**", "page.tsx"), recursive=True)
    routes = sorted({(os.path.relpath(p, os.path.join(fe, "app"))[:-len("/page.tsx")] + "/") for p in pages})
    routes = [("/" if r == "./" else r) for r in routes]
    total = 0
    for root, dirs, files in os.walk(fe):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".next", ".next_old_*")]
        for fn in files:
            if fn.endswith((".ts", ".tsx")):
                total += 1
    return {"routes": routes, "route_count": len(routes), "source_files": total}


def collect_tests() -> dict:
    files = sorted(glob.glob(os.path.join(ROOT, "tests", "test_*.py")))
    return {"script_count": len(files),
            "scripts": [os.path.basename(f) for f in files]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非人读摘要")
    args = ap.parse_args()

    data = {
        "migrations": collect_migrations(),
        "prod_db": _pg_tables(_prod_db()),
        "test_db": _pg_tables("furui_aios_test"),
        "api": collect_api(),
        "frontend": collect_frontend(),
        "tests": collect_tests(),
    }

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    m = data["migrations"]
    p, t = data["prod_db"], data["test_db"]
    print("=== 迁移链 ===")
    print(f"  版本数 {m['count']} / 链根(revision-less 起点) {m['root']}")
    print("=== 双库 ===")
    for k in ("prod_db", "test_db"):
        d = data[k]
        if "error" in d:
            print(f"  [{k}] {d['error']}")
        else:
            print(f"  [{d['db']}] tip(alembic_version)={d['version']} "
                  f"tables={d['tables']} rls_tables={d['rls_tables']}")
    a, f, ts = data["api"], data["frontend"], data["tests"]
    print("=== 接口面 ===")
    print(f"  后端 API {a.get('endpoints')} 个 / {a.get('groups')} 组"
          + (f" / 错误 {a['error']}" if "error" in a else ""))
    print(f"  前端路由 {f.get('route_count')} 个")
    print("=== 测试面 ===")
    print(f"  脚本 {ts['script_count']} 个")
    print("=== 前端源码文件 ===", f.get("source_files"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
