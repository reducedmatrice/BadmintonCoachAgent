from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.analytics.importer import StructuredLogImportResult, import_manager_structured_log_file
from app.analytics.repository import AnalyticsFilters
from app.analytics.service import get_alerts, get_by_route, get_errors, get_import_jobs, get_summary, get_timeseries

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
_REPO_ROOT = Path(__file__).resolve().parents[4]


class AnalyticsFiltersResponse(BaseModel):
    start_time: str = ""
    end_time: str = ""
    route: str = ""
    channel: str = ""
    assistant_id: str = ""


class SummaryResponse(BaseModel):
    total_requests: int
    error_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    avg_total_tokens: float
    filters: AnalyticsFiltersResponse


class TimeseriesPointResponse(BaseModel):
    bucket_start: str
    total_requests: int
    error_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    avg_total_tokens: float


class TimeseriesResponse(BaseModel):
    bucket: str
    points: list[TimeseriesPointResponse]
    filters: AnalyticsFiltersResponse


class RouteMetricsResponse(BaseModel):
    route: str
    assistant_ids: list[str]
    channels: list[str]
    total_requests: int
    error_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    avg_total_tokens: float


class ByRouteResponse(BaseModel):
    routes: list[RouteMetricsResponse]
    filters: AnalyticsFiltersResponse


class ErrorTypeResponse(BaseModel):
    error_type: str
    count: int


class RecentErrorResponse(BaseModel):
    created_at: str
    channel: str
    assistant_id: str
    route: str
    error_type: str


class ErrorsResponse(BaseModel):
    total_errors: int
    error_rate: float
    error_types: list[ErrorTypeResponse]
    recent_errors: list[RecentErrorResponse]
    filters: AnalyticsFiltersResponse


class ImportJobResponse(BaseModel):
    id: int
    started_at: str
    finished_at: str | None = None
    status: str
    source_file: str
    records_scanned: int
    records_inserted: int
    records_skipped: int
    error_message: str


class ImportJobsResponse(BaseModel):
    jobs: list[ImportJobResponse]


class AlertPayloadResponse(BaseModel):
    model_config = {"extra": "allow"}


class AlertResponse(BaseModel):
    id: int
    created_at: str
    alert_type: str
    severity: str
    window_start: str
    window_end: str
    threshold_value: float | None = None
    observed_value: float | None = None
    status: str
    payload: AlertPayloadResponse


class AlertsResponse(BaseModel):
    alerts: list[AlertResponse]


class ImportRequest(BaseModel):
    log_file: str = Field(..., description="要导入的 gateway.log 路径")


class ImportResponse(BaseModel):
    job_id: int
    source_file: str
    status: str
    records_scanned: int
    records_inserted: int
    records_skipped: int
    records_failed: int
    alerts_generated: int
    error_message: str


def _build_filters(
    start_time: str = "",
    end_time: str = "",
    route: str = "",
    channel: str = "",
    assistant_id: str = "",
) -> AnalyticsFilters:
    return AnalyticsFilters(
        start_time=start_time.strip(),
        end_time=end_time.strip(),
        route=route.strip(),
        channel=channel.strip(),
        assistant_id=assistant_id.strip(),
    )


@router.get("/summary", response_model=SummaryResponse)
async def analytics_summary(
    start_time: str = "",
    end_time: str = "",
    route: str = "",
    channel: str = "",
    assistant_id: str = "",
) -> SummaryResponse:
    data = get_summary(_build_filters(start_time, end_time, route, channel, assistant_id))
    return SummaryResponse.model_validate(data)


@router.get("/timeseries", response_model=TimeseriesResponse)
async def analytics_timeseries(
    start_time: str = "",
    end_time: str = "",
    route: str = "",
    channel: str = "",
    assistant_id: str = "",
    bucket: str = Query(default="hour", pattern="^(minute|hour|day)$"),
) -> TimeseriesResponse:
    data = get_timeseries(_build_filters(start_time, end_time, route, channel, assistant_id), bucket=bucket)
    return TimeseriesResponse.model_validate(data)


@router.get("/by-route", response_model=ByRouteResponse)
async def analytics_by_route(
    start_time: str = "",
    end_time: str = "",
    route: str = "",
    channel: str = "",
    assistant_id: str = "",
) -> ByRouteResponse:
    data = get_by_route(_build_filters(start_time, end_time, route, channel, assistant_id))
    return ByRouteResponse.model_validate(data)


@router.get("/errors", response_model=ErrorsResponse)
async def analytics_errors(
    start_time: str = "",
    end_time: str = "",
    route: str = "",
    channel: str = "",
    assistant_id: str = "",
) -> ErrorsResponse:
    data = get_errors(_build_filters(start_time, end_time, route, channel, assistant_id))
    return ErrorsResponse.model_validate(data)


@router.get("/import-jobs", response_model=ImportJobsResponse)
async def analytics_import_jobs(limit: int = Query(default=20, ge=1, le=200)) -> ImportJobsResponse:
    data = get_import_jobs(limit=limit)
    return ImportJobsResponse.model_validate(data)


@router.get("/alerts", response_model=AlertsResponse)
async def analytics_alerts(limit: int = Query(default=20, ge=1, le=200)) -> AlertsResponse:
    data = get_alerts(limit=limit)
    return AlertsResponse.model_validate(data)


@router.post("/import", response_model=ImportResponse)
async def analytics_import(payload: ImportRequest) -> ImportResponse:
    log_path = _resolve_log_file_path(payload.log_file)
    if log_path is None:
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        result = import_manager_structured_log_file(log_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to import structured logs") from exc

    return ImportResponse.model_validate(result.model_dump())


def _resolve_log_file_path(raw_path: str) -> Path | None:
    candidate = Path(raw_path.strip()).expanduser()
    if candidate.is_absolute():
        return candidate if candidate.exists() and candidate.is_file() else None

    search_roots = [
        Path.cwd(),
        Path.cwd().parent,
        _REPO_ROOT,
    ]
    for root in search_roots:
        resolved = (root / candidate).resolve()
        if resolved.exists() and resolved.is_file():
            return resolved
    return None
