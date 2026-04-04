import { MinimalChatDemo } from "@/components/workspace/minimal-chat-demo";

export default function WorkspacePage() {
  return (
    <MinimalChatDemo
      title="Workspace Demo"
      subtitle="这里保留 workspace 路由，但界面已经收敛成同一套最小聊天壳，不再展示旧的 sidebar、thread 列表和复杂状态。"
      badge="Workspace"
      threadId="new"
    />
  );
}
