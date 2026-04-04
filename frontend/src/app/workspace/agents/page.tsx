import { MinimalChatDemo } from "@/components/workspace/minimal-chat-demo";

export default function AgentsPage() {
  return (
    <MinimalChatDemo
      title="Agents Demo"
      subtitle="原来的 agent 列表和管理卡片先撤掉，保留一个可运行的最小入口。后续如果要恢复 agent 管理，再在这个基础上重新加。"
      badge="Agent Mode"
      agentName="default-agent"
    />
  );
}
