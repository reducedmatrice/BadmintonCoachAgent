import { AgentRoutePlaceholder } from "@/components/workspace/agent-route-placeholder";

export default function AgentsPage() {
  return (
    <AgentRoutePlaceholder
      title="Agents Demo"
      description="`/workspace/agents` 现在指向最小 demo，占位说明为主。这里不再加载旧的 agent 列表、管理卡片，也不会再连真实 agent 线程。"
      badge="Agent Mode"
      backHref="/"
      backLabel="返回首页"
    />
  );
}
