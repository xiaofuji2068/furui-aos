# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_ontology_persistence.py")
t = p.read_text(encoding="utf-8")
reps = [
    # 剩余所有未加 cid 的 filter_by(type= → 全部加（已加的不匹配）
    ("filter_by(type=", "filter_by(company_id=cid, type="),
    # 第二处 seed（Link 幂等段）
    ("            seed_ontology(db)", "            seed_ontology(db, company_id=cid)"),
]
n = 0
for o, nw in reps:
    c = t.count(o)
    if c:
        t = t.replace(o, nw)
        n += c
    else:
        print("MISS:", o[:50])
# 孤儿 link 清理：测试工单的 WO→Device link 一并删除
old_clean = ("            # 清理测试工单，避免残留导致下次运行失败\n"
             "            row = db2.query(OntologyObjectRow).filter_by(company_id=cid, type=\"WorkOrder\", object_id=wid).first()\n"
             "            if row:\n"
             "                db2.delete(row)\n"
             "                db2.commit()\n")
new_clean = ("            # 清理测试工单及其关系，避免残留导致下次运行失败\n"
             "            row = db2.query(OntologyObjectRow).filter_by(company_id=cid, type=\"WorkOrder\", object_id=wid).first()\n"
             "            if row:\n"
             "                db2.delete(row)\n"
             "            db2.query(OntologyLinkRow).filter(OntologyLinkRow.source_id == wid).delete()\n"
             "            if row or True:\n"
             "                db2.commit()\n")
if old_clean in t:
    t = t.replace(old_clean, new_clean)
    n += 1
else:
    print("MISS: clean block")
p.write_text(t, encoding="utf-8")
ast.parse(p.read_text(encoding="utf-8"))
print("PATCHED", n, "SYNTAX OK")