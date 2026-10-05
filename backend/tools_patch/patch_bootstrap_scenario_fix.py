# -*- coding: utf-8 -*-
"""修复 _seed_scenarios：销售场景也按 name 幂等，避免重复创建。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\bootstrap.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

old = '''    db.add(BusinessScenario(
        company_id=company_id, application_id=app.id,
        name="销售下降自动归因", category="销售", owner="李明", department="销售部",
        problem="月度销售下滑时，人工归因耗时长且口径不统一",
        acceptance="输入问题后 60 秒内输出归因报告，主因定位准确率可复核",
        stage="运行中", progress=80, status="运行中",
    ))
    db.add(BusinessScenario(
        company_id=company_id, application_id=app.id,
        name="大客户流失预警", category="销售", owner="王欢", department="销售部",
        problem="大客户订单下滑发现滞后，错过挽回窗口",
        acceptance="大客户环比下滑超 30% 时自动预警并生成挽回任务",
        stage="测试中", progress=45, status="测试中",
    ))
'''
new = '''    if "销售下降自动归因" not in existing_names:
        db.add(BusinessScenario(
            company_id=company_id, application_id=app.id,
            name="销售下降自动归因", category="销售", owner="李明", department="销售部",
            problem="月度销售下滑时，人工归因耗时长且口径不统一",
            acceptance="输入问题后 60 秒内输出归因报告，主因定位准确率可复核",
            stage="运行中", progress=80, status="运行中",
        ))
    if "大客户流失预警" not in existing_names:
        db.add(BusinessScenario(
            company_id=company_id, application_id=app.id,
            name="大客户流失预警", category="销售", owner="王欢", department="销售部",
            problem="大客户订单下滑发现滞后，错过挽回窗口",
            acceptance="大客户环比下滑超 30% 时自动预警并生成挽回任务",
            stage="测试中", progress=45, status="测试中",
        ))
'''
assert old in src, "scenario block missing"
src = src.replace(old, new, 1)
with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("SCENARIO IDEMPOTENT OK")
