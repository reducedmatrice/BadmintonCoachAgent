# Analytics Acceptance

This document captures the final acceptance status for the `dev-spec-database2.1` analytics MVP.

## Acceptance Summary

The structured log analytics MVP is complete across:

- SQLite schema and idempotent import
- parser / repository / service / alerts
- gateway analytics APIs
- frontend analytics dashboard
- local scheduling and operations runbook
- regression and end-to-end validation

## Backend Validation

Validated coverage includes:

- parser normalization
- dedupe hash stability and duplicate skip behavior
- importer job accounting and alert generation
- repository and aggregation queries
- API route integration
- end-to-end import → query → file-summary cross-check

Primary verification command:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_analytics_end_to_end.py tests/test_analytics_router.py tests/test_analytics_service.py tests/test_analytics_importer.py tests/test_analytics_parser.py tests/test_analytics_database.py tests/test_structured_logs.py tests/test_run_log_report.py
```

## Frontend Validation

Validated items:

- `/workspace/analytics` route builds and serves successfully
- dashboard layout renders filters and manual import controls
- analytics data layer passes typecheck and lint
- production build succeeds with the same dashboard route enabled
- page loads without browser console errors in the acceptance environment

Primary verification commands:

```bash
cd frontend
pnpm typecheck
pnpm eslint src/app/workspace/analytics/page.tsx src/components/workspace/analytics-dashboard.tsx src/core/analytics/api.ts src/core/analytics/hooks.ts src/core/analytics/index.ts src/core/analytics/types.ts
BETTER_AUTH_SECRET=dummy NEXT_PUBLIC_BACKEND_BASE_URL=http://127.0.0.1:8001 pnpm build
```

## Operational Validation

Validated items:

- one-shot analytics import works from `scripts/import_structured_logs.py`
- `make analytics-import` triggers the wrapper script successfully
- scheduler wrapper supports `LOG_FILE` and optional `DB_PATH`
- cron example is documented
- rollback path keeps file-based analytics available through `scripts/summarize_run_logs.py`

## Regression Guarantees

The MVP preserves the following guarantees:

- structured logging to `logs/gateway.log` remains the source of truth
- analytics import failure does not block the main bot request flow
- SQLite storage can be disabled operationally by stopping the scheduler
- historical logs can be re-imported later for recovery

## Explicit Follow-ups

The following items are intentionally left for later phases and are no longer blocking acceptance:

- move alert thresholds from code constants into config or UI
- add external alert delivery such as Feishu webhook or email
- migrate from SQLite to PostgreSQL or ClickHouse when concurrency or data volume requires it
- introduce a dedicated chart library only if the current SVG approach becomes insufficient
