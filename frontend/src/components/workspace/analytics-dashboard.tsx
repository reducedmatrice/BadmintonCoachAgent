"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ChartColumn,
  Clock3,
  Database,
  FileWarning,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Siren,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { BreadcrumbPage } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useAnalyticsAlerts,
  useAnalyticsByRoute,
  useAnalyticsErrors,
  useAnalyticsImportJobs,
  useAnalyticsSummary,
  useAnalyticsTimeseries,
  useTriggerAnalyticsImport,
  type AnalyticsAlert,
  type AnalyticsFilters,
  type AnalyticsImportJob,
  type AnalyticsTimeseries,
  type RouteMetrics,
} from "@/core/analytics";
import { formatTimeAgo } from "@/core/utils/datetime";

import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "./workspace-container";

const queryClient = new QueryClient();

const DEFAULT_FILTERS: AnalyticsFilters = {
  start_time: "",
  end_time: "",
  route: "",
  channel: "",
  assistant_id: "",
};

const DEFAULT_LOG_FILE = "logs/gateway.log";

export function AnalyticsDashboard() {
  return (
    <QueryClientProvider client={queryClient}>
      <AnalyticsDashboardInner />
    </QueryClientProvider>
  );
}

function AnalyticsDashboardInner() {
  const [draftFilters, setDraftFilters] = useState<AnalyticsFilters>(DEFAULT_FILTERS);
  const [appliedFilters, setAppliedFilters] =
    useState<AnalyticsFilters>(DEFAULT_FILTERS);
  const [bucket, setBucket] = useState<AnalyticsTimeseries["bucket"]>("hour");
  const [logFile, setLogFile] = useState(DEFAULT_LOG_FILE);

  const summaryQuery = useAnalyticsSummary(appliedFilters);
  const timeseriesQuery = useAnalyticsTimeseries(appliedFilters, bucket);
  const byRouteQuery = useAnalyticsByRoute(appliedFilters);
  const errorsQuery = useAnalyticsErrors(appliedFilters);
  const importJobsQuery = useAnalyticsImportJobs();
  const alertsQuery = useAnalyticsAlerts();
  const importMutation = useTriggerAnalyticsImport();

  const isInitialLoading =
    summaryQuery.isLoading ||
    timeseriesQuery.isLoading ||
    byRouteQuery.isLoading ||
    errorsQuery.isLoading ||
    importJobsQuery.isLoading ||
    alertsQuery.isLoading;

  const queryErrors = [
    summaryQuery.error,
    timeseriesQuery.error,
    byRouteQuery.error,
    errorsQuery.error,
    importJobsQuery.error,
    alertsQuery.error,
  ].filter(Boolean);

  const globalError = queryErrors[0] ?? importMutation.error ?? null;
  const hasAnyData =
    (summaryQuery.data?.total_requests ?? 0) > 0 ||
    (importJobsQuery.data?.length ?? 0) > 0 ||
    (alertsQuery.data?.length ?? 0) > 0;

  const handleApplyFilters = () => {
    setAppliedFilters(draftFilters);
  };

  const handleResetFilters = () => {
    setDraftFilters(DEFAULT_FILTERS);
    setAppliedFilters(DEFAULT_FILTERS);
    setBucket("hour");
  };

  const handleImport = async () => {
    const trimmedPath = logFile.trim();
    if (!trimmedPath) {
      toast.error("请先输入日志文件路径");
      return;
    }

    try {
      const result = await importMutation.mutateAsync(trimmedPath);
      toast.success(
        `导入完成：新增 ${result.records_inserted} 条，跳过 ${result.records_skipped} 条`,
      );
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "导入失败，请稍后重试",
      );
    }
  };

  return (
    <WorkspaceContainer className="bg-muted/20">
      <WorkspaceHeader>
        <BreadcrumbPage>Analytics</BreadcrumbPage>
      </WorkspaceHeader>
      <WorkspaceBody className="overflow-y-auto">
        <div className="flex w-full max-w-7xl flex-col gap-6 px-4 py-6 md:px-6">
          <Card>
            <CardHeader>
              <CardTitle>Analytics Dashboard</CardTitle>
              <CardDescription>
                查看请求量、错误率、延迟分布、路由拆分、告警与导入状态。
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-6">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
                <FilterField
                  label="开始时间"
                  input={
                    <Input
                      type="datetime-local"
                      value={toDateTimeLocalValue(draftFilters.start_time)}
                      onChange={(event) =>
                        setDraftFilters((current) => ({
                          ...current,
                          start_time: fromDateTimeLocalValue(event.target.value),
                        }))
                      }
                    />
                  }
                />
                <FilterField
                  label="结束时间"
                  input={
                    <Input
                      type="datetime-local"
                      value={toDateTimeLocalValue(draftFilters.end_time)}
                      onChange={(event) =>
                        setDraftFilters((current) => ({
                          ...current,
                          end_time: fromDateTimeLocalValue(event.target.value),
                        }))
                      }
                    />
                  }
                />
                <FilterField
                  label="Route"
                  input={
                    <Input
                      value={draftFilters.route ?? ""}
                      placeholder="agent_name 或 assistant_id"
                      onChange={(event) =>
                        setDraftFilters((current) => ({
                          ...current,
                          route: event.target.value,
                        }))
                      }
                    />
                  }
                />
                <FilterField
                  label="Channel"
                  input={
                    <Input
                      value={draftFilters.channel ?? ""}
                      placeholder="如 feishu / slack"
                      onChange={(event) =>
                        setDraftFilters((current) => ({
                          ...current,
                          channel: event.target.value,
                        }))
                      }
                    />
                  }
                />
                <FilterField
                  label="Assistant"
                  input={
                    <Input
                      value={draftFilters.assistant_id ?? ""}
                      placeholder="assistant_id"
                      onChange={(event) =>
                        setDraftFilters((current) => ({
                          ...current,
                          assistant_id: event.target.value,
                        }))
                      }
                    />
                  }
                />
                <FilterField
                  label="趋势窗口"
                  input={
                    <Select
                      value={bucket}
                      onValueChange={(value) =>
                        setBucket(value as AnalyticsTimeseries["bucket"])
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="选择窗口" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="minute">分钟</SelectItem>
                        <SelectItem value="hour">小时</SelectItem>
                        <SelectItem value="day">天</SelectItem>
                      </SelectContent>
                    </Select>
                  }
                />
              </div>
              <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
                <div className="flex flex-wrap gap-2">
                  <Button onClick={handleApplyFilters}>
                    <RefreshCw className="size-4" />
                    应用筛选
                  </Button>
                  <Button variant="outline" onClick={handleResetFilters}>
                    重置
                  </Button>
                </div>
                <div className="flex w-full flex-col gap-2 xl:max-w-xl">
                  <span className="text-sm font-medium">手动导入日志</span>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Input
                      value={logFile}
                      placeholder="例如 logs/gateway.log"
                      onChange={(event) => setLogFile(event.target.value)}
                    />
                    <Button
                      onClick={handleImport}
                      disabled={importMutation.isPending}
                      className="sm:w-36"
                    >
                      {importMutation.isPending ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Database className="size-4" />
                      )}
                      触发导入
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {globalError && (
            <Alert variant="destructive">
              <AlertTriangle />
              <AlertTitle>数据加载失败</AlertTitle>
              <AlertDescription>
                {globalError instanceof Error
                  ? globalError.message
                  : "暂时无法获取 analytics 数据。"}
              </AlertDescription>
            </Alert>
          )}

          {isInitialLoading ? (
            <AnalyticsLoadingState />
          ) : !hasAnyData ? (
            <AnalyticsEmptyState />
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                  title="总请求数"
                  value={formatInteger(summaryQuery.data?.total_requests ?? 0)}
                  subtitle="当前筛选窗口内"
                  icon={<Activity className="size-4" />}
                />
                <MetricCard
                  title="错误率"
                  value={formatPercent(summaryQuery.data?.error_rate ?? 0)}
                  subtitle={`总错误数 ${formatInteger(errorsQuery.data?.total_errors ?? 0)}`}
                  icon={<ShieldAlert className="size-4" />}
                />
                <MetricCard
                  title="P50 / P95 延迟"
                  value={`${formatLatency(summaryQuery.data?.p50_latency_ms ?? 0)} / ${formatLatency(summaryQuery.data?.p95_latency_ms ?? 0)}`}
                  subtitle="单位：ms"
                  icon={<Clock3 className="size-4" />}
                />
                <MetricCard
                  title="平均 Tokens"
                  value={formatDecimal(summaryQuery.data?.avg_total_tokens ?? 0)}
                  subtitle="平均 total tokens"
                  icon={<ChartColumn className="size-4" />}
                />
              </div>

              <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
                <Card>
                  <CardHeader>
                    <CardTitle>趋势图</CardTitle>
                    <CardDescription>
                      按 {bucketLabel(bucket)} 观察请求量、错误率与延迟变化。
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-4">
                    <TrendChart points={timeseriesQuery.data?.points ?? []} />
                    <div className="grid gap-3 md:grid-cols-3">
                      <TrendLegend
                        label="请求量"
                        value={formatInteger(
                          (timeseriesQuery.data?.points ?? []).reduce(
                            (sum, point) => sum + point.total_requests,
                            0,
                          ),
                        )}
                      />
                      <TrendLegend
                        label="最高错误率"
                        value={formatPercent(
                          Math.max(
                            0,
                            ...(timeseriesQuery.data?.points ?? []).map(
                              (point) => point.error_rate,
                            ),
                          ),
                        )}
                      />
                      <TrendLegend
                        label="最高 P95"
                        value={formatLatency(
                          Math.max(
                            0,
                            ...(timeseriesQuery.data?.points ?? []).map(
                              (point) => point.p95_latency_ms,
                            ),
                          ),
                        )}
                      />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>最近错误</CardTitle>
                    <CardDescription>快速查看错误分布与最近异常。</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-4">
                    <div className="flex flex-wrap gap-2">
                      {(errorsQuery.data?.error_types ?? []).slice(0, 4).map((item) => (
                        <div
                          key={item.error_type}
                          className="rounded-full border px-3 py-1 text-xs"
                        >
                          {item.error_type} · {item.count}
                        </div>
                      ))}
                    </div>
                    {(errorsQuery.data?.recent_errors ?? []).length > 0 ? (
                      <div className="space-y-3">
                        {errorsQuery.data?.recent_errors.slice(0, 5).map((item) => (
                          <div
                            key={`${item.created_at}-${item.route}-${item.error_type}`}
                            className="rounded-lg border p-3"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <span className="font-medium">{item.route}</span>
                              <span className="text-muted-foreground text-xs">
                                {formatRelativeTime(item.created_at)}
                              </span>
                            </div>
                            <div className="text-muted-foreground mt-1 text-sm">
                              {item.error_type} · {item.channel || "unknown"} ·{" "}
                              {item.assistant_id || "unknown"}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <SectionEmpty text="当前筛选下没有错误记录" />
                    )}
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-6 xl:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Route 统计</CardTitle>
                    <CardDescription>
                      按 route 维度查看请求数、延迟与 token 数据。
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <RouteTable routes={byRouteQuery.data?.routes ?? []} />
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>最近告警</CardTitle>
                    <CardDescription>
                      展示导入失败、高错误率和高 P95 延迟告警。
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <AlertList alerts={alertsQuery.data ?? []} />
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>导入任务</CardTitle>
                  <CardDescription>
                    查看最近导入状态、扫描结果与失败信息。
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ImportJobsList jobs={importJobsQuery.data ?? []} />
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}

function FilterField({
  label,
  input,
}: {
  label: string;
  input: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-sm font-medium">{label}</span>
      {input}
    </label>
  );
}

function MetricCard({
  title,
  value,
  subtitle,
  icon,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div className="space-y-1">
          <CardDescription>{title}</CardDescription>
          <CardTitle className="text-2xl">{value}</CardTitle>
        </div>
        <div className="text-muted-foreground">{icon}</div>
      </CardHeader>
      <CardContent className="text-muted-foreground text-sm">
        {subtitle}
      </CardContent>
    </Card>
  );
}

function TrendChart({
  points,
}: {
  points: AnalyticsTimeseries["points"];
}) {
  if (points.length === 0) {
    return <SectionEmpty text="当前筛选范围内没有趋势数据" />;
  }

  const width = 760;
  const height = 220;
  const padding = 24;
  const maxRequests = Math.max(...points.map((point) => point.total_requests), 1);
  const maxLatency = Math.max(...points.map((point) => point.p95_latency_ms), 1);
  const requestPath = buildLinePath(
    points.map((point) => point.total_requests),
    width,
    height,
    padding,
    maxRequests,
  );
  const latencyPath = buildLinePath(
    points.map((point) => point.p95_latency_ms),
    width,
    height,
    padding,
    maxLatency,
  );

  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <LegendPill color="bg-primary" label="请求量" />
        <LegendPill color="bg-amber-500" label="P95 延迟" />
      </div>
      <div className="overflow-hidden rounded-lg border">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="bg-card h-56 w-full"
          role="img"
          aria-label="analytics timeseries"
        >
          <rect x="0" y="0" width={width} height={height} fill="transparent" />
          <line
            x1={padding}
            y1={height - padding}
            x2={width - padding}
            y2={height - padding}
            stroke="currentColor"
            opacity="0.2"
          />
          <line
            x1={padding}
            y1={padding}
            x2={padding}
            y2={height - padding}
            stroke="currentColor"
            opacity="0.2"
          />
          <path
            d={requestPath}
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            className="text-primary"
          />
          <path
            d={latencyPath}
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            className="text-amber-500"
          />
          {points.map((point, index) => {
            const x =
              padding +
              (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
            return (
              <text
                key={`${point.bucket_start}-${index}`}
                x={x}
                y={height - 6}
                textAnchor="middle"
                className="fill-muted-foreground text-[10px]"
              >
                {compactBucketLabel(point.bucket_start)}
              </text>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

function TrendLegend({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}

function LegendPill({
  color,
  label,
}: {
  color: string;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} />
      <span>{label}</span>
    </div>
  );
}

function RouteTable({
  routes,
}: {
  routes: RouteMetrics[];
}) {
  if (routes.length === 0) {
    return <SectionEmpty text="当前筛选下没有 route 统计数据" />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="bg-muted/40">
          <tr className="[&_th]:px-4 [&_th]:py-3 [&_th]:font-medium">
            <th>Route</th>
            <th>请求数</th>
            <th>错误率</th>
            <th>P50</th>
            <th>P95</th>
            <th>Avg Tokens</th>
            <th>Channel</th>
          </tr>
        </thead>
        <tbody className="[&_td]:border-t [&_td]:px-4 [&_td]:py-3">
          {routes.map((route) => (
            <tr key={route.route}>
              <td className="font-medium">{route.route}</td>
              <td>{formatInteger(route.total_requests)}</td>
              <td>{formatPercent(route.error_rate)}</td>
              <td>{formatLatency(route.p50_latency_ms)}</td>
              <td>{formatLatency(route.p95_latency_ms)}</td>
              <td>{formatDecimal(route.avg_total_tokens)}</td>
              <td>{route.channels.join(", ") || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AlertList({
  alerts,
}: {
  alerts: AnalyticsAlert[];
}) {
  if (alerts.length === 0) {
    return <SectionEmpty text="最近没有告警事件" />;
  }

  return (
    <div className="space-y-3">
      {alerts.slice(0, 8).map((alert) => (
        <div key={alert.id} className="rounded-lg border p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Siren className="text-muted-foreground size-4" />
                <span className="font-medium">{alert.alert_type}</span>
              </div>
              <div className="text-muted-foreground text-sm">
                {formatRelativeTime(alert.created_at)} · {alert.severity} ·{" "}
                {alert.status}
              </div>
            </div>
            <div className="text-right text-xs">
              {alert.observed_value !== null && (
                <div>观测值：{formatAlertNumber(alert.observed_value)}</div>
              )}
              {alert.threshold_value !== null && (
                <div className="text-muted-foreground">
                  阈值：{formatAlertNumber(alert.threshold_value)}
                </div>
              )}
            </div>
          </div>
          <div className="text-muted-foreground mt-2 text-sm">
            时间窗：{alert.window_start || "-"} → {alert.window_end || "-"}
          </div>
        </div>
      ))}
    </div>
  );
}

function ImportJobsList({
  jobs,
}: {
  jobs: AnalyticsImportJob[];
}) {
  if (jobs.length === 0) {
    return <SectionEmpty text="还没有导入任务记录" />;
  }

  return (
    <div className="space-y-3">
      {jobs.slice(0, 8).map((job) => (
        <div
          key={job.id}
          className="flex flex-col gap-3 rounded-lg border p-4 lg:flex-row lg:items-center lg:justify-between"
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              {job.status === "success" ? (
                <Database className="text-muted-foreground size-4" />
              ) : (
                <FileWarning className="text-destructive size-4" />
              )}
              <span className="font-medium">{job.source_file}</span>
            </div>
            <div className="text-muted-foreground text-sm">
              {formatRelativeTime(job.started_at)} · {job.status}
            </div>
            {job.error_message && (
              <div className="text-destructive text-sm">{job.error_message}</div>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3 text-sm lg:min-w-[320px]">
            <StatChip label="扫描" value={formatInteger(job.records_scanned)} />
            <StatChip label="新增" value={formatInteger(job.records_inserted)} />
            <StatChip label="跳过" value={formatInteger(job.records_skipped)} />
          </div>
        </div>
      ))}
    </div>
  );
}

function StatChip({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border p-3 text-center">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-1 font-semibold">{value}</div>
    </div>
  );
}

function AnalyticsLoadingState() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <Card key={index}>
          <CardHeader>
            <CardDescription>加载中</CardDescription>
            <CardTitle className="text-muted-foreground text-base">
              正在读取 analytics 数据…
            </CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground text-sm">
            请稍候
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function AnalyticsEmptyState() {
  return (
    <Card>
      <CardContent className="py-12">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Database className="size-5" />
            </EmptyMedia>
            <EmptyTitle>还没有可展示的统计数据</EmptyTitle>
            <EmptyDescription>
              先通过上方“手动导入日志”按钮导入 gateway.log，再返回查看指标、
              趋势图、route 统计、告警和导入任务列表。
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <div className="text-muted-foreground text-sm">
              推荐先尝试：{DEFAULT_LOG_FILE}
            </div>
          </EmptyContent>
        </Empty>
      </CardContent>
    </Card>
  );
}

function SectionEmpty({
  text,
}: {
  text: string;
}) {
  return (
    <Empty className="min-h-48 border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Database className="size-5" />
        </EmptyMedia>
        <EmptyTitle>暂无数据</EmptyTitle>
        <EmptyDescription>{text}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

function buildLinePath(
  values: number[],
  width: number,
  height: number,
  padding: number,
  maxValue: number,
) {
  return values
    .map((value, index) => {
      const x =
        padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
      const y =
        height -
        padding -
        (Math.max(value, 0) / Math.max(maxValue, 1)) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
}

function toDateTimeLocalValue(value?: string) {
  if (!value) {
    return "";
  }
  return value.replace("Z", "").slice(0, 16);
}

function fromDateTimeLocalValue(value: string) {
  return value ? `${value}:00` : "";
}

function formatInteger(value: number) {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(
    value,
  );
}

function formatDecimal(value: number) {
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

function formatLatency(value: number) {
  return `${formatDecimal(value)} ms`;
}

function formatRelativeTime(value: string) {
  if (!value) {
    return "-";
  }

  try {
    return formatTimeAgo(new Date(value));
  } catch {
    return value;
  }
}

function compactBucketLabel(value: string) {
  if (!value) {
    return "-";
  }
  return value.includes("T") ? value.split("T")[1]?.slice(0, 5) ?? value : value;
}

function bucketLabel(bucket: AnalyticsTimeseries["bucket"]) {
  switch (bucket) {
    case "minute":
      return "分钟";
    case "day":
      return "天";
    case "hour":
    default:
      return "小时";
  }
}

function formatAlertNumber(value: number) {
  if (value <= 1) {
    return formatPercent(value);
  }
  return formatDecimal(value);
}
