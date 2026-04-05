import { getBackendBaseURL } from "@/core/config";

import type {
  AnalyticsAlert,
  AnalyticsByRoute,
  AnalyticsErrors,
  AnalyticsFilters,
  AnalyticsImportJob,
  AnalyticsImportResult,
  AnalyticsSummary,
  AnalyticsTimeseries,
} from "./types";

type Bucket = AnalyticsTimeseries["bucket"];

function buildQueryString(
  filters: AnalyticsFilters,
  extras: Record<string, string | number | undefined> = {},
) {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries({
    ...filters,
    ...extras,
  })) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    params.set(key, String(value));
  }

  const queryString = params.toString();
  return queryString ? `?${queryString}` : "";
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${getBackendBaseURL()}${path}`);
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `请求失败：${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function getAnalyticsSummary(
  filters: AnalyticsFilters,
): Promise<AnalyticsSummary> {
  return fetchJson<AnalyticsSummary>(
    `/api/analytics/summary${buildQueryString(filters)}`,
  );
}

export async function getAnalyticsTimeseries(
  filters: AnalyticsFilters,
  bucket: Bucket,
): Promise<AnalyticsTimeseries> {
  return fetchJson<AnalyticsTimeseries>(
    `/api/analytics/timeseries${buildQueryString(filters, { bucket })}`,
  );
}

export async function getAnalyticsByRoute(
  filters: AnalyticsFilters,
): Promise<AnalyticsByRoute> {
  return fetchJson<AnalyticsByRoute>(
    `/api/analytics/by-route${buildQueryString(filters)}`,
  );
}

export async function getAnalyticsErrors(
  filters: AnalyticsFilters,
): Promise<AnalyticsErrors> {
  return fetchJson<AnalyticsErrors>(
    `/api/analytics/errors${buildQueryString(filters)}`,
  );
}

export async function getAnalyticsImportJobs(
  limit = 20,
): Promise<AnalyticsImportJob[]> {
  const data = await fetchJson<{ jobs: AnalyticsImportJob[] }>(
    `/api/analytics/import-jobs${buildQueryString({}, { limit })}`,
  );
  return data.jobs;
}

export async function getAnalyticsAlerts(
  limit = 20,
): Promise<AnalyticsAlert[]> {
  const data = await fetchJson<{ alerts: AnalyticsAlert[] }>(
    `/api/analytics/alerts${buildQueryString({}, { limit })}`,
  );
  return data.alerts;
}

export async function triggerAnalyticsImport(
  logFile: string,
): Promise<AnalyticsImportResult> {
  const res = await fetch(`${getBackendBaseURL()}/api/analytics/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ log_file: logFile }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `导入失败：${res.statusText}`);
  }
  return res.json() as Promise<AnalyticsImportResult>;
}
