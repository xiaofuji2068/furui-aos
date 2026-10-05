# -*- coding: utf-8 -*-
"""全量回归 runner（隔离库版）。

## 为什么要存在这个脚本
此前直接串行跑 `tests/test_*.py`，它们从 `app.db` 读 DATABASE_URL：
- 不设环境变量 → 落回 SQLite `app.db`（与 PG 生产库不是一套数据）
- 若设成生产库 `furui_aios` → TASK-016 已 seed 过 2 个 Bundle 并装了 2 个安装，
  导致 `test_asset_bundle` 的「seed 首次创建 2 Bundle / seed 幂等 / catalog 未安装标记」
  等断言前提不成立，出现 PASS 34 / FAIL 1 的**假回归**。

本 runner 强制把 DATABASE_URL 指向隔离测试库 **furui_aios_test**
（与生产库同结构，各 46 张表），使断言前提复位，同时绝不污染生产数据。

## 用法
    cd backend
    venv/Scripts/python.exe run_tests.py                  # 全量 24 个脚本
    venv/Scripts/python.exe run_tests.py tests/test_asset_bundle.py   # 单个
"""
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TEST_URL = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test"

# 必须在 import app.db 之前设置：app/db.py 第 21 行 os.getenv("DATABASE_URL", sqlite 兜底)
os.environ["DATABASE_URL"] = TEST_URL

# 各测试脚本输出格式不一致（中文「通过 N 项，失败 M 项」/ 英文「PASS N / FAIL M」），统一抽断言数。
# 必须行级匹配：脚本间输出格式不统一，跨行截断会把别的行内容算进来。
# 典型坑：test_admin_keys 只打印 "PASS 9/9 admin_keys 断言"（没有 FAIL 字样，
# 表示 9 个全过）。用 `PASS\s*(\d+)\s*/\s*(\d+)` 去抓会把两个 9 分别当成 pass=9 /
# fail=9，批量回归里凭空多出 9 条 FAIL，而单跑该脚本是绿的 —— 典型的假失败。
_PASS_LINE = [
    re.compile(r"PASS\s*(\d+)\s*/\s*FAIL\s*(\d+)"),     # "PASS 34 / FAIL 1"
    re.compile(r"(\d+)\s*PASS\s*/\s*(\d+)\s*FAIL"),     # "34 PASS / 1 FAIL"
    re.compile(r"通过\s*(\d+)\s*项，失败\s*(\d+)\s*项"),  # 「通过 34 项，失败 1 项」
]
# "PASS 9/9 xxx" —— 只有 PASS 一段，行内不含 FAIL → 记成 (9, 0)
_NM_LINE = re.compile(r"PASS\s*(\d+)\s*/\s*(\d+)")
_SKIP_PAT = re.compile(r"SKIP\s*(\d+)")


def _scan(out: str):
    """从一段测试输出里抽出 (pass_n, fail_n, skip_n)。"""
    best = (0, 0)
    counts = []
    for line in out.splitlines():
        hit = None
        for p in _PASS_LINE:
            m = p.search(line)
            if m:
                hit = (int(m.group(1)), int(m.group(2)))
                break
        if hit is None:
            m = _NM_LINE.search(line)
            if m:
                # 行里有 FAIL 才当「N/M 里过了 N 剩下的失败」；否则是 N/N 全过
                hit = (int(m.group(1)), int(m.group(2))) if "FAIL" in line else (int(m.group(1)), 0)
        if hit:
            counts.append(hit)
    if counts:
        # 取出现次数最多的那组，避免误匹配到汇总行以外的地方
        from collections import Counter

        best = Counter(counts).most_common(1)[0][0]
    skip_m = _SKIP_PAT.search(out)
    # findall 的分组是 str，必须转 int，否则汇总处 `total_pass += n_pass` 会 TypeError
    return int(best[0]), int(best[1]), (int(skip_m.group(1)) if skip_m else 0)


def main():
    targets = sys.argv[1:] or sorted(str(p) for p in (ROOT / "tests").glob("test_*.py"))
    print(f"数据库: {TEST_URL}\n目标: {len(targets)} 个脚本\n" + "=" * 62)

    total_pass = total_fail = total_skip = 0
    broken = []

    for i, f in enumerate(targets, 1):
        p = pathlib.Path(f)
        if not p.is_absolute():
            p = ROOT / f
        r = subprocess.run([sys.executable, str(p)], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="ignore")
        out = (r.stdout or "") + (r.stderr or "")
        n_pass, n_fail, n_skip = _scan(out)
        total_pass += n_pass
        total_fail += n_fail
        total_skip += n_skip

        # 关键：断言数为 0（脚本中途崩溃 / 没有输出汇总行）绝不能算「通过」，
        # 否则测试库残留数据导致崩溃时会被误报成全绿。
        if n_fail:
            status = "FAIL"
        elif n_pass + n_fail == 0:
            status = "ERR " if r.returncode != 0 else "????"
        else:
            status = "OK  "

        print(f"[{i:>2}/{len(targets)}] {status} {p.name:<36} "
              f"PASS {n_pass:>3} / FAIL {n_fail} / SKIP {n_skip}")
        if n_fail or n_pass + n_fail == 0:
            broken.append(p.name)
            tail = (out.strip().splitlines() or ["<无输出>"])[-1]
            for line in out.splitlines():
                if re.search(r"FAIL|失败|Error|error", line):
                    print(f"       └ {line.strip()[:78]}")
                    break
            else:
                print(f"       └ 崩溃/无断言输出: {tail[:78]}")

    print("=" * 62)
    print(f"汇总  PASS {total_pass} / FAIL {total_fail} / SKIP {total_skip}")
    print(f"文件  {'全部通过' if not broken else '未通过: ' + ', '.join(broken)}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
