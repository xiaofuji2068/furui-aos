# FRONTEND RULES
# Stack
React
TypeScript
---
# 1. Architecture
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
# 2. Component
Component：
单一职责。
---
# 3. Page
Page：
负责组合。
不要承载所有业务逻辑。
---
# 4. Business Logic
业务逻辑：
不要写在 JSX。
应该进入：
Hook
Service
Application Layer
---
# 5. API
API：
统一通过 API Service。
不要：
多个页面重复 fetch。
---
# 6. State
区分：
Local State
Server State
Global State
---
# 7. Async
必须处理：
Loading
Success
Error
Empty
---
# 8. Permission
前端：
可以隐藏无权限操作。
后端：
必须重新验证。
---
# 9. Components
优先复用：
Button
Modal
Table
Form
Card
Layout
---
# 10. Design System
新页面：
优先使用现有 Design System。
---
# 11. TypeScript
禁止无理由：
any
---
# 12. Performance
关注：
Unnecessary Render
Repeated Request
Large Component
Large List
---
# 13. UI Philosophy
企业软件：
清晰
简洁
高信息密度
低认知负担。
不要：
为了视觉效果增加无意义动画。
---
# 14. AI UI
AI 页面应该明确：
AI 正在做什么
AI 知道什么
AI 不知道什么
AI 建议什么
AI 是否正在执行
AI 执行结果是什么。
