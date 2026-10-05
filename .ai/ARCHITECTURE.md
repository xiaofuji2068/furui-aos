# ARCHITECTURE
# 1. Overall Architecture
系统采用：
Layered Architecture
+
Domain Driven Design
+
Modular Architecture
+
AI Agent Architecture
---
# 2. System
User
↓
Interaction Layer
↓
Application Layer
↓
Capability Layer
↓
Domain Layer
↓
Infrastructure Layer
↓
Data
---
# 3. Interaction Layer
负责：
Web UI
Chat
Dashboard
Notification
User Interaction
---
禁止：
直接访问数据库
实现核心业务逻辑
---
# 4. Application Layer
负责：
Use Case
Command
Query
Agent
Workflow
业务流程编排。
---
# 5. Capability Layer
包括：
Service
Tool
Integration
Workflow Action
---
# 6. Domain Layer
包括：
Entity
Value Object
Domain Service
Domain Event
---
# 7. Infrastructure
包括：
Repository
Database
File Storage
Vector Database
External API
LLM Provider
---
# 8. Dependency
允许：
UI
↓
API
↓
Application
↓
Domain
↓
Repository
↓
Infrastructure
---
禁止：
UI → Database
UI → Repository
Agent → Database
Agent → Repository
Controller → Database
Domain → FastAPI
Domain → React
---
# 9. Frontend
推荐：
pages
features
components
hooks
services
api
types
utils
---
# 10. Backend
推荐：
modules/
    customer/
        domain/
        application/
        infrastructure/
        api/
        tests/
---
# 11. Agent
Agent：
理解任务
↓
规划
↓
选择 Tool
↓
调用 Tool
↓
分析结果
↓
决定下一步
↓
完成任务
---
# 12. Agent Dependency
Agent
↓
Tool
↓
Application Service
↓
Domain
↓
Repository
↓
Database
---
# 13. Agent 禁止
Agent 不允许：
直接 SQL
直接 ORM
直接 Database
绕过权限
绕过 Service
---
# 14. Workflow
确定性业务流程：
Workflow。
---
非确定性问题：
Agent。
---
复杂场景：
Agent
+
Tool
+
Workflow。
---
# 15. Data
系统数据分为：
Transactional Data
Knowledge Data
Vector Data
Event Data
File Data
---
# 16. Knowledge
Document
↓
Parser
↓
Chunk
↓
Metadata
↓
Embedding
↓
Vector Store
↓
Retrieval
↓
Reranking
↓
Context
↓
LLM
---
# 17. Event
重要业务行为：
可以产生 Event。
例如：
CustomerCreated
ProjectCreated
TaskCreated
TaskCompleted
AgentExecuted
---
# 18. Security
Authentication
↓
Authorization
↓
Application
↓
Audit
---
# 19. Architecture Change
重大变化：
必须创建：
docs/decisions/ADR-XXX.md
---
# 20. Priority
优先级：
Security
>
Data Integrity
>
Domain Integrity
>
Architecture
>
Maintainability
>
Performance
>
Convenience
