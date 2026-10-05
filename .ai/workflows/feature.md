# FEATURE DEVELOPMENT WORKFLOW
# STEP 1 — Understand
明确：
目标用户
业务问题
使用场景
成功标准。
---
# STEP 2 — Locate
搜索现有：
Entity
API
Service
Repository
Component
Hook
Tool
Agent
Workflow
Test
---
# STEP 3 — Domain
确定：
属于哪个 Domain。
是否需要新增 Entity。
---
# STEP 4 — Architecture
明确：
Frontend
↓
API
↓
Application
↓
Domain
↓
Data
以及：
Agent
↓
Tool
↓
Service
---
# STEP 5 — Design
设计：
Business
Domain
Data
API
UI
AI
Permission
Test
---
# STEP 6 — Plan
把工作拆成小 Task。
例如：
TASK-001
Domain
TASK-002
Database
TASK-003
API
TASK-004
UI
TASK-005
Agent
TASK-006
Test
---
# STEP 7 — Implement
一次只处理当前 Task。
---
# STEP 8 — Test
至少考虑：
Happy Path
Error Path
Permission
Boundary
---
# STEP 9 — Review
检查：
Architecture
Domain
Security
Reuse
Performance
Code Quality
---
# STEP 10 — Documentation
同步更新：
API
Domain
Architecture
Module
---
# STEP 11 — Task Complete
更新：
CURRENT.md
---
# STEP 12 — Final Report
输出：
Completed
Files
Design
Reuse
Tests
Risks
Documentation
Next
---
# IMPORTANT
不要因为任务比较大：
一次生成大量代码。
优先：
小步开发
小步测试
小步提交
