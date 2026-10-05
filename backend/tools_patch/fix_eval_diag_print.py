# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\tests\test_eval_contract.py")
t = p.read_text(encoding="utf-8")
# 在 execute 后打印结果（临时诊断，定位后移除）
old = '        r3 = execute(ctx, "create_sales_task", {\n            "customer_id": 1, "customer_name": "Lineage 测试客户", "title": "Lineage 拒绝测试",'
new = '        r3 = execute(ctx, "create_sales_task", {\n            "customer_id": 1, "customer_name": "Lineage 测试客户", "title": "Lineage 拒绝测试",'
if old not in t:
    print("MISS marker")
else:
    # 在 r3 赋值后加打印：找到下一行内容
    print("FOUND r3 block")
p.write_text(t, encoding="utf-8")