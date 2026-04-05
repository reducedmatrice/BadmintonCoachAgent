import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f6f3ea_0%,#f0ebdf_42%,#e8e0d1_100%)] px-4 py-6 text-stone-900">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-3xl flex-col justify-center rounded-[28px] border border-stone-300/80 bg-[rgba(255,252,246,0.78)] px-8 py-10 shadow-[0_30px_80px_rgba(70,52,20,0.12)] backdrop-blur">
        <span className="w-fit rounded-full border border-stone-300 bg-stone-100 px-3 py-1 text-xs tracking-[0.14em] text-stone-500 uppercase">
          Home Demo
        </span>
        <h1 className="mt-4 text-3xl font-semibold tracking-[-0.03em]">
          Badminton-Coach-Agent
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-stone-600">
          首页问答已先下线，避免继续走旧的真实对话链路并返回历史的 DeerFlow
          文案。当前首页只保留最小导航入口，后续再按新的产品形态接回交互。
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            className="rounded-full bg-stone-900 px-5 py-2 text-sm font-medium text-stone-50 transition hover:bg-stone-700"
            href="/workspace/agents"
          >
            打开 Agents Demo
          </Link>
          <Link
            className="rounded-full border border-stone-300 bg-white px-5 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:text-stone-900"
            href="/workspace/chats/new"
          >
            打开 Chat Demo
          </Link>
        </div>
      </div>
    </div>
  );
}
