"use client";

import { useEffect, useState } from "react";
import DashboardShell from "../components/DashboardShell";
import KpiCards from "../components/KpiCards";
import InsightsGrid from "../components/InsightsGrid";
import WorkingAgents from "../components/WorkingAgents";
import DataSources from "../components/DataSources";
import SystemHealth from "../components/SystemHealth";
import TasksPanel from "../components/TasksPanel";
import ActivitiesPanel from "../components/ActivitiesPanel";
import ChatBar from "../components/ChatBar";
import CreateAgentCTA from "../components/CreateAgentCTA";
import { api, streamSSE, approveApproval, rejectApproval } from "../lib/api";

export default function OverviewPage() {
  const [overview, setOverview] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [activities, setActivities] = useState<any[]>([]);
  const [chat, setChat] = useState<{ role: string; agent?: string; avatar?: string; content: string }[]>([
    { role: "ai", content: "" },
  ]);
  const [multiAgent, setMultiAgent] = useState(false);

  const loadAll = () => {
    Promise.all([
      api.get("/overview").catch(() => null),
      api.get("/agents").catch(() => ({ items: [] })),
      api.get("/approvals?status=Pending").catch(() => ({ items: [] })),
      api.get("/activities?limit=10").catch(() => ({ items: [] })),
    ]).then(([ov, ag, ap, ac]: any[]) => {
      setOverview(ov);
      setAgents(ag?.items || []);
      setApprovals(ap?.items || []);
      setActivities(ac?.items || []);
    });
  };

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (overview) {
      setChat([{
        role: "ai",
        agent: "企业智能助手",
        content: `你好，我是企业智能助手。今天我可以帮你：分析销售数据 / 查企业知识 / 发现经营问题 / 生成报告 / 创建 AI 员工…`,
      }]);
    }
  }, [overview]);

  const refetch = () => {
    api.get("/overview").then(setOverview).catch(() => {});
  };

  const reloadApprovalsAndActivities = () => {
    Promise.all([
      api.get("/approvals?status=Pending").catch(() => ({ items: [] })),
      api.get("/activities?limit=10").catch(() => ({ items: [] })),
    ]).then(([ap, ac]: any[]) => {
      setApprovals(ap?.items || []);
      setActivities(ac?.items || []);
    });
  };

  // 把审批单整理成 TasksPanel 需要的形状（id / title / description / created_at）
  const pendingTasks = approvals.map((a: any) => ({
    id: a.id,
    title: a.title,
    description:
      `${a.agent} · ${a.action}` + (a.ai_reason ? `：${String(a.ai_reason).slice(0, 40)}` : ""),
    created_at: a.created_at,
    level: a.level,
  }));

  const handleConfirm = async (id: number | string) => {
    await approveApproval(Number(id)).catch(() => {});
    reloadApprovalsAndActivities();
  };

  const handleReject = async (id: number | string) => {
    await rejectApproval(Number(id)).catch(() => {});
    reloadApprovalsAndActivities();
  };

  const handleSend = async (msg: string) => {
    setChat(c => [...c, { role: "user", content: msg }]);
    const idx = chat.length + 1;
    let acc = "";
    let header = "";
    let agentName = "";
    let avatar = "🤖";
    let sawToken = false;

    try {
      if (multiAgent) {
        // 多方会诊：POST /api/orchestrate（协调层 Coordinator）
        setChat(c => [...c, { role: "ai", agent: "🩺 多方会诊", avatar: "🩺", content: "正在组织专家会诊…" }]);
        await streamSSE("/orchestrate", { message: msg }, (ev, payload: any) => {
          if (ev === "plan") {
            const names = (payload.agents || []).map((a: any) => a.name).join("、");
            const mode = payload.strategy === "multi" ? "多领域 · 多方会诊" : "单一领域";
            header = `🩺 **多方会诊**已发起（${mode}）\n参与专家：${names || "—"}\n> ${payload.reason || ""}\n\n`;
          } else if (ev === "agent_view") {
            acc += `**@${payload.agent || "专家"}**：\n${payload.view || ""}\n\n`;
          } else if (ev === "token") {
            if (!sawToken) { acc += `\n---\n**综合结论**：\n`; sawToken = true; }
            acc += payload;
          }
          setChat(c => {
            const arr = [...c];
            arr[idx] = { role: "ai", agent: "🩺 多方会诊", avatar: "🩺", content: header + acc };
            return arr;
          });
        });
      } else {
        // 单 Agent 对话：POST /api/chat-stream（编排器 orchestrator）
        setChat(c => [...c, { role: "ai", agent: "思考中…", avatar: "🤖", content: "" }]);
        await streamSSE("/chat-stream", { message: msg, history: [] }, (ev, payload: any) => {
          if (ev === "agent") {
            agentName = payload.name;
            avatar = payload.avatar;
          } else if (ev === "token") {
            acc += payload;
          } else if (ev === "tool_call") {
            acc += `\n\n**[调用工具]** \`${payload.name}(${JSON.stringify(payload.args)})\`\n\n`;
          } else if (ev === "tool_result") {
            acc += "\n\n*（已从企业数据层获取结果）*\n\n";
          } else if (ev === "pending") {
            acc += `\n\n> ⚠️ 该操作需要你确认（在右侧"待确认任务"里点确认）\n`;
            api.get("/approvals?status=Pending")
              .then((t: any) => setApprovals(t?.items || []))
              .catch(() => {});
          }
          setChat(c => {
            const arr = [...c];
            arr[idx] = { role: "ai", agent: agentName || "AI 助手", avatar, content: acc };
            return arr;
          });
        });
      }
      api.get("/activities?limit=10")
        .then((a: any) => setActivities(a?.items || []))
        .catch(() => {});
    } catch (e) {
      setChat(c => {
        const arr = [...c];
        arr[idx] = { role: "ai", content: "**网络异常**，请确认后端 8000 端口是否启动。" };
        return arr;
      });
    }
  };

  return (
    <DashboardShell footer={<ChatBar chat={chat} onSend={handleSend} multiAgent={multiAgent} onToggleMulti={setMultiAgent} />}>
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">
            {overview?.greeting || "早上好，企业用户"}
            <span className="ml-2">👋</span>
          </h1>
          <p className="text-sm text-gray-400 mt-1">{overview?.subtitle}</p>
        </div>
      </div>

      <KpiCards kpis={overview?.kpis} />

      <SystemHealth />

      <section>
        <h2 className="text-base font-medium mb-3">数据连接状态</h2>
        <DataSources items={overview?.data_sources || []} onChanged={refetch} />
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-medium">企业 AI 洞察</h2>
          <button className="text-xs text-gray-400 hover:text-gray-200">查看更多 →</button>
        </div>
        <InsightsGrid items={overview?.insights || []} />
      </section>

      <section className="grid grid-cols-12 gap-5">
        <div className="col-span-12 xl:col-span-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-medium">正在工作的 AI 员工</h2>
            <button className="text-xs text-gray-400 hover:text-gray-200">查看全部 →</button>
          </div>
          <WorkingAgents agents={agents} />
        </div>
        <div className="col-span-12 xl:col-span-4 space-y-5">
          <TasksPanel items={pendingTasks} onConfirm={handleConfirm} onReject={handleReject} />
          <ActivitiesPanel items={activities} />
          <CreateAgentCTA />
        </div>
      </section>

    </DashboardShell>
  );
}
