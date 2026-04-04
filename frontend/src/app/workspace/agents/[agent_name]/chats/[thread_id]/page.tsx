"use client";

import { useParams } from "next/navigation";

import { MinimalChatDemo } from "@/components/workspace/minimal-chat-demo";

export default function AgentChatPage() {
  const { agent_name, thread_id } = useParams<{
    agent_name: string;
    thread_id: string;
  }>();

  return (
    <MinimalChatDemo
      title="Agent Chat Demo"
      subtitle="这里保留了 agent chat 路由，但复杂的 thread 流、todo、artifact 和欢迎态都已移除，只剩最小对话窗口。"
      badge="Agent Mode"
      agentName={agent_name}
      threadId={thread_id}
    />
  );
}
