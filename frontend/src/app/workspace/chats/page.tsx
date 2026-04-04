import { MinimalChatDemo } from "@/components/workspace/minimal-chat-demo";

export default function ChatsPage() {
  return (
    <MinimalChatDemo
      title="Chat Demo"
      subtitle="原来的 chats 列表页已被收缩。现在这里直接展示一个最小可交互对话窗口，便于先跑通前端 demo。"
      badge="Workspace"
    />
  );
}
