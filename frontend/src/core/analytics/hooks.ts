import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAnalyticsAlerts,
  getAnalyticsByRoute,
  getAnalyticsErrors,
  getAnalyticsImportJobs,
  getAnalyticsSummary,
  getAnalyticsTimeseries,
  triggerAnalyticsImport,
} from "./api";
import type { AnalyticsFilters, AnalyticsTimeseries } from "./types";

export function useAnalyticsSummary(filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["analytics", "summary", filters],
    queryFn: () => getAnalyticsSummary(filters),
  });
}

export function useAnalyticsTimeseries(
  filters: AnalyticsFilters,
  bucket: AnalyticsTimeseries["bucket"],
) {
  return useQuery({
    queryKey: ["analytics", "timeseries", filters, bucket],
    queryFn: () => getAnalyticsTimeseries(filters, bucket),
  });
}

export function useAnalyticsByRoute(filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["analytics", "by-route", filters],
    queryFn: () => getAnalyticsByRoute(filters),
  });
}

export function useAnalyticsErrors(filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["analytics", "errors", filters],
    queryFn: () => getAnalyticsErrors(filters),
  });
}

export function useAnalyticsImportJobs(limit = 20) {
  return useQuery({
    queryKey: ["analytics", "import-jobs", limit],
    queryFn: () => getAnalyticsImportJobs(limit),
  });
}

export function useAnalyticsAlerts(limit = 20) {
  return useQuery({
    queryKey: ["analytics", "alerts", limit],
    queryFn: () => getAnalyticsAlerts(limit),
  });
}

export function useTriggerAnalyticsImport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (logFile: string) => triggerAnalyticsImport(logFile),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}
