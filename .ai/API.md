# API RULES
# 1. API Philosophy
API 是系统契约。
必须：
明确
稳定
可测试
可理解。
---
# 2. Standard
推荐：
REST API。
---
# 3. Naming
使用：
/api/v1/customers
/api/v1/customers/{id}
/api/v1/projects
/api/v1/tasks
---
# 4. HTTP
GET
查询。
POST
创建。
PUT / PATCH
修改。
DELETE
删除。
---
# 5. Response
统一响应结构。
成功：
{
  "data": {},
  "meta": {}
}
失败：
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {}
  }
}
实际实现可以根据现有项目框架调整，
但整个项目必须保持一致。
---
# 6. Validation
所有外部输入：
必须验证。
---
# 7. Authentication
受保护 API：
必须认证。
---
# 8. Authorization
敏感 API：
必须授权。
---
# 9. Pagination
列表接口：
必须考虑分页。
不要默认返回无限数据。
---
# 10. Filtering
复杂列表：
使用明确 Query Parameters。
---
# 11. Error
错误：
必须可理解。
不要把：
Stack Trace
直接返回给用户。
---
# 12. Version
重大 API Breaking Change：
必须升级 Version。
---
# 13. Documentation
API 变化：
同步更新 API Documentation。
---
# 14. Compatibility
修改 API：
必须检查：
Frontend
Agent
Tool
External Client
Tests
