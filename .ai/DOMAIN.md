# DOMAIN
# 1. Core Domains
Enterprise
User
Customer
Contact
Project
Contract
Order
Task
Agent
Tool
Workflow
Knowledge
Document
Event
---
# 2. Enterprise
企业。
属性：
id
name
industry
status
created_at
updated_at
---
# 3. User
用户。
属于 Enterprise。
属性：
id
enterprise_id
name
email
role
status
---
# 4. Customer
客户。
属于 Enterprise。
属性：
id
enterprise_id
name
industry
status
owner_id
created_at
updated_at
---
# 5. Contact
客户联系人。
属于 Customer。
---
# 6. Project
项目。
可以关联：
Customer
User
Contract
Task
---
# 7. Contract
合同。
可以关联：
Customer
Project
---
# 8. Order
订单。
可以关联：
Customer
Project
Contract
---
# 9. Task
任务。
可以由：
User
或者
Agent
创建。
可以由：
User
或者
Agent
执行。
---
# 10. Agent
AI Agent。
可以：
调用 Tool
访问 Knowledge
执行 Workflow
分析数据
---
# 11. Tool
Agent 能力接口。
例如：
customer.search
customer.get
customer.analysis
project.search
project.get
task.create
task.update
report.generate
---
# 12. Workflow
确定性业务流程。
包含：
Trigger
Step
Condition
Action
Approval
Result
---
# 13. Knowledge
企业知识。
来源：
Document
Database
Manual
FAQ
Meeting
Record
---
# 14. Document
企业文档。
属性：
source
version
owner
permission
created_at
updated_at
---
# 15. Event
系统事件。
例如：
CustomerCreated
ProjectCreated
ContractSigned
TaskCreated
TaskCompleted
AgentExecuted
---
# 16. Relationships
Enterprise
├── User
├── Customer
│   └── Contact
├── Project
├── Contract
├── Order
├── Task
├── Agent
├── Knowledge
└── Document
---
Customer
├── Contact
├── Project
├── Contract
└── Order
---
Project
├── Contract
├── Order
└── Task
---
Agent
├── Tool
├── Workflow
└── Knowledge
---
# 17. New Entity Rule
新增 Entity 必须回答：
1. 是否有独立生命周期？
2. 是否有独立业务规则？
3. 是否有独立权限？
4. 是否需要独立事件？
5. 为什么现有 Entity 无法表达？
如果不能合理回答：
不要新增 Entity。
---
# 18. DTO
DTO：
不是 Domain Entity。
DTO 用于：
API
外部数据
页面展示
数据传输。
---
# 19. Naming
统一使用：
Customer
Project
Task
Contract
Enterprise
Agent
Knowledge
---
禁止为了不同模块创造：
CustomerInfo
CustomerEntity
CustomerData
ProjectInfo
TaskData
等重复概念。
除非业务意义确实不同。
