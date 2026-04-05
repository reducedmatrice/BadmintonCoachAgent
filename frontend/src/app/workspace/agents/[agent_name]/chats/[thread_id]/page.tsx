"use client";

import { useParams } from "next/navigation";

import { AgentRoutePlaceholder } from "@/components/workspace/agent-route-placeholder";

export default function AgentChatPage() {
  const { agent_name, thread_id } = useParams<{
    agent_name: string;
    thread_id: string;
  }>();

  return (
    <AgentRoutePlaceholder
      title="Agent Chat Demo"
      description="`/workspace/agents/[agent_name]/chats/[thread_id]` 现在只保留最小 demo，占位展示当前 `agent_name` 和 `thread_id`，不再进入真实聊天线程。"
      badge="Agent Mode"
      agentName={agent_name}
      threadId={thread_id}
      backHref="/workspace/agents"
      backLabel="返回 Agents Demo"
    />
  );
}
