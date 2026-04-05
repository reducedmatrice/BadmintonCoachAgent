"""Analytics backend helpers."""

from app.analytics.alerts import AnalyticsAlert, DEFAULT_ALERT_THRESHOLDS, evaluate_alerts_for_import
from app.analytics.database import (
    ANALYTICS_DB_RELATIVE_PATH,
    ANALYTICS_SCHEMA,
    connect_analytics_db,
    create_import_job,
    ensure_analytics_db,
    finalize_import_job,
    get_analytics_db_path,
    initialize_analytics_schema,
    insert_structured_log_run,
)
from app.analytics.dedupe import (
    StructuredLogDedupeKeys,
    build_structured_log_dedupe_keys,
    canonicalize_structured_log_payload,
    compute_dedupe_hash,
    compute_source_line_hash,
)
from app.analytics.parser import (
    parse_manager_structured_log_file,
    parse_manager_structured_log_line,
    parse_manager_structured_log_text,
)
from app.analytics.importer import (
    StructuredLogImportResult,
    import_manager_structured_log_file,
    import_manager_structured_log_text,
)
from app.analytics.repository import AnalyticsFilters, create_alert, list_alerts, list_filtered_runs, list_import_jobs
from app.analytics.service import get_alerts, get_by_route, get_errors, get_import_jobs, get_summary, get_timeseries

__all__ = [
    "ANALYTICS_DB_RELATIVE_PATH",
    "ANALYTICS_SCHEMA",
    "AnalyticsAlert",
    "AnalyticsFilters",
    "DEFAULT_ALERT_THRESHOLDS",
    "StructuredLogDedupeKeys",
    "build_structured_log_dedupe_keys",
    "canonicalize_structured_log_payload",
    "connect_analytics_db",
    "compute_dedupe_hash",
    "compute_source_line_hash",
    "create_alert",
    "create_import_job",
    "ensure_analytics_db",
    "evaluate_alerts_for_import",
    "finalize_import_job",
    "get_alerts",
    "get_analytics_db_path",
    "get_by_route",
    "get_errors",
    "get_import_jobs",
    "get_summary",
    "get_timeseries",
    "initialize_analytics_schema",
    "import_manager_structured_log_file",
    "import_manager_structured_log_text",
    "insert_structured_log_run",
    "list_alerts",
    "list_filtered_runs",
    "list_import_jobs",
    "parse_manager_structured_log_file",
    "parse_manager_structured_log_line",
    "parse_manager_structured_log_text",
    "StructuredLogImportResult",
]
