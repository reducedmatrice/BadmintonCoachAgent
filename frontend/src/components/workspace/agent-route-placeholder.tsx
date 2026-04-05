"use client";

import Link from "next/link";

type AgentRoutePlaceholderProps = {
  title: string;
  description: string;
  badge?: string;
  agentName?: string;
  threadId?: string;
  backHref?: string;
  backLabel?: string;
};

export function AgentRoutePlaceholder({
  title,
  description,
  badge = "Agent Placeholder",
  agentName,
  threadId,
  backHref = "/workspace/agents",
  backLabel = "返回 Agents",
}: AgentRoutePlaceholderProps) {
  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f6f3ea_0%,#f0ebdf_42%,#e8e0d1_100%)] px-4 py-6 text-stone-900">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-3xl flex-col justify-center rounded-[28px] border border-stone-300/80 bg-[rgba(255,252,246,0.78)] px-8 py-10 shadow-[0_30px_80px_rgba(70,52,20,0.12)] backdrop-blur">
        <div className="flex flex-wrap items-center gap-2 text-xs tracking-[0.14em] text-stone-500 uppercase">
          <span className="rounded-full border border-stone-300 bg-stone-100 px-3 py-1">
            {badge}
          </span>
          {agentName ? (
            <span className="rounded-full border border-stone-300 bg-white px-3 py-1">
              Agent: {agentName}
            </span>
          ) : null}
          {threadId ? (
            <span className="rounded-full border border-stone-300 bg-white px-3 py-1">
              Thread: {threadId}
            </span>
          ) : null}
        </div>

        <h1 className="mt-4 text-3xl font-semibold tracking-[-0.03em]">
          {title}
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-stone-600">
          {description}
        </p>
        <p className="mt-4 text-xs leading-6 text-stone-500">
          这里现在只保留路由占位和基础说明，不再触发真实线程、流式响应、artifact
          或 agent bootstrap 逻辑。
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            className="rounded-full bg-stone-900 px-5 py-2 text-sm font-medium text-stone-50 transition hover:bg-stone-700"
            href={backHref}
          >
            {backLabel}
          </Link>
          <Link
            className="rounded-full border border-stone-300 bg-white px-5 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:text-stone-900"
            href="/"
          >
            返回首页
          </Link>
        </div>
      </div>
    </div>
  );
}
