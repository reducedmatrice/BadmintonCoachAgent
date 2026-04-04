"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { extractTextFromMessage } from "@/core/messages/utils";
import { useLocalSettings } from "@/core/settings";
import { DEFAULT_LOCAL_SETTINGS } from "@/core/settings/local";
import { SubtasksProvider } from "@/core/tasks/context";
import { useThreadStream } from "@/core/threads/hooks";
import { uuid } from "@/core/utils/uuid";

type DemoMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
};

type MinimalChatDemoProps = {
  title: string;
  subtitle: string;
  badge?: string;
  agentName?: string;
  threadId?: string;
  composerLabel?: string;
};

const queryClient = new QueryClient();

export function MinimalChatDemo(props: MinimalChatDemoProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <SubtasksProvider>
        <MinimalChatDemoInner {...props} />
      </SubtasksProvider>
    </QueryClientProvider>
  );
}

function MinimalChatDemoInner({
  title,
  subtitle,
  badge = "Backend Demo",
  agentName,
  threadId,
  composerLabel = "输入一条消息，验证真实 backend 对话流程",
}: MinimalChatDemoProps) {
  const pathname = usePathname();
  const [settings] = useLocalSettings();
  const [input, setInput] = useState("");
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [sessionThreadId, setSessionThreadId] = useState(() =>
    threadId && threadId !== "new" ? threadId : uuid(),
  );
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (threadId && threadId !== "new") {
      setSessionThreadId(threadId);
      return;
    }
    setSessionThreadId(uuid());
  }, [threadId]);

  const context = {
    ...DEFAULT_LOCAL_SETTINGS.context,
    ...settings.context,
    mode: settings.context.mode ?? "flash",
  };

  const [thread, sendMessage] = useThreadStream({
    threadId: sessionThreadId,
    context,
    onError: (error) => {
      setRuntimeError(error.message);
    },
    onStart: (createdThreadId) => {
      setSessionThreadId(createdThreadId);
      if (pathname.endsWith("/new")) {
        history.replaceState(
          null,
          "",
          pathname.replace(/\/new$/, `/${createdThreadId}`),
        );
      }
    },
  });

  const messages = useMemo<DemoMessage[]>(() => {
    const collected = thread.messages
      .map((message) => {
        if (message.type !== "human" && message.type !== "ai") {
          return null;
        }

        const content = extractTextFromMessage(message);
        if (!content) {
          return null;
        }

        return {
          id: message.id ?? `${message.type}-${Math.random()}`,
          role: message.type === "human" ? "user" : "assistant",
          content,
        } satisfies DemoMessage;
      })
      .filter((message): message is DemoMessage => message !== null);

    if (collected.length > 0) {
      return collected;
    }

    return [
      {
        id: "welcome",
        role: "assistant",
        content: agentName
          ? `你好，我是 ${agentName}。现在这个最小聊天窗已经接到真实 backend，你可以直接发消息验证链路。`
          : "你好，这个最小聊天窗已经接到真实 backend。你可以直接发消息验证链路。",
      },
    ];
  }, [thread.messages, agentName]);

  const meta = useMemo(() => {
    const items = [badge];
    if (agentName) {
      items.push(`Agent: ${agentName}`);
    }
    if (sessionThreadId) {
      items.push(`Thread: ${sessionThreadId}`);
    }
    items.push(`Mode: ${context.mode ?? "flash"}`);
    return items.join("  ");
  }, [badge, agentName, sessionThreadId, context.mode]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thread.isLoading]);

  async function handleSend() {
    const value = input.trim();
    if (!value || thread.isLoading) {
      return;
    }

    setRuntimeError(null);
    setInput("");
    try {
      await sendMessage(
        sessionThreadId,
        {
          text: value,
          files: [],
        },
        agentName ? { agent_name: agentName } : undefined,
      );
    } catch (error) {
      setRuntimeError(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f6f3ea_0%,#f0ebdf_42%,#e8e0d1_100%)] px-4 py-6 text-stone-900">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-5xl flex-col overflow-hidden rounded-[28px] border border-stone-300/80 bg-[rgba(255,252,246,0.78)] shadow-[0_30px_80px_rgba(70,52,20,0.12)] backdrop-blur">
        <header className="border-b border-stone-300/70 px-6 py-5">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs tracking-[0.16em] text-stone-500 uppercase">
            <span className="rounded-full border border-stone-300 bg-stone-100 px-2 py-1">
              {badge}
            </span>
            {agentName && (
              <span className="rounded-full border border-stone-300 bg-white px-2 py-1">
                {agentName}
              </span>
            )}
            <span className="rounded-full border border-emerald-300 bg-emerald-50 px-2 py-1 text-emerald-700">
              Real Backend
            </span>
          </div>
          <h1 className="text-3xl font-semibold tracking-[-0.03em]">{title}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-stone-600">
            {subtitle}
          </p>
          <p className="mt-3 text-xs text-stone-500">{meta}</p>
        </header>

        <main className="flex min-h-0 flex-1 flex-col">
          <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
            {runtimeError && (
              <div className="flex justify-start">
                <div className="max-w-2xl whitespace-pre-wrap rounded-[22px] border border-rose-300 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-800 shadow-sm">
                  backend 返回错误：
                  {"\n"}
                  {runtimeError}
                </div>
              </div>
            )}

            {messages.map((message) => {
              const isUser = message.role === "user";

              return (
                <div
                  key={message.id}
                  className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-2xl whitespace-pre-wrap rounded-[22px] px-4 py-3 text-sm leading-6 shadow-sm ${
                      isUser
                        ? "bg-stone-900 text-stone-50"
                        : "border border-stone-200 bg-white text-stone-800"
                    }`}
                  >
                    {message.content}
                  </div>
                </div>
              );
            })}

            {thread.isLoading && (
              <div className="flex justify-start">
                <div className="rounded-[22px] border border-stone-200 bg-white px-4 py-3 text-sm text-stone-500 shadow-sm">
                  backend 正在生成回复...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="border-t border-stone-300/70 bg-[rgba(255,250,242,0.72)] px-6 py-5">
            <label className="mb-2 block text-xs tracking-[0.14em] text-stone-500 uppercase">
              {composerLabel}
            </label>
            <div className="flex flex-col gap-3">
              <textarea
                className="min-h-28 w-full rounded-[20px] border border-stone-300 bg-white px-4 py-3 text-sm leading-6 outline-none transition focus:border-stone-500"
                placeholder="比如：请简单介绍一下你能做什么。"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void handleSend();
                  }
                }}
              />

              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-stone-500">
                  Enter 发送，Shift + Enter 换行。当前已经接入真实 LangGraph backend。
                </p>
                <button
                  type="button"
                  className="rounded-full bg-stone-900 px-5 py-2 text-sm font-medium text-stone-50 transition hover:bg-stone-700 disabled:cursor-not-allowed disabled:bg-stone-400"
                  disabled={!input.trim() || thread.isLoading}
                  onClick={() => void handleSend()}
                >
                  {thread.isLoading ? "生成中" : "发送"}
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
