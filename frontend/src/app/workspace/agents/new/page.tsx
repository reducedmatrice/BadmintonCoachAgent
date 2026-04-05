import { AgentRoutePlaceholder } from "@/components/workspace/agent-route-placeholder";

export default function NewAgentPage() {
  return (
    <AgentRoutePlaceholder
      title="Agent 创建流已暂时下线"
      description="`/workspace/agents/new` 已改成轻量占位页，不再保留原来的 bootstrap 创建流程。后续如果恢复创建能力，再基于新的简化界面重做。"
      backHref="/workspace/agents"
      backLabel="返回 Agents Demo"
    />
  );
}
