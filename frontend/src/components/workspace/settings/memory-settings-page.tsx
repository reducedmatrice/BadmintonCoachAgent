"use client";

import { Streamdown } from "streamdown";

import { useI18n } from "@/core/i18n/hooks";
import { useMemory } from "@/core/memory/hooks";
import type { UserMemory } from "@/core/memory/types";
import { streamdownPlugins } from "@/core/streamdown/plugins";
import { pathOfThread } from "@/core/threads/utils";
import { formatTimeAgo } from "@/core/utils/datetime";

import { SettingsSection } from "./settings-section";

function confidenceToLevelKey(confidence: unknown): {
  key: "veryHigh" | "high" | "normal" | "unknown";
  value?: number;
} {
  if (typeof confidence !== "number" || !Number.isFinite(confidence)) {
    return { key: "unknown" };
  }

  // Clamp to [0, 1] since confidence is expected to be a probability-like score.
  const value = Math.min(1, Math.max(0, confidence));

  // 3 levels:
  // - veryHigh: [0.85, 1]
  // - high:     [0.65, 0.85)
  // - normal:   [0, 0.65)
  if (value >= 0.85) return { key: "veryHigh", value };
  if (value >= 0.65) return { key: "high", value };
  return { key: "normal", value };
}

function formatMemorySection(
  title: string,
  summary: string,
  updatedAt: string | undefined,
  sources: string[],
  threadIds: string[],
  t: ReturnType<typeof useI18n>["t"],
): string {
  const content =
    summary.trim() ||
    `<span class="text-muted-foreground">${t.settings.memory.markdown.empty}</span>`;
  return [
    `### ${title}`,
    content,
    "",
    updatedAt &&
      `> ${t.settings.memory.markdown.updatedAt}: \`${formatTimeAgo(updatedAt)}\``,
    `> ${t.settings.memory.markdown.sources}: ${
      sources.length > 0
        ? sources.map((source) => `\`${source}\``).join(", ")
        : t.settings.memory.markdown.none
    }`,
    `> ${t.settings.memory.markdown.threadIds}: ${
      threadIds.length > 0
        ? threadIds.map((threadId) => `[${threadId}](${pathOfThread(threadId)})`).join(", ")
        : t.settings.memory.markdown.none
    }`,
  ]
    .filter(Boolean)
    .join("\n");
}

function memoryToMarkdown(
  memory: UserMemory,
  t: ReturnType<typeof useI18n>["t"],
) {
  const parts: string[] = [];

  parts.push(`## ${t.settings.memory.markdown.overview}`);
  parts.push(
    `- **${t.common.lastUpdated}**: \`${formatTimeAgo(memory.lastUpdated)}\``,
  );

  parts.push(`\n## ${t.settings.memory.markdown.userContext}`);
  parts.push(
    formatMemorySection(
      t.settings.memory.markdown.work,
      memory.user.workContext.summary,
      memory.user.workContext.updatedAt,
      memory.user.workContext.sources,
      memory.user.workContext.thread_ids,
      t,
    ),
  );
  parts.push(
    formatMemorySection(
      t.settings.memory.markdown.personal,
      memory.user.personalContext.summary,
      memory.user.personalContext.updatedAt,
      memory.user.personalContext.sources,
      memory.user.personalContext.thread_ids,
      t,
    ),
  );
  parts.push(
    formatMemorySection(
      t.settings.memory.markdown.topOfMind,
      memory.user.topOfMind.summary,
      memory.user.topOfMind.updatedAt,
      memory.user.topOfMind.sources,
      memory.user.topOfMind.thread_ids,
      t,
    ),
  );

  parts.push(`\n## ${t.settings.memory.markdown.historyBackground}`);
  parts.push(
    formatMemorySection(
      t.settings.memory.markdown.recentMonths,
      memory.history.recentMonths.summary,
      memory.history.recentMonths.updatedAt,
      memory.history.recentMonths.sources,
      memory.history.recentMonths.thread_ids,
      t,
    ),
  );
  parts.push(
    formatMemorySection(
      t.settings.memory.markdown.earlierContext,
      memory.history.earlierContext.summary,
      memory.history.earlierContext.updatedAt,
      memory.history.earlierContext.sources,
      memory.history.earlierContext.thread_ids,
      t,
    ),
  );
  parts.push(
    formatMemorySection(
      t.settings.memory.markdown.longTermBackground,
      memory.history.longTermBackground.summary,
      memory.history.longTermBackground.updatedAt,
      memory.history.longTermBackground.sources,
      memory.history.longTermBackground.thread_ids,
      t,
    ),
  );

  parts.push(`\n## ${t.settings.memory.markdown.facts}`);
  if (memory.facts.length === 0) {
    parts.push(
      `<span class="text-muted-foreground">${t.settings.memory.markdown.empty}</span>`,
    );
  } else {
    parts.push(
      [
        `| ${t.settings.memory.markdown.table.category} | ${t.settings.memory.markdown.table.confidence} | ${t.settings.memory.markdown.table.content} | ${t.settings.memory.markdown.table.sourceEntry} | ${t.settings.memory.markdown.table.thread} | ${t.settings.memory.markdown.table.createdAt} |`,
        "|---|---|---|---|---|---|",
        ...memory.facts.map((f) => {
          const { key, value } = confidenceToLevelKey(f.confidence);
          const levelLabel =
            t.settings.memory.markdown.table.confidenceLevel[key];
          const confidenceText =
            typeof value === "number" ? `${levelLabel}` : levelLabel;
          const sourceText =
            f.sources.length > 0
              ? f.sources.map((source) => `\`${source}\``).join("<br/>")
              : t.settings.memory.markdown.none;
          const threadText =
            f.thread_ids.length > 0
              ? f.thread_ids
                  .map((threadId) => `[${t.settings.memory.markdown.table.view}](${pathOfThread(threadId)})`)
                  .join("<br/>")
              : (f.source && f.source !== "unknown"
                  ? `[${t.settings.memory.markdown.table.view}](${pathOfThread(f.source)})`
                  : t.settings.memory.markdown.none);
          return `| ${upperFirst(f.category)} | ${confidenceText} | ${f.content} | ${sourceText} | ${threadText} | ${formatTimeAgo(f.createdAt)} |`;
        }),
      ].join("\n"),
    );
  }

  const markdown = parts.join("\n\n");

  // Ensure every level-2 heading (##) is preceded by a horizontal rule.
  const lines = markdown.split("\n");
  const out: string[] = [];
  let i = 0;
  for (const line of lines) {
    i++;
    if (i !== 1 && line.startsWith("## ")) {
      if (out.length === 0 || out[out.length - 1] !== "---") {
        out.push("---");
      }
    }
    out.push(line);
  }

  return out.join("\n");
}

export function MemorySettingsPage() {
  const { t } = useI18n();
  const { memory, isLoading, error } = useMemory();
  return (
    <SettingsSection
      title={t.settings.memory.title}
      description={t.settings.memory.description}
    >
      {isLoading ? (
        <div className="text-muted-foreground text-sm">{t.common.loading}</div>
      ) : error ? (
        <div>Error: {error.message}</div>
      ) : !memory ? (
        <div className="text-muted-foreground text-sm">
          {t.settings.memory.empty}
        </div>
      ) : (
        <div className="rounded-lg border p-4">
          <Streamdown
            className="size-full [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
            {...streamdownPlugins}
          >
            {memoryToMarkdown(memory, t)}
          </Streamdown>
        </div>
      )}
    </SettingsSection>
  );
}

function upperFirst(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}
