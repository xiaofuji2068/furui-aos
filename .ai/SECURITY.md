# SECURITY
# 1. Default
默认：
Zero Trust。
---
# 2. Authentication
所有受保护资源：
必须确认用户身份。
---
# 3. Authorization
身份确认之后：
必须确认权限。
---
# 4. Tenant Isolation
企业数据必须隔离。
Enterprise A：
不能访问：
Enterprise B
的数据。
---
# 5. Agent Permission
Agent：
继承用户权限。
不得绕过。
---
# 6. Input
所有外部输入：
必须验证。
---
# 7. SQL
禁止：
拼接用户输入 SQL。
---
# 8. Secrets
禁止提交：
API Key
Password
Token
Private Key
---
# 9. Environment
使用：
Environment Variables
---
# 10. Logs
日志禁止：
Password
Token
API Key
敏感个人信息
---
# 11. File Upload
文件上传必须考虑：
文件类型
文件大小
文件名
存储位置
恶意文件
---
# 12. External API
外部请求：
必须考虑：
Timeout
Retry
Authentication
Rate Limit
---
# 13. Destructive Actions
删除数据：
默认需要：
权限
确认
Audit
---
# 14. Audit
重要行为记录：
Who
When
What
Target
Result
---
# 15. AI Security
防止：
Prompt Injection
Data Leakage
Unauthorized Tool Call
Privilege Escalation
---
# 16. Sensitive Data
敏感数据：
最小权限
最小暴露
最小存储。
---
# 17. Security Priority
如果：
功能便利性
与
安全
发生冲突：
优先安全。
