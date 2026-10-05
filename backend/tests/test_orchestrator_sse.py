"""P1 Orchestrator.chat SSE 序列化回归（接真 LLM 前必修）。

锁定：
- chat 流里所有"结构化"事件（agent / tool_call / pending / tool_result / done）
  的 data 必须是合法 JSON 字符串，不能把 dict 直接丢给 sse_starlette 2.1.3
  （其 encode() 对 data 走 str()，dict 会变成 Python repr，前端 JSON.parse 失败）。
- 模拟 sse_starlette 2.1.3 的 encode：data 非 str 时走 str(data)，验证结果仍可 json.loads。
- 路由级：真实打 POST /api/chat-stream，复刻前端 streamSSE 解析，确认 agent/done 可解析。

运行：
    backend/venv/Scripts/python.exe tests/test_orchestrator_sse.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.agents import orchestrator  # noqa: E402
from app.config import settings as cfg_settings  # noqa: E402

# chat() 里读的 settings 是 orchestrator 模块的全局名 → 替换它即可强制 mock 模式
# （settings.llm_enabled 是只读 property，无法直接赋值）
# 注意：`import app.agents.orchestrator as X` 拿到的是单例（被包 __init__ 遮蔽），
# 必须走 sys.modules 才能拿到真正的模块对象。
orch_mod = sys.modules["app.agents.orchestrator"]


class _MockSettings:
    """只提供 chat() 在 mock 分支需要的属性。"""
    llm_enabled = False


PASS, FAIL = [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'  PASS' if cond else '  FAIL'}  {name}" + (f"  <{extra}>" if extra and not cond else ""))


def wire_ok(ev: dict) -> tuple[bool, str | None]:
    """模拟 sse_starlette 2.1.3 ServerSentEvent.encode 的 data 序列化。"""
    data = ev.get("data")
    wire = data if isinstance(data, str) else str(data)
    try:
        json.loads(wire)
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, str(e)


async def _collect() -> list[dict]:
    events = []
    async for ev in orchestrator.chat("分析华东销售", []):
        events.append(ev)
    return events


def main():
    print(f"=== 系统 settings.llm_enabled={cfg_settings.llm_enabled}（测试强制 mock 模式）===")
    orig = orch_mod.settings
    orch_mod.settings = _MockSettings()
    try:
        print("=== 生成器级：事件 data 经 sse_starlette 序列化后仍为合法 JSON ===")
        events = asyncio.run(_collect())
        types = [e["event"] for e in events]
        check("含 agent 事件", "agent" in types)
        check("含 done 事件", "done" in types)
        check("含 token 事件(流式)", "token" in types)

        # token 是纯文本片段（前端保留原文，走 JSON.parse 的 catch 分支），
        # 只有"结构化"事件要求 data 是合法 JSON。
        STRUCTURED = {"agent", "tool_call", "pending", "tool_result", "done"}
        all_ok = True
        n_struct = 0
        for e in events:
            if e["event"] not in STRUCTURED:
                continue
            n_struct += 1
            ok, err = wire_ok(e)
            if not ok:
                all_ok = False
                print(f"    坏事件 {e['event']}: {err}")
        check(f"结构化事件 data 均可 json.loads（{n_struct} 个）", all_ok and n_struct > 0,
              f"n_struct={n_struct}")

        agent_ev = next((e for e in events if e["event"] == "agent"), None)
        ad = json.loads(agent_ev["data"]) if agent_ev else {}
        check("agent.data 含 name", bool(ad.get("name")))
        check("agent.data 含 avatar", "avatar" in ad)
        check("agent.data 含 role", "role" in ad)

        print("\n=== 路由级：POST /api/chat-stream 真实 SSE，复刻前端解析 ===")
        with TestClient(app) as c:
            r = c.post("/api/chat-stream", json={"message": "分析华东销售", "history": []})
            check("chat-stream 200", r.status_code == 200, str(r.status_code))
            raw = r.text.replace("\r\n", "\n")
            parsed: list[tuple[str, any]] = []
            for block in raw.split("\n\n"):
                ev = "message"
                dlines = []
                for line in block.split("\n"):
                    if line.startswith("event:"):
                        ev = line[6:].strip()
                    elif line.startswith("data:"):
                        dlines.append(line[5:].strip())
                if dlines:
                    raw_data = "\n".join(dlines)
                    if ev == "token":
                        # token 是纯文本片段，前端保留原文，不要求 JSON
                        parsed.append((ev, raw_data))
                        continue
                    try:
                        parsed.append((ev, json.loads(raw_data)))
                    except Exception as e:  # noqa: BLE001
                        check(f"路由结构化事件 data 可解析({ev})", False, str(e))
            ptypes = [p[0] for p in parsed]
            check("路由含 agent", "agent" in ptypes)
            check("路由含 done", "done" in ptypes)
            a = next((p[1] for p in parsed if p[0] == "agent"), {})
            check("路由 agent 含 name", bool(a.get("name")))
    finally:
        orch_mod.settings = orig

    print(f"\n=== 结果：PASS {len(PASS)} / FAIL {len(FAIL)} ===")
    if FAIL:
        print("失败：", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
