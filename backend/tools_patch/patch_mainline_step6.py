# -*- coding: utf-8 -*-
"""巡检场景 step6 提前收尾：销售分支前插入 done+return。"""
P = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend\app\mainline.py"
with open(P, "r", encoding="utf-8") as f:
    src = f.read()

old = """        else:
            top = analysis.get("top_drop_customer")
            payload: Dict[str, Any] = {}
        if top:"""
new = """        else:
            top = analysis.get("top_drop_customer")
            payload: Dict[str, Any] = {}
        if top:
            if getattr(self.agent, "code", "") == "inspection-analyst":
                self._advance_stage(step6)
                self._progress()
                db.commit()
                if self.task.status != "WaitingApproval":
                    self.task.transition("Completed")
                    self.task.finished_at = datetime.utcnow()
                    for st in self.task.stages:
                        if st.status != "Completed":
                            st.status = "Completed"
                            st.finished_at = datetime.utcnow()
                self.task.result = collected.get("report", "")
                if self.agent:
                    self.agent.total_tasks += 1
                    self.agent.today_tasks += 1
                    if self.task.status == "Completed":
                        self.agent.success_tasks += 1
                db.commit()
                yield {"event": "done", "data": {
                    "task_id": self.task.id,
                    "agent": self.agent.name if self.agent else "",
                    "status": self.task.status,
                    "progress": self.task.progress,
                }}
                return"""
assert old in src, "anchor missing"
src = src.replace(old, new, 1)
with open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("STEP6 RETURN OK")
