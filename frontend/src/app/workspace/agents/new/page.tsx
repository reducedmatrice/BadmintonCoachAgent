import Link from "next/link";

export default function NewAgentPage() {
  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f6f3ea_0%,#f0ebdf_42%,#e8e0d1_100%)] px-4 py-6 text-stone-900">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-3xl flex-col items-center justify-center rounded-[28px] border border-stone-300/80 bg-[rgba(255,252,246,0.78)] px-8 py-10 text-center shadow-[0_30px_80px_rgba(70,52,20,0.12)] backdrop-blur">
        <span className="rounded-full border border-stone-300 bg-stone-100 px-3 py-1 text-xs tracking-[0.14em] text-stone-500 uppercase">
          Agent Placeholder
        </span>
        <h1 className="mt-4 text-3xl font-semibold tracking-[-0.03em]">
          Agent 创建流已暂时下线
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-6 text-stone-600">
          这个页面先不保留原来的 bootstrap 创建流程。当前目标是把前端压到最小可跑 demo，
          后续如果要恢复创建 agent，再在新的简化界面上重做。
        </p>
        <Link
          className="mt-6 rounded-full bg-stone-900 px-5 py-2 text-sm font-medium text-stone-50 transition hover:bg-stone-700"
          href="/workspace/agents"
        >
          返回 Agent Demo
        </Link>
      </div>
    </div>
  );
}
