# CODING RULES
# 1. Readability
代码优先：
Readable
Explicit
Predictable
Maintainable
---
# 2. Single Responsibility
模块尽量单一职责。
---
# 3. Naming
命名必须表达业务意义。
禁止：
data
temp
obj
foo
bar
manager2
helper2
---
# 4. Reuse
发现已有能力：
优先复用。
---
# 5. Duplication
避免明显重复。
但是不要：
为了消灭少量重复而建立复杂抽象。
---
# 6. Error
禁止：
except:
    pass
禁止吞掉异常。
---
# 7. Logging
正式代码不要依赖：
print()
---
# 8. Configuration
环境相关配置：
不要硬编码。
---
# 9. Dependencies
增加依赖前：
先搜索现有项目。
---
# 10. Comments
注释解释：
Why
不要大量解释：
What
---
# 11. Type Safety
尽量使用明确类型。
不要使用：
any
来掩盖设计问题。
---
# 12. Side Effects
尽量减少：
隐藏 Side Effect。
---
# 13. Unrelated Change
不要：
顺便格式化整个项目。
不要：
顺便重命名无关代码。
不要：
顺便升级依赖。
---
# 14. Large File
如果一个文件越来越大：
考虑拆分。
但不要机械拆分。
---
# 15. Public API
修改公共接口：
必须检查调用方。
---
# 16. Code Review
完成任务以后：
主动检查：
Correctness
Security
Architecture
Reuse
Maintainability
Test
