# AGENT RULES
# 1. Agent
Agent：
理解任务
规划
选择工具
执行
判断结果
---
# 2. Agent ≠ Business Logic
不要把业务规则全部写进 Prompt。
---
# 3. Tool
Tool：
小
明确
可测试
可复用
---
# 4. Naming
domain.action
例如：
customer.search
customer.get
project.search
task.create
---
# 5. Permission
Tool 执行：
必须检查权限。
---
# 6. Database
禁止：
Agent → Database
必须：
Agent
↓
Tool
↓
Service
↓
Repository
↓
Database
---
# 7. Context
只提供：
完成任务需要的数据。
---
# 8. Memory
明确区分：
Conversation
Preference
Knowledge
Business Data
---
# 9. Tool Call
每次 Tool Call：
应该有明确原因。
---
# 10. Loop
限制：
最大循环次数
最大 Tool Call
最大 Token
---
# 11. Failure
Tool 失败：
Agent 应该：
识别失败
尝试合理恢复
无法恢复时：
明确告诉用户。
---
# 12. Confirmation
高风险操作：
必须确认。
---
# 13. Observability
记录：
Task
Agent
Tool
Input
Output
Duration
Error
---
# 14. Hallucination
不知道：
说不知道。
禁止：
编造业务数据。
---
# 15. Agent Output
区分：
事实
推断
建议
行动
---
# 16. Agent Design
不要建立：
一个超级 Agent。
优先：
多个明确能力。
