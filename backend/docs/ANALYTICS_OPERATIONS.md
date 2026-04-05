# Analytics Operations

This document describes how to run, schedule, deploy, and roll back the structured log analytics subsystem introduced by `dev-spec-database2.1`.

## Scope

The analytics subsystem currently includes:

- structured log ingestion from `logs/gateway.log`
- SQLite storage at `backend/.deer-flow/analytics/structured_logs.db`
- gateway analytics APIs under `/api/analytics/*`
- frontend dashboard at `/workspace/analytics`
- basic alerts for import failure, high error rate, and high P95 latency

The subsystem is intentionally isolated from the primary bot request path. If analytics import or SQLite storage fails, file-based logging and agent chat flows continue to work.

## Local Operations

### One-shot import

You can run one import job manually with either the Python entrypoint or the Make target:

```bash
./scripts/import_structured_logs.py --log-file ./logs/gateway.log
```

```bash
make analytics-import LOG_FILE=./logs/gateway.log
```

Optional database override:

```bash
./scripts/import_structured_logs.py --log-file ./logs/gateway.log --db-path ./backend/.deer-flow/analytics/structured_logs.db
```

### Cron entry

The wrapper script `scripts/run-analytics-import.sh` is designed for cron usage and defaults to `logs/gateway.log`.

Example cron line:

```cron
*/10 * * * * LOG_FILE=/Users/you/path/to/note-agent/logs/gateway.log /Users/you/path/to/note-agent/scripts/run-analytics-import.sh >> /Users/you/path/to/note-agent/logs/analytics-import.log 2>&1
```

The same example is stored in:

- `scripts/analytics-import.cron.example`

### Expected result

Each run should:

- create or update one row in `structured_log_import_jobs`
- insert new run rows into `structured_log_runs`
- skip duplicate rows safely when the same file is imported again
- write alert rows into `structured_log_alerts` when thresholds are exceeded

## Cloud Deployment

### Container deployment

The current Docker deployment already mounts the backend runtime home under `.deer-flow`, which is also where the analytics SQLite database lives.

For cloud deployment, preserve the following properties:

- mount `backend/.deer-flow` to persistent storage
- keep `logs/gateway.log` writable by the gateway container
- run analytics import as a separate scheduled job, not in the request-serving process

Recommended deployment shape:

1. Gateway keeps writing structured logs.
2. Scheduler invokes `scripts/run-analytics-import.sh` on a fixed cadence.
3. Analytics API and frontend read from the SQLite file on the shared persistent volume.

### Scheduler options

Supported scheduler approaches for the current MVP:

- host cron on a single VM
- container platform scheduled job
- GitHub Actions scheduled workflow for non-production demo environments
- Kubernetes `CronJob`

For production-like setups, prefer a platform scheduler or Kubernetes `CronJob` over embedding cron directly into the main gateway container.

### SQLite persistence and risk

SQLite is acceptable for the current single-instance, low-concurrency MVP, but it has clear limits:

- write contention increases under multiple simultaneous import jobs
- storage remains node-local unless a persistent volume is attached
- failover across multiple replicas is limited

If you need multi-instance writers, stronger HA, or larger historical analytics volume, move off SQLite.

## Migration Boundaries

The current abstraction boundary is:

- parser / importer stay unchanged
- repository and service remain the public analytics access layer
- API contracts under `/api/analytics/*` stay stable

Recommended migration path:

- PostgreSQL: first target for service-grade durability and multi-user access
- ClickHouse: later target for large-scale analytics and more complex reporting

When migrating, replace the SQL implementation inside the repository/database layer first, then keep the service and API contracts unchanged as much as possible.

## Rollback and Fault Isolation

### Rollback policy

If analytics causes operational issues:

1. disable the cron or scheduler job
2. keep gateway structured logging enabled
3. keep `/workspace/analytics` available if reads still work; otherwise allow it to degrade with empty/error state
4. fall back to the file-based report script:

```bash
./scripts/summarize_run_logs.py --log-file ./logs/gateway.log
```

### Isolation guarantees

The current implementation isolates analytics from the core bot flow in these ways:

- request handling writes plain structured logs before any analytics import runs
- import is only triggered manually or by an external scheduler
- gateway analytics API failures do not affect chat endpoints
- frontend analytics page is a dedicated route and does not block the main workspace chat screens

### Database unavailable scenario

If the analytics database becomes unavailable:

- agent conversations still run because they do not depend on analytics reads or writes
- structured logs still exist in `logs/gateway.log`
- the scheduler can be disabled without changing agent behavior
- operators can restore analytics later by re-importing historical logs

## Recommended Operator Checklist

- verify `logs/gateway.log` is being written
- verify `.deer-flow` is on persistent storage
- verify scheduler cadence and log rotation policy
- verify `/api/analytics/summary` returns data after import
- verify `/workspace/analytics` shows recent jobs and alerts
- verify the scheduler can be disabled independently during incidents
