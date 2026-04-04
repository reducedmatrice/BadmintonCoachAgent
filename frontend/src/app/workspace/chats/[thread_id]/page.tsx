"use client";

import { useParams } from "next/navigation";

import { MinimalChatDemo } from "@/components/workspace/minimal-chat-demo";

export default function ChatPage() {
  const { thread_id } = useParams<{ thread_id: string }>();

  return (
    <MinimalChatDemo
      title={thread_id === "new" ? "New Chat Demo" : "Thread Demo"}
      subtitle="真实线程流已临时下线。这个页面只保留最小聊天壳，用来验证前端路由和对话窗口可以正常工作。"
      badge="Workspace"
      threadId={thread_id}
    />
  );
}
