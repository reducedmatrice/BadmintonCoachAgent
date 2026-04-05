export interface AnalyticsFilters {
  start_time?: string;
  end_time?: string;
  route?: string;
  channel?: string;
  assistant_id?: string;
}

export interface AnalyticsSummary {
  total_requests: number;
  error_rate: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  avg_total_tokens: number;
  filters: Required<AnalyticsFilters>;
}

export interface TimeseriesPoint {
  bucket_start: string;
  total_requests: number;
  error_rate: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  avg_total_tokens: number;
}

export interface AnalyticsTimeseries {
  bucket: "minute" | "hour" | "day";
  points: TimeseriesPoint[];
  filters: Required<AnalyticsFilters>;
}

export interface RouteMetrics {
  route: string;
  assistant_ids: string[];
  channels: string[];
  total_requests: number;
  error_rate: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  avg_total_tokens: number;
}

export interface AnalyticsByRoute {
  routes: RouteMetrics[];
  filters: Required<AnalyticsFilters>;
}

export interface ErrorTypeCount {
  error_type: string;
  count: number;
}

export interface RecentError {
  created_at: string;
  channel: string;
  assistant_id: string;
  route: string;
  error_type: string;
}

export interface AnalyticsErrors {
  total_errors: number;
  error_rate: number;
  error_types: ErrorTypeCount[];
  recent_errors: RecentError[];
  filters: Required<AnalyticsFilters>;
}

export interface AnalyticsImportJob {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  source_file: string;
  records_scanned: number;
  records_inserted: number;
  records_skipped: number;
  error_message: string;
}

export interface AnalyticsAlert {
  id: number;
  created_at: string;
  alert_type: string;
  severity: string;
  window_start: string;
  window_end: string;
  threshold_value: number | null;
  observed_value: number | null;
  status: string;
  payload: Record<string, unknown>;
}

export interface AnalyticsImportResult {
  job_id: number;
  source_file: string;
  status: string;
  records_scanned: number;
  records_inserted: number;
  records_skipped: number;
  records_failed: number;
  alerts_generated: number;
  error_message: string;
}
