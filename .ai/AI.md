# AI SYSTEM RULES
# 1. AI Architecture
AI 系统包括：
LLM
↓
Context
↓
Agent
↓
Tool
↓
Service
↓
Domain
↓
Data
---
# 2. LLM
LLM 负责：
理解
推理
生成
规划
---
LLM 不应该直接拥有：
数据库权限
系统管理员权限
---
# 3. Agent
Agent 负责：
Intent
Planning
Tool Selection
Execution
Evaluation
---
# 4. Tool
Tool 是：
Agent 与系统能力之间的标准接口。
Tool 必须：
输入明确
输出明确
权限明确
可测试
可记录。
---
# 5. Tool Naming
统一：
domain.action
例如：
customer.search
customer.get
customer.summary
project.search
project.analyze
task.create
task.update
---
# 6. Agent Permission
Agent 的权限：
不能超过当前用户权限。
---
# 7. Human Confirmation
默认需要确认：
删除
修改关键业务数据
发送外部消息
资金操作
修改权限
高风险操作。
---
# 8. Context
Context 应该：
相关
最小
准确
可追溯。
禁止：
把整个数据库塞入 Prompt。
---
# 9. Memory
区分：
Conversation Memory
User Preference
Enterprise Knowledge
Business Data
不能混为一谈。
---
# 10. RAG
RAG：
Search
↓
Retrieve
↓
Rerank
↓
Context
↓
Generate
---
# 11. Hallucination
不确定：
明确说不知道。
禁止：
编造企业数据。
---
# 12. Agent Loop
必须防止：
无限循环
重复 Tool Call
Token 爆炸
---
# 13. Timeout
AI 调用需要考虑：
Timeout
Retry
Fallback
---
# 14. Observability
记录：
Agent
Task
Tool
Input
Output
Duration
Error
---
# 15. AI Output
AI 输出应该区分：
Fact
Inference
Recommendation
Action
---
# 16. AI 不应该假装知道
如果数据不存在：
不要创造。
---
# 17. AI + Workflow
确定性：
Workflow。
复杂推理：
Agent。
复杂业务：
Agent
+
Workflow。
