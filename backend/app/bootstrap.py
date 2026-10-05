"""系统初始化引导 — 建表、灌种子、建模拟外部库、建知识索引。

拆分原因：models.py 管组织域、models_ai.py 管 AI 域，
两者都有种子数据，且 AI 域种子依赖组织域已存在（需要 company_id / department_id）。
统一由本模块按顺序编排，避免循环导入。

幂等：可重复调用，已有数据不重复灌入。
"""
from __future__ import annotations

import json
from typing import Dict, List

from sqlalchemy.orm import Session

from .data_gateway import init_erp_db
from .db import SessionLocal, engine, ensure_column
from .models import Company, Department, User, init_db
from .models_ai import (
    Agent, AgentSkill, AIApplication, ApprovalRule, BusinessScenario,
    DataSource, EvalContract, KnowledgeBase, KnowledgeDocument, Tool,
)
from .rag import index_document
from .ontology import seed_ontology
from .assets import seed_bundles

# 当前分析月 / 对比月，与 data_gateway 样例数据保持一致
CURRENT_MONTH = "2026-08"
PREV_MONTH = "2026-07"


# ==================== 知识库种子内容 ====================
# 刻意与模拟 ERP/CRM 数据中埋的下降原因对齐：
# 数据里埋了「大客户流失 / 单价下调 / 新客断档」三条线索，
# 知识库里正好有对应的归因指引 —— 这样 Agent 检索到的知识才真的用得上。

KB_SEED: List[Dict] = [
    {
        "name": "销售管理知识库",
        "category": "业务知识",
        "authority_level": 2,
        "docs": [
            {
                "title": "客户分级管理办法",
                "source": "销售部 · 2026 版",
                "content": """客户分级管理办法（2026 修订版）

一、分级标准
A 类客户：年度订单金额 ≥ 500 万元，或具备行业标杆意义。
B 类客户：年度订单金额 100 万 ~ 500 万元。
C 类客户：年度订单金额 < 100 万元。

二、A 类客户管理要求
1. 指定专属客户成功经理，每月至少一次现场拜访。
2. 订单量环比下滑超过 30% 时，必须在 3 个工作日内启动流失预警，
   由销售负责人牵头，7 日内出具挽回方案。
3. 单客户流失将直接影响年度销售目标达成，需在经营会上专项复盘。

三、价格管理
1. 标准产品折扣权限：销售代表 5%，销售经理 15%，超过需总经理审批。
2. 服务类单价下调超过 10% 时，须评估对整体毛利的影响并报财务备案。
3. 季度内累计降价产品超过 3 项的，需提交价格策略复盘报告。
""",
            },
            {
                "title": "销售异常归因标准指引",
                "source": "经营管理部",
                "content": """销售异常归因标准指引

当月度销售额或订单量环比下滑超过 15% 时，按以下顺序逐项排查，不得跳步：

第一步：客户维度
按客户维度拆解环比，定位下滑贡献最大的客户。
若单一客户贡献的下滑量超过总下滑量的 40%，判定为「大客户因素」。

第二步：价格维度
对比主要产品单价变动。若某产品单价下调超过 8%，
且该产品占销售额比重较高，判定为「价格因素」。

第三步：新客维度
统计本月新客户首单数量。若新客首单数量环比减少超过 50%，
判定为「新客获取不足」，需检查线索量与转化漏斗。

第四步：季节与交付维度
排除行业季节性波动，以及因交付排期导致的订单确认延迟。

归因结论必须给出：主因、次因、影响金额、建议动作、责任人、完成时限。
""",
            },
            {
                "title": "大客户流失预警与挽回流程",
                "source": "销售部 · SOP-2026-07",
                "content": """大客户流失预警与挽回流程

一、预警触发
系统监测到大客户订单量环比下滑超过 30%，自动生成流失预警。

二、响应动作（分级）
1. 一级响应（下滑 30%~50%）：客户成功经理 3 日内电话沟通，
   了解原因，形成沟通记录。
2. 二级响应（下滑 50%~70%）：销售负责人 5 日内带队现场拜访，
   出具书面挽回方案。
3. 三级响应（下滑 > 70%）：总经理介入，启动高层对话，
   必要时调整商务条件。

三、常见流失原因
- 客户内部预算调整或项目延期
- 竞争对手低价切入
- 交付质量或响应速度未达预期
- 客户关键对接人变动

四、挽回动作闭环
每次挽回动作须录入 CRM，30 日内复盘效果，结果计入客户健康度评分。
""",
            },
            {
                "title": "新客户获取与转化管理规范",
                "source": "市场部",
                "content": """新客户获取与转化管理规范

一、线索目标
销售团队每月新增有效线索不少于 40 条，新客户首单不少于 4 家。

二、漏斗管理
线索 → 初步接触 → 需求确认 → 方案报价 → 商务谈判 → 签约首单
各环节转化率基准：40% / 50% / 60% / 50% / 70%

三、新客断档的处置
若连续两个月新客户首单低于目标值的 50%，
须由市场负责人牵头，两周内提交获客渠道复盘与改进计划，
并临时提高线索投放预算。

四、重点渠道
行业展会、老客户转介绍、产业协会、行业协会研修班、技术研讨会。
其中老客户转介绍转化率最高，应作为优先渠道投入。
""",
            },
            {
                "title": "2026 年 Q3 经营策略要点",
                "source": "总经理办公会纪要",
                "content": """2026 年 Q3 经营策略要点

一、总体基调
稳住存量，拓展增量。存量客户是基本盘，任何大客户的异常波动
都必须在 48 小时内上报经营会。

二、重点客户名单
恒力重工、中广核工程、浙能集团为三大战略客户，
三者合计占公司年度销售目标约 45%，须重点保障。

三、价格策略
Q3 原则上不做普遍性降价。对服务类产品（如三维建模、现场实施）
的降价须逐单审批，避免侵蚀毛利。

四、新客拓展
聚焦核电、能源、生物医药三个方向，依托行业协会与研修班渠道建联，
Q3 目标新增有效客户 12 家。

五、AI 能力赋能
推进企业 AI 操作系统建设，优先落地销售分析与知识助手场景，
用 AI 提升一线响应速度与分析深度。
""",
            },
        ],
    },
    {
        "name": "企业制度知识库",
        "category": "企业制度",
        "authority_level": 1,
        "docs": [
            {
                "title": "经营数据使用与授权规范",
                "source": "总经理办公室",
                "content": """经营数据使用与授权规范

一、数据分级
L1 公开：产品介绍、公开案例
L2 内部：销售订单、客户名录
L3 敏感：客户联系方式、产品成本、毛利数据
L4 核心：财务台账、合同金额明细

二、AI 系统使用规范
1. AI Agent 查询经营数据必须经 Data Gateway，禁止直连生产库。
2. L3、L4 级数据返回时自动脱敏，联系方式显示为 138****5678 格式。
3. AI 生成的所有结论必须标注数据来源与生成时间。
4. AI 的写入类动作（建单、发信、改数据）必须经人工审批后方可执行。

三、审计要求
所有数据查询、工具调用、审批动作全程留痕，保存期不少于 3 年。
""",
            },
            {
                "title": "AI 员工管理办法",
                "source": "总经理办公室",
                "content": """AI 员工管理办法

一、定位
AI 员工是辅助岗位，不具备独立决策权。所有对外、写入类动作
必须经人类确认后执行。

二、权限原则
每个 AI 员工必须显式配置：允许访问的知识、允许查询的数据、
允许调用的工具、允许执行的操作。四者均为白名单，未列入即禁止。

三、动作分级
Level 1 自动执行：查询、检索、生成草稿
Level 2 通知后执行：创建内部任务、生成报告
Level 3 必须审批：创建客户任务、发送外部邮件、修改业务数据
Level 4 禁止执行：删除核心数据、大额资金操作

四、考核
按任务完成率、人工修改率、审批拒绝率、单任务成本四项月度考核，
连续两月不达标的 AI 员工须下线整改。
""",
            },
        ],
    },
    {
        "name": "工业空间智能知识库",
        "category": "业务知识",
        "authority_level": 2,
        "docs": [
            {
                "title": "核电厂三维数字化交付标准",
                "source": "技术中心 · 2026 版",
                "content": """核电厂三维数字化交付标准

一、适用范围
核电厂新建/技改项目中的三维数字化成果交付，包括激光扫描点云、
BIM 模型、数字孪生平台与竣工资料。

二、坐标系与精度
1. 统一采用电厂控制网坐标，扫描前须完成控制点布设与联测。
2. 关键设备与管道：点云精度不低于 ±3mm；厂房结构：不低于 ±10mm。
3. 交付模型须通过点云与模型叠加比对（偏差云图），超差区域逐项标注。

三、交付物清单
点云数据（含报告）、处理后的模型（LOD300 以上）、数字孪生平台、
设备台账关联数据、验收记录。

四、验收流程
自检 → 抽检（不低于 10% 区域）→ 业主验收 → 归档。归档数据保存期
不少于电厂全生命周期。
""",
            },
            {
                "title": "点云数据采集与质量规范",
                "source": "技术中心",
                "content": """点云数据采集与质量规范

一、采集准备
作业前确认现场环境（粉尘、辐射、温度）与设备标定状态；
辐射区域作业须按辐射防护要求控制作业时长。

二、采集要求
1. 站点间距按扫描仪有效范围与遮挡情况布设，相邻站点重叠率 ≥ 30%。
2. 每站作业前完成黑白标靶/球标靶布设，用于拼接配准。
3. 分辨率按目标精度等级设定：高精度扫描 ≤ 3mm@10m，常规 ≤ 6mm@10m。

三、质量校验
1. 拼接误差：相邻站点配准误差 ≤ 5mm，全局闭环误差 ≤ 10mm。
2. 噪声点：有效点云占比 ≥ 95%，明显噪点（飞点）须人工清理。
3. 每批次出具质量报告，超差须返工重扫并留记录。

四、数据处理
去噪 → 配准 → 抽稀 → 分类 → 建模。每一步记录参数与耗时，
用于后续质量追溯与效率优化。
""",
            },
            {
                "title": "高危工业场景现场作业安全指引",
                "source": "安全环保部",
                "content": """高危工业场景现场作业安全指引

一、适用范围
核电、石化、大型设备厂房等高风险环境中的三维扫描、无人机巡检、
设备检修等现场作业。

二、作业准入
1. 进入现场前完成安全培训与授权，携带作业票/工作许可。
2. 辐射区域作业须佩戴个人剂量计，作业时长受控，超限须轮换。
3. 高处、受限空间、动火等特殊作业按现场规定单独审批。

三、设备安全
1. 激光扫描设备使用前检查电池、支架与防护罩，防止跌落与误触。
2. 无人机飞行须避开禁飞区与吊装作业区，保持安全距离。

四、应急与上报
发现设备异常、人员不适或环境指标异常，立即停止作业并上报现场
负责人，按应急预案处置，任何异常不得隐瞒。
""",
            },
            {
                "title": "辐射防护与监测限值标准",
                "source": "安全环保部 · 2026 版",
                "content": """辐射防护与监测限值标准

一、适用范围
核电厂运行与检修期间的辐射监测、个人剂量控制与异常响应。

二、监测限值
1. 区域剂量率（核岛运行区）常规限值 20 uSv/h，超过即触发告警。
2. 个人年剂量限值 20 mSv，月剂量超过 1/12 年度限值须评估作业安排。
3. 辐射监测站读数与阈值须每季度校准一次，偏差超过 5% 须上报。

三、异常响应
1. 剂量率超过限值时，AI 系统应在 15 分钟内完成初步归因：
   区分「设备故障 / 源项异常 / 测量装置漂移 / 背景波动」四类。
2. 初步归因须附带数据依据（读数、时间序列、关联设备状态），
   人工复核确认后 2 小时内生成处置工单。
3. 处置完成后 24 小时内闭环验收，异常记录保存期不少于 3 年。
""",
            },
            {
                "title": "核电设备巡检异常归因标准",
                "source": "技术中心 · 运维组",
                "content": """核电设备巡检异常归因标准

一、适用范围
辐射监测站、转动设备（主冷却泵等）、管道阀门等关键设备的
在线监测异常分析与处置。

二、归因维度（按序排查）
1. 指标维度：辐射剂量率、温度、振动三指标分别与各自阈值比对，
   超限指标单独归因。
2. 站点维度：同一厂区内多个监测站同时异常，优先怀疑共因
   （电源、网络、环境）；单站异常优先怀疑设备本体。
3. 时间维度：与上月同周期对比，识别持续劣化（连续上升）与
   突发的区别。

三、处置分级
1. 单指标超限 <15%：生成预警，纳入日巡检重点。
2. 单指标超限 ≥15% 或健康度 <60：生成工单，人工确认后 24 小时内处置。
3. 多指标同时超限或健康度 <40：升级为紧急工单，2 小时内响应。

四、闭环要求
工单须记录：异常描述、归因结论、处置动作、验收结果，全程留痕。
""",
            },
            {
                "title": "AI 辅助巡检作业规范",
                "source": "技术中心 · 运维组",
                "content": """AI 辅助巡检作业规范

一、巡检场景
基于三维模型与实时监测数据的设备巡检：辐射监测站、转动设备、
管道与关键区域。

二、AI 辅助流程
1. AI 基于历史数据与实时读数生成巡检重点与告警预判。
2. 巡检结果与三维模型叠加，异常点位自动标注空间位置。
3. AI 生成巡检报告，高风险项触发工单并进入人工审批。

三、人机分工
AI 负责数据监测、异常初筛与报告生成；人工负责现场确认、
处置决策与闭环验收。

四、数据与审计
巡检记录、AI 判断依据、人工处置过程全程留痕，保存期不少于 3 年，
供追溯与模型迭代。
""",
            },
        ],
    },
]


AGENT_SEED = [
    {
        "name": "销售分析 Agent",
        "code": "sales-analyst",
        "avatar": "📊",
        "position": "销售分析师",
        "agent_type": "analyst",
        "description": "负责销售数据分析、异常归因与经营建议生成，可查询 ERP 订单与 CRM 客户数据。",
        "system_prompt": "你是资深销售分析师。回答必须基于真实查询结果，禁止编造数据。所有结论需标注数据来源。",
        "goal": "及时发现销售异常，给出可执行的归因与改进建议。",
        "rules": "1. 先查数据再下结论；2. 引用企业知识库的归因规范；3. 不得编造任何数字。",
        "actions": ["read", "analyze", "report"],
        "approval_level": 3,
        "skills": ["query_erp_orders", "query_crm_customers", "search_knowledge",
                   "analyze_sales_drop", "create_sales_task"],
        "color": "from-rose-500 to-orange-500",
        "capabilities": ["销售趋势分析", "区域对比分析", "客户分层",
                         "异常归因", "增长机会挖掘", "周报自动生成"],
        "status": "Published",
    },
    {
        "name": "知识助手 Agent",
        "code": "knowledge-assistant",
        "avatar": "📚",
        "position": "知识管理专员",
        "agent_type": "assistant",
        "description": "负责企业知识检索、制度问答与文档摘要。",
        "system_prompt": "你是企业知识助手。只依据知识库内容回答，未检索到时须明确说明。",
        "goal": "让员工快速获得准确、可溯源的企业知识。",
        "rules": "1. 回答必须引用来源文档；2. 检索不到就直说，不得臆测。",
        "actions": ["read"],
        "approval_level": 1,
        "skills": ["search_knowledge"],
        "color": "from-violet-500 to-purple-500",
        "capabilities": ["知识语义检索", "文档归纳总结", "SOP 生成", "引用溯源"],
        "status": "Published",
    },
    {
        "name": "巡检分析 Agent",
        "code": "inspection-analyst",
        "avatar": "☢️",
        "position": "核电巡检分析师",
        "agent_type": "analyst",
        "description": "负责核电设备巡检数据分析、异常归因与处置工单建议，可查询监测站与设备指标数据。",
        "system_prompt": "你是核电巡检分析师。回答必须基于真实查询结果，禁止编造数据；超限结论须引用辐射防护与巡检归因标准。",
        "goal": "及时发现设备异常并给出可执行的处置建议。",
        "rules": "1. 先查数据再下结论；2. 引用巡检归因标准；3. 创建工单需人工审批。",
        "actions": ["read", "analyze", "report", "write"],
        "approval_level": 3,
        "skills": ["query_monitoring_stations", "query_device_metrics",
                   "search_knowledge", "analyze_inspection_anomaly", "create_workorder"],
        "color": "from-amber-500 to-red-500",
        "capabilities": ["监测站状态监控", "设备指标分析", "异常归因",
                         "健康度预警", "巡检工单生成", "辐射防护合规核查"],
        "status": "Published",
    },
    {
        "name": "设备运维 Agent",
        "code": "ops-engineer",
        "avatar": "⚙️",
        "position": "设备运维工程师",
        "agent_type": "operator",
        "description": "负责设备状态监控、工单生成与运维建议。",
        "system_prompt": "你是设备运维工程师，关注设备异常与维护计划。",
        "goal": "降低设备故障停机时间。",
        "rules": "1. 优先处理高危告警；2. 建工单需人工确认。",
        "actions": ["read", "analyze", "write"],
        "approval_level": 3,
        "skills": ["search_knowledge", "create_workorder", "send_notification"],
        "color": "from-sky-500 to-blue-500",
        "capabilities": ["设备故障诊断", "维护计划制定", "工单自动派发", "应急预案生成"],
        "status": "Testing",
    },
]


TOOL_SEED = [
    ("query_erp_orders",    "查询 ERP 销售订单", "查询工具", "按月份/区域/客户查询销售订单与金额", 1, "datasource:view"),
    ("query_crm_customers", "查询 CRM 客户信息", "查询工具", "查询客户分级、区域、联系方式（自动脱敏）", 1, "datasource:view"),
    ("search_knowledge",    "检索企业知识库",   "查询工具", "混合检索企业知识，返回可溯源片段", 1, "knowledge:use"),
    ("analyze_sales_drop",  "销售下降归因分析", "分析工具", "按客户/价格/新客三维度拆解销售下滑", 1, "tool:use"),
    ("create_sales_task",   "创建销售跟进任务", "执行工具", "在 CRM 中创建客户跟进任务（写入动作）", 3, "tool:use"),
    ("send_notification",   "发送通知",         "通知工具", "向企微/邮件发送通知（写入动作）", 3, "tool:use"),
    ("draft_report",        "草拟分析报告",     "文件工具", "生成 Markdown 格式分析报告", 2, "tool:use"),
    ("create_workorder",          "创建核电巡检工单", "执行工具", "为监测站/设备异常创建巡检处置工单（写入动作）", 3, "tool:use"),
    ("query_monitoring_stations", "查询核电监测站台账", "查询工具", "查询监测站基础信息与状态", 1, "datasource:view"),
    ("query_device_metrics",      "查询设备指标读数",   "查询工具", "查询辐射/温度/振动指标与阈值", 1, "datasource:view"),
    ("analyze_inspection_anomaly", "巡检异常归因分析", "分析工具", "按指标/站点/环比三维度拆解巡检异常", 1, "tool:use"),
]


def _seed_knowledge(db: Session, company_id: int) -> Dict[str, int]:
    """建知识库并建向量索引。返回 {知识库名: kb_id}。"""
    # 幂等补齐：已有知识库按名称跳过，新增知识库可增量种入
    existing = {k.name: k.id for k in db.query(KnowledgeBase).filter(
        KnowledgeBase.company_id == company_id).all()}
    kb_map: Dict[str, int] = dict(existing)
    for kb_def in KB_SEED:
        if kb_def["name"] in kb_map:
            continue
        kb = KnowledgeBase(
            company_id=company_id,
            name=kb_def["name"],
            category=kb_def["category"],
            description=f"{kb_def['name']}（种子数据）",
            authority_level=kb_def["authority_level"],
            allowed_department_ids="[]",     # 企业内公开
            status="active",
        )
        db.add(kb)
        db.flush()
        kb_map[kb.name] = kb.id

        for d in kb_def["docs"]:
            doc = KnowledgeDocument(
                kb_id=kb.id,
                company_id=company_id,
                title=d["title"],
                source=d["source"],
                file_type="txt",
                status="已发布",
                author="系统初始化",
                version=1,
            )
            db.add(doc)
            db.flush()
            index_document(db, doc, d["content"])

    db.commit()
    return kb_map


def _seed_agents(db: Session, company_id: int, dept_map: Dict[str, int],
                 kb_ids: List[int], ds_ids: List[int], tool_ids: Dict[str, int]) -> None:
    existing = {a.code: a for a in db.query(Agent).filter(Agent.company_id == company_id).all()}
    if existing:
        # 幂等补齐：老库升级时回填 color/capabilities，并补绑新增 Skill（如 create_workorder）
        for a in AGENT_SEED:
            ag = existing.get(a["code"])
            if not ag:
                continue
            changed = False
            if not ag.color and a.get("color"):
                ag.color = a["color"]
                changed = True
            if ag.capabilities in ("", "[]") and a.get("capabilities"):
                ag.capabilities = json.dumps(a["capabilities"], ensure_ascii=False)
                changed = True
            bound = {s.skill_name for s in ag.skills}
            for s in a["skills"]:
                if s in tool_ids and s not in bound:
                    db.add(AgentSkill(agent_id=ag.id, skill_name=s, enabled=True))
                    tid = tool_ids[s]
                    if tid not in ag.tool_ids:
                        ag.allowed_tool_ids = json.dumps(ag.tool_ids + [tid])
                    changed = True
            if changed:
                db.commit()
    # 逐条补齐完全新增的 Agent（如 TASK-002 巡检分析 Agent）
    for a in AGENT_SEED:
        if a["code"] in existing:
            continue
        agent = Agent(
            company_id=company_id,
            department_id=dept_map.get("销售部"),
            name=a["name"],
            code=a["code"],
            avatar=a["avatar"],
            position=a["position"],
            agent_type=a["agent_type"],
            description=a["description"],
            system_prompt=a["system_prompt"],
            goal=a["goal"],
            rules=a["rules"],
            status=a["status"],
            # 四类白名单：知识 / 数据 / 工具 / 操作
            allowed_knowledge_ids=json.dumps(kb_ids if a["code"] != "knowledge-assistant" else kb_ids),
            allowed_datasource_ids=json.dumps(
                ds_ids if a["code"] in ("sales-analyst", "inspection-analyst", "ops-engineer")
                else []),
            allowed_tool_ids=json.dumps([tool_ids[s] for s in a["skills"] if s in tool_ids]),
            allowed_actions=json.dumps(a["actions"]),
            approval_level=a["approval_level"],
            color=a.get("color", ""),
            capabilities=json.dumps(a.get("capabilities", []), ensure_ascii=False),
        )
        db.add(agent)
        db.flush()
        for s in a["skills"]:
            db.add(AgentSkill(agent_id=agent.id, skill_name=s, enabled=True))
        existing[a["code"]] = agent
    db.commit()

def _seed_tools_and_approvals(db: Session, company_id: int) -> Dict[str, int]:
    tool_ids: Dict[str, int] = {
        t.name: t.id for t in db.query(Tool).filter(Tool.company_id == company_id).all()
    }
    for name, label, cat, desc, level, perm in TOOL_SEED:
        if name in tool_ids:
            continue
        t = Tool(
            company_id=company_id, name=name, label=label, category=cat,
            description=desc, action_level=level, required_permission=perm, status="active",
        )
        db.add(t)
        db.flush()
        tool_ids[name] = t.id

        db.add(ApprovalRule(
            company_id=company_id, action=name, level=level,
            description=f"{label} — 动作分级 Level {level}",
            approver_role="owner",
        ))
    db.commit()
    return tool_ids


def _seed_datasources(db: Session, company_id: int) -> List[int]:
    ds_map = {d.name: d for d in db.query(DataSource).filter(DataSource.company_id == company_id).all()}
    if ds_map:
        existing = [d.id for d in ds_map.values()]
        # 幂等补齐：刷新已有数据源的 allowed_tables（旧库升级可能遗留空列表/旧定义）
        _EXPECT = {
            "ERP 销售系统": ["orders", "products", "sales_reps", "customers"],
            "CRM 客户系统": ["customers"],
            "IoT 设备监测系统": ["monitoring_stations", "device_metrics", "inspection_records"],
        }
        for _name, _tabs in _EXPECT.items():
            _ds = ds_map.get(_name)
            if _ds:
                try:
                    _cur = set(json.loads(_ds.allowed_tables or "[]"))
                except Exception:
                    _cur = set()
                if _cur != set(_tabs):
                    _ds.allowed_tables = json.dumps(_tabs, ensure_ascii=False)
        # 逐条补齐新增数据源（如 TASK-002 IoT 设备监测系统）
        if "IoT 设备监测系统" not in ds_map:
            iot = DataSource(
                company_id=company_id, name="IoT 设备监测系统", source_type="SQLite", category="IoT",
                description="模拟 IoT：核电监测站、设备指标、巡检记录（只读）",
                allowed_tables=json.dumps(["monitoring_stations", "device_metrics", "inspection_records"]),
                sensitive_fields=json.dumps([]),
                read_only=True, status="Connected",
            )
            db.add(iot)
            db.flush()
            from .models_ai import DataConnection
            db.add(DataConnection(
                source_id=iot.id, company_id=company_id, name="IoT 设备监测主连接",
                dsn="data/erp_crm.db", status="Connected", created_by="系统初始化",
            ))
            db.commit()
            existing.append(iot.id)
        return existing

    erp = DataSource(
        company_id=company_id, name="ERP 销售系统", source_type="SQLite", category="ERP",
        description="模拟 ERP：订单、产品、销售代表数据（只读）",
        # customers 与 CRM 同库，query_erp_orders 固定 JOIN customers 展示客户名
        allowed_tables=json.dumps(["orders", "products", "sales_reps", "customers"]),
        sensitive_fields=json.dumps(["cost"]),
        read_only=True, status="Connected",
    )
    crm = DataSource(
        company_id=company_id, name="CRM 客户系统", source_type="SQLite", category="CRM",
        description="模拟 CRM：客户、分级、联系方式（只读，敏感字段自动脱敏）",
        allowed_tables=json.dumps(["customers"]),
        sensitive_fields=json.dumps(["contact_phone", "id_card"]),
        read_only=True, status="Connected",
    )
    iot = DataSource(
        company_id=company_id, name="IoT 设备监测系统", source_type="SQLite", category="IoT",
        description="模拟 IoT：核电监测站、设备指标、巡检记录（只读）",
        allowed_tables=json.dumps(["monitoring_stations", "device_metrics", "inspection_records"]),
        sensitive_fields=json.dumps([]),
        read_only=True, status="Connected",
    )
    db.add_all([erp, crm, iot])
    db.flush()

    from .models_ai import DataConnection
    db.add(DataConnection(
        source_id=erp.id, company_id=company_id, name="ERP 主连接",
        dsn="data/erp_crm.db", status="Connected", created_by="系统初始化",
    ))
    db.add(DataConnection(
        source_id=crm.id, company_id=company_id, name="CRM 主连接",
        dsn="data/erp_crm.db", status="Connected", created_by="系统初始化",
    ))
    db.add(DataConnection(
        source_id=iot.id, company_id=company_id, name="IoT 设备监测主连接",
        dsn="data/erp_crm.db", status="Connected", created_by="系统初始化",
    ))
    db.commit()
    return [erp.id, crm.id, iot.id]


def _seed_scenarios(db: Session, company_id: int) -> None:
    # 已存在的场景名集合（用于增量补齐新场景）
    existing_names = {s.name for s in db.query(BusinessScenario).filter(BusinessScenario.company_id == company_id).all()}
    if existing_names and not {"监测站异常自动归因", "设备健康度预警"} - existing_names:
        return

    app = AIApplication(
        company_id=company_id, name="销售经营智能分析", code="SALES-AI",
        description="销售异常监测、归因分析与行动建议", owner="李明", status="running",
    )
    db.add(app)
    db.flush()

    if "销售下降自动归因" not in existing_names:
        db.add(BusinessScenario(
            company_id=company_id, application_id=app.id,
            name="销售下降自动归因", category="销售", owner="李明", department="销售部",
            problem="月度销售下滑时，人工归因耗时长且口径不统一",
            acceptance="输入问题后 60 秒内输出归因报告，主因定位准确率可复核",
            stage="运行中", progress=80, status="运行中",
        ))
    if "大客户流失预警" not in existing_names:
        db.add(BusinessScenario(
            company_id=company_id, application_id=app.id,
            name="大客户流失预警", category="销售", owner="王欢", department="销售部",
            problem="大客户订单下滑发现滞后，错过挽回窗口",
            acceptance="大客户环比下滑超 30% 时自动预警并生成挽回任务",
            stage="测试中", progress=45, status="测试中",
        ))

    if "监测站异常自动归因" in existing_names:
        return
    app2 = AIApplication(
        company_id=company_id, name="核电巡检智能分析", code="NUCLEAR-INSPECT-AI",
        description="设备监测异常归因、健康度预警与处置工单", owner="张工", status="running",
    )
    db.add(app2)
    db.flush()

    db.add(BusinessScenario(
        company_id=company_id, application_id=app2.id,
        name="监测站异常自动归因", category="核电巡检", owner="张工", department="运维部",
        problem="设备指标超限后人工排查慢、口径不统一",
        acceptance="输入问题后 60 秒内输出归因报告，超限站点与指标可复核",
        stage="运行中", progress=80, status="运行中",
    ))
    db.add(BusinessScenario(
        company_id=company_id, application_id=app2.id,
        name="设备健康度预警", category="核电巡检", owner="李工", department="运维部",
        problem="设备劣化趋势发现滞后，存在非计划停机风险",
        acceptance="健康度低于阈值或连续劣化时自动预警并生成处置工单",
        stage="测试中", progress=45, status="测试中",
    ))
    db.commit()


def seed_ai(db: Session) -> None:
    """AI 域种子（幂等）。依赖组织域已初始化。"""
    company = db.query(Company).filter(Company.code == "FURUI").first()
    if not company:
        return
    cid = company.id
    dept_map = {d.name: d.id for d in db.query(Department).filter(Department.company_id == cid).all()}

    kb_map = _seed_knowledge(db, cid)
    ds_ids = _seed_datasources(db, cid)
    tool_ids = _seed_tools_and_approvals(db, cid)
    _seed_agents(db, cid, dept_map, list(kb_map.values()), ds_ids, tool_ids)
    _seed_scenarios(db, cid)
    _seed_eval_contracts(db, cid)


def _seed_eval_contracts(db: Session, cid: int) -> None:
    """EvalContract 默认基线（图谱 #5）：三条红线，幂等 upsert。"""
    defaults = [
        {"name": "accuracy@agent", "description": "Agent 决策准确率下限",
         "metric": "accuracy", "operator": "gte", "threshold": 0.90},
        {"name": "fairness@approval", "description": "审批公平性评分下限",
         "metric": "fairness", "operator": "gte", "threshold": 0.80},
        {"name": "latency@toolcall", "description": "工具调用延迟上限（秒）",
         "metric": "latency", "operator": "lte", "threshold": 30.0},
    ]
    for d in defaults:
        row = (db.query(EvalContract)
               .filter(EvalContract.company_id == cid, EvalContract.name == d["name"])
               .first())
        if not row:
            db.add(EvalContract(company_id=cid, **d))
    db.commit()


def init_all(force_erp: bool = False) -> None:
    """完整初始化：组织域 → 模拟外部库 → AI 域。可重复调用。"""
    init_db()                                  # 组织域建表 + 种子
    # 既有表新增字段的幂等迁移（create_all 不改已有表）
    db_m = SessionLocal()
    try:
        ensure_column(db_m, "approvals", "decision_lineage", "TEXT DEFAULT '{}'")
        ensure_column(db_m, "agents", "color", "VARCHAR(64) DEFAULT ''")
        ensure_column(db_m, "agents", "capabilities", "TEXT DEFAULT '[]'")
        # TASK-012 长程任务状态机：TaskBrief 列（agent_stages / task_reviews 由 create_all 自动建新表）
        ensure_column(db_m, "agent_tasks", "brief", "TEXT DEFAULT '{}'")
    finally:
        db_m.close()
    init_erp_db(force=force_erp)               # 模拟 ERP/CRM
    db = SessionLocal()
    try:
        _fc = db.query(Company).order_by(Company.id).first()
        seed_ontology(db, company_id=_fc.id if _fc else 1)  # 本体归属当前企业（Phase 1 P0）
        seed_ai(db)
        seed_bundles(db)  # TASK-016 平台资产目录（幂等，全局 RLS 豁免）
    finally:
        db.close()
