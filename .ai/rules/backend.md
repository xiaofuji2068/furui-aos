# BACKEND RULES
# Stack
Python
FastAPI
---
# 1. API Layer
负责：
Request
Validation
Authentication
Authorization
Response
---
# 2. Application Service
负责：
业务流程。
---
# 3. Domain
负责：
业务规则。
---
# 4. Repository
负责：
数据访问。
---
# 5. Database
业务代码：
不要直接操作数据库。
通过：
Repository
---
# 6. Validation
所有输入：
必须验证。
---
# 7. Error
统一错误处理。
---
# 8. Logging
记录：
Request ID
User
Action
Result
Error
---
# 9. Transaction
多个数据操作：
考虑事务。
---
# 10. Idempotency
重复执行有风险：
考虑幂等。
---
# 11. External Service
必须考虑：
Timeout
Retry
Fallback
---
# 12. Performance
关注：
N+1
Large Query
Unbounded Query
Repeated API
---
# 13. API Compatibility
修改 API：
检查所有调用方。
---
# 14. Async
只有真正 IO 场景：
使用 async。
不要为了形式：
全部 async。
