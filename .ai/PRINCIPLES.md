# PRINCIPLES
# P01 — Single Source of Truth
同一个业务概念：
只能存在一个权威定义。
例如：
Customer
不能同时存在：
Client
CustomerInfo
CustomerEntity
表达同一个概念。
---
# P02 — Domain First
先理解业务。
再设计代码。
不要：
先设计数据库
再硬套业务。
---
# P03 — Reuse First
新功能开发前：
必须搜索已有能力。
优先复用：
Entity
Service
Component
Hook
Tool
Workflow
---
# P04 — Simple First
简单方案可以解决：
不要复杂化。
---
# P05 — Explicit
重要逻辑必须明确。
不要依赖：
隐藏状态
魔法逻辑
隐式行为
---
# P06 — Separation of Concerns
UI
API
Application
Domain
Repository
Infrastructure
保持边界。
---
# P07 — Agent Is Not God
Agent 不拥有无限权限。
Agent 必须遵守：
用户权限
业务权限
系统规则。
---
# P08 — Agent Is Orchestrator
Agent：
理解
规划
选择
调用
组合
---
Tool：
执行能力。
---
Service：
执行业务。
---
Domain：
定义业务规则。
---
# P09 — Observable
重要行为：
必须能够追踪。
---
# P10 — Testable
核心能力：
必须能够测试。
---
# P11 — Documentation Is Code
重要代码变化：
必须同步文档。
---
# P12 — Architecture Is Explicit
重大架构变化：
必须记录 ADR。
---
# P13 — No Unrelated Changes
当前任务之外：
不要修改。
---
# P14 — Human in the Loop
高风险操作：
AI 建议
→
人工确认
→
执行。
---
# P15 — Long Term
任何设计都必须考虑：
今天能不能用？
三个月后还能不能维护？
一年后还能不能扩展？
