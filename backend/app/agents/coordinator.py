"""多 Agent 编排（协调层 / Coordinator）。

定位（参考 Palantir AIP + Claude 多 Agent）：
    Agent OS 不止于"把一个问题丢给一个专家"，而是像一个指挥中心——
    1. 收到问题 → plan() 拆解意图，选出 1..N 个相关专家 Agent（DB 真实 Agent 表）
    2. 并发/串行地让每个 Agent 从自己的视角产出结论（agent_view）
    3. synthesize() 把多视角收敛成一份带归属的综合结论

真实数据原则：
    - 专家名单来自 DB agents 表（与首页/任务中心同一份真实数据）。
    - 每个 Agent 的"视角"锚定到 Ontology 语义层的真实对象（订单/设备/工单/风险事件），
      不编造数字；无 LLM key 时走 mock 生成（与 orchestrator._mock_chat 一致），
      LLM 就绪时可平滑替换为模型生成（run() 预留 use_llm 分支）。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI

from ..db import SessionLocal
from ..models_ai import Agent
from ..ontology import list_objects
from ..config import settings


# 各 Agent 负责的领域关键词 → 用于 plan() 的规则路由
_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "sales-analyst": ["销售", "订单", "客户", "区域", "增长", "下滑", "复盘", "归因", "营收", "业绩", "成交"],
    "ops-engineer":   ["设备", "故障", "工单", "运维", "监测", "异常", "停机", "巡检", "报警"],
    "knowledge-assistant": ["知识", "手册", "制度", "流程", "什么是", "怎么", "SOP", "规范", "文档", "规程"],
}


class Coordinator:
    """把一个问题分发给多位专家 Agent 并综合结论。"""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key or "sk-placeholder",
            base_url=settings.openai_base_url,
        )

    # ---------- 名册（真实 Agent 表） ----------

    def roster(self, db, company_id: Optional[int]) -> List[Agent]:
        q = db.query(Agent)
        if company_id:
            q = q.filter(Agent.company_id == company_id)
        # 只纳入可执行的 Agent
        return q.filter(Agent.status.in_(("Published", "Running", "Testing"))).all()

    # ---------- 规划：意图拆解 → 选专家 ----------

    def plan(self, question: str, agents: List[Agent]) -> Dict[str, Any]:
        text = question or ""
        picked: List[Agent] = []
        for a in agents:
            kws = _DOMAIN_KEYWORDS.get(a.code, [])
            if any(k in text for k in kws):
                picked.append(a)

        # 去重保序
        seen = set()
        picked = [a for a in picked if not (a.id in seen or seen.add(a.id))]

        if not picked:
            # 没有命中任何领域关键词 → 用 goal/规则/描述 给每个 Agent 打分，取最相关的一个
            if agents:
                picked = [max(agents, key=lambda a: self._score(a, text))]
            else:
                picked = []

        strategy = "multi" if len(picked) > 1 else "single"
        reason = ("命中多领域，发起多方会诊" if strategy == "multi"
                  else "命中单一领域，由对应专家独立处理")
        return {
            "strategy": strategy,
            "agents": picked,
            "reason": reason,
        }

    def _score(self, agent: Agent, text: str) -> int:
        """用 Agent 的目标/规则/描述/岗位 与问题做关键词重叠打分。"""
        blob = " ".join([
            agent.goal or "", agent.rules or "", agent.description or "", agent.position or "",
        ])
        return sum(1 for ch in set(text) if ch in blob)

    # ---------- 单 Agent 视角（锚定真实 Ontology 数据） ----------

    def agent_view(self, agent: Agent, question: str) -> str:
        facts = self._ground_facts(agent.code, question)
        head = f"【{agent.position or agent.name}视角】围绕「{question}」："
        if facts:
            body = "\n".join(f"- {f}" for f in facts[:4])
        else:
            body = "- 当前语义层暂无直接关联数据，建议补充对应数据源后重试。"
        return f"{head}\n{body}"

    def _ground_facts(self, agent_code: str, question: str) -> List[str]:
        """从 Ontology 真实对象中抽取与该 Agent 领域相关的要点（不编造）。"""
        facts: List[str] = []

        if agent_code == "sales-analyst":
            orders = list_objects("Order")
            total = sum((o.properties.get("amount") or 0) for o in orders)
            facts.append(f"在册订单 {len(orders)} 笔，合计金额 ¥{total:,.0f}")
            for t in list_objects("Ticket"):
                if t.properties.get("category") == "销售异常":
                    facts.append(f"风险事件：{t.properties.get('title')}（严重度 {t.properties.get('severity')}）")
            for p in list_objects("Product"):
                if (p.properties.get("stock") or 9999) < 200:
                    facts.append(f"库存预警：{p.properties.get('name')} 仅剩 {p.properties.get('stock')} 件")

        elif agent_code == "ops-engineer":
            for d in list_objects("Device"):
                facts.append(f"设备 {d.id} 状态：{d.properties.get('status')}")
            for w in list_objects("WorkOrder"):
                facts.append(f"工单 {w.id}：{w.properties.get('title')}（{w.properties.get('status')}）")
            for t in list_objects("Ticket"):
                title = t.properties.get("title") or ""
                if "库存" in title or "设备" in title:
                    facts.append(f"关联风险：{title}")

        elif agent_code == "knowledge-assistant":
            for t in list_objects("Ticket"):
                facts.append(f"知识风险点：{t.properties.get('title')}")
            facts.append("建议：将以上风险沉淀为 SOP，纳入企业知识库并定期复审。")

        return facts

    # ---------- 综合（收敛多视角） ----------

    def synthesize(self, question: str, views: List[Dict[str, Any]]) -> str:
        lines = [
            f"收到问题：「{question}」",
            "",
            f"已组织 {len(views)} 位专家从各自视角会诊：",
        ]
        for v in views:
            first = v["view"].split("\n", 1)[0]
            lines.append(f"- {v['agent']}：{first.replace('【', '').replace('视角】', '')}")

        lines.append("")
        lines.append("综合结论：")
        bullets: List[str] = []
        for v in views:
            for line in v["view"].split("\n")[1:]:
                line = line.strip()
                if line.startswith("- ") and line not in bullets:
                    bullets.append(line)
        lines += bullets[:8]

        lines.append("")
        lines.append("下一步建议：将结论转成可执行的审批 / 工单 / 报告——写入动作需经人工确认后才会落地。")
        return "\n".join(lines)

    # ---------- LLM 驱动：意图路由 / 专家视角 / 综合收敛 ----------

    async def _plan_llm(self, question: str, agents: List[Agent]) -> Optional[Dict[str, Any]]:
        """LLM 意图路由：从名册中选出相关专家。失败返回 None（调用方降级规则路由）。"""
        if not agents:
            return None
        roster_text = "\n".join(
            f"- code={a.code}｜名称={a.name}｜岗位={a.position}｜职责={a.description or ''}"
            for a in agents
        )
        system = (
            "你是傅瑞科技企业AI操作系统的意图路由。根据用户问题，从给出的AI员工中选出最相关的"
            "1~3位参与多方会诊。只输出JSON，不要输出其他内容，格式："
            '{"agent_codes": ["code1", "code2"], "reason": "一句话说明为什么选这些专家"}'
        )
        try:
            resp = await self.client.chat.completions.create(
                model=settings.model_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"用户问题：{question}\n\n可选AI员工：\n{roster_text}"},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            data = json.loads((resp.choices[0].message.content or "").strip())
            valid = {a.code for a in agents}
            picked = [a for a in agents if a.code in data.get("agent_codes", []) and a.code in valid]
            if not picked:
                return None
            strategy = "multi" if len(picked) > 1 else "single"
            reason = data.get("reason") or (
                "命中多领域，发起多方会诊" if strategy == "multi" else "由对应专家独立处理"
            )
            return {"strategy": strategy, "agents": picked, "reason": reason}
        except Exception:                                            # noqa: BLE001
            return None

    async def _agent_view_llm(self, agent: Agent, question: str, facts: List[str]) -> str:
        """让单个专家（携带角色设定与真实数据上下文）独立分析问题。"""
        fact_block = "\n".join(f"- {f}" for f in facts[:8]) if facts else "（当前语义层暂无直接关联数据）"
        system = "\n".join(filter(None, [
            agent.system_prompt or "",
            f"你的岗位：{agent.position}",
            f"你的目标：{agent.goal}",
            f"你的工作规则：{agent.rules}",
            "以下是企业当前的真实数据摘要，必须基于这些数据分析，不得编造任何数字。",
            fact_block,
        ]))
        user = (
            f"用户问题：{question}\n\n"
            f"请以「{agent.position or agent.name}」的视角，围绕这个问题给出你的专业分析与判断"
            "（200字以内，分点列出，并引用上面给出的数据）。"
        )
        stream = await self.client.chat.completions.create(
            model=settings.model_name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.3,
            stream=True,
        )
        parts: List[str] = []
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                parts.append(delta.content)
        text = "".join(parts).strip()
        if not text:
            return self.agent_view(agent, question)
        return f"【{agent.position or agent.name}视角】围绕「{question}」：\n{text}"

    async def _synthesize_llm(self, question: str, views: List[Dict[str, Any]]) -> str:
        """把多位专家视角交给 LLM 综合收敛。"""
        views_block = "\n\n".join(f"## {v['agent']}（{v.get('code', '')}）\n{v['view']}" for v in views)
        system = (
            "你是傅瑞科技企业AI操作系统的主持人。多位专家已从各自视角分析同一问题，"
            "请你综合收敛：先概括各方共识，再指出分歧或盲区，最后给出下一步可执行建议。"
            "必须基于专家提供的内容，不得编造数据；250字以内。"
        )
        user = f"原始问题：{question}\n\n各专家视角：\n{views_block}\n\n请给出综合结论。"
        stream = await self.client.chat.completions.create(
            model=settings.model_name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.3,
            stream=True,
        )
        parts: List[str] = []
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                parts.append(delta.content)
        text = "".join(parts).strip()
        if not text:
            return self.synthesize(question, views)
        return text

    # ---------- 执行（SSE 异步生成器） ----------

    async def run(self, question: str, company_id: Optional[int] = None) -> AsyncIterator[Dict[str, Any]]:
        db = SessionLocal()
        try:
            agents = self.roster(db, company_id)
            llm = settings.llm_enabled

            # 规划：LLM 意图路由（失败自动降级规则路由）
            if llm:
                plan = await self._plan_llm(question, agents) or self.plan(question, agents)
            else:
                plan = self.plan(question, agents)
            yield {
                "event": "plan",
                "data": json.dumps({
                    "strategy": plan["strategy"],
                    "reason": plan["reason"],
                    "agents": [{"name": a.name, "avatar": a.avatar or "🤖", "code": a.code} for a in plan["agents"]],
                }, ensure_ascii=False),
            }

            # 单 Agent 视角：LLM 并发生成（失败降级模板）；mock 走模板
            views: List[Dict[str, Any]] = []
            if llm:
                async def _view(a: Agent) -> Dict[str, Any]:
                    facts = self._ground_facts(a.code, question)
                    try:
                        v = await self._agent_view_llm(a, question, facts)
                    except Exception:                                      # noqa: BLE001
                        v = self.agent_view(a, question)
                    return {"agent": a.name, "avatar": a.avatar or "🤖", "code": a.code, "view": v}

                results = await asyncio.gather(*(_view(a) for a in plan["agents"]), return_exceptions=True)
                for r in results:
                    if isinstance(r, dict):
                        views.append(r)
                        yield {
                            "event": "agent_view",
                            "data": json.dumps(r, ensure_ascii=False),
                        }
            else:
                for a in plan["agents"]:
                    view = self.agent_view(a, question)
                    views.append({"agent": a.name, "avatar": a.avatar or "🤖", "code": a.code, "view": view})
                    yield {
                        "event": "agent_view",
                        "data": json.dumps(
                            {"agent": a.name, "avatar": a.avatar or "🤖", "code": a.code, "view": view},
                            ensure_ascii=False,
                        ),
                    }

            # 综合：LLM 收敛（失败降级模板）；mock 走模板
            if views:
                if llm:
                    try:
                        final = await self._synthesize_llm(question, views)
                    except Exception:                                      # noqa: BLE001
                        final = self.synthesize(question, views)
                else:
                    final = self.synthesize(question, views)
            else:
                final = self.synthesize(question, views)

            if llm:
                yield {"event": "token", "data": final}
            else:
                for chunk in _chunk(final, size=14):
                    yield {"event": "token", "data": chunk}
                    await asyncio.sleep(0.005)

            yield {
                "event": "done",
                "data": json.dumps(
                    {"strategy": plan["strategy"], "agents": [a.name for a in plan["agents"]]},
                    ensure_ascii=False,
                ),
            }
        finally:
            db.close()


def _chunk(s: str, size: int = 14) -> List[str]:
    return [s[i:i + size] for i in range(0, len(s), size)] or [""]


# 单例
coordinator = Coordinator()
