***

name: auto-coder
description: Autonomous spec-driven development agent. Syncs the active dev spec into chapter-based reference files, identifies the next pending task from the schedule, implements code following spec architecture and patterns, runs tests with up to 3 auto-fix rounds, and persists progress with small reviewable commits. Use when user says "auto code", "自动开发", "自动写代码", "auto dev", "一键开发", "autopilot", or wants fully automated spec-to-code workflow.
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Auto Coder

One trigger completes **read spec → find task → code → test → persist progress**.

Optional modifiers: append a task ID (e.g. `auto code B2`) to target a specific task, or `--no-commit` to skip git commit.

***

## Pipeline

```
Sync Spec → Find Task → Implement → Test (≤3 fix rounds) → Persist
```

Pause only at the end for commit confirmation. Run everything else autonomously.

> **⚠️ CRITICAL: Activate** **`.venv`** **before ANY** **`python`/`pytest`** **command (idempotent, re-run if unsure).**
>
> - **Windows**: `.\.venv\Scripts\Activate.ps1`
> - **macOS/Linux**: `source .venv/bin/activate`

## Active Spec Resolution

The active spec file is fixed to `dev-spec-gpt5.4.md`.
Do not read or infer task state from `DEV_SPEC.md`, `dev_spec.md`, or `dev-spec-gpt.md`.

## Reference Map

All files under `.trae/skills/auto-coder/references/`:

| File                 | Content                      | When to Read                               |
| -------------------- | ---------------------------- | ------------------------------------------ |
| `01-overview.md`     | Project overview & goals     | First task or when needing project context |
| `02-features.md`     | Feature specifications       | When implementing feature-related tasks    |
| `03-tech-stack.md`   | Tech stack & dependencies    | When choosing libraries or patterns        |
| `04-testing.md`      | Testing conventions          | When writing tests                         |
| `05-architecture.md` | Architecture & module design | When creating/modifying modules            |
| `06-schedule.md`     | Task schedule & status       | Every cycle (Sync Spec step)               |
| `07-future.md`       | Future roadmap               | When planning or assessing scope           |

***

### 1. Sync Spec

```powershell
python3 .trae/skills/auto-coder/scripts/sync_spec.py
```

Then read the schedule file to get task statuses:

- Read `.trae/skills/auto-coder/references/06-schedule.md`

Task markers:

| Marker                 | Status      |
| ---------------------- | ----------- |
| `[ ]` / `⬜`            | Not started |
| `[~]` / `🔶` / `(进行中)` | In progress |
| `[x]` / `✅` / `(已完成)`  | Completed   |

***

### 2. Find Task

Pick the first `IN_PROGRESS` task, then the first `NOT_STARTED`. If user specified a task ID, use that directly.

Quick-check predecessor artifacts exist (file-level only). On mismatch, log a warning and continue — only stop if the target task itself is blocked.

### Task Granularity Rule

Do **not** force every task into a one-hour box.

Use this rule instead:
- One task = one **complete, reviewable, independently verifiable increment**
- Prefer smaller diffs, but do not split a coherent change into artificial fragments
- If a spec item is too large, split it into child tasks before coding
- If a spec item is already atomic and coherent, implement it as one task even if it slightly exceeds one hour

For this repository, tasks marked as `[doc]` and tasks like `A4/B4/C4/D4/E3` are documentation/summarization tasks, not code tasks.

Task selection priority for this repository:
1. Explicit task ID from user
2. `IN_PROGRESS` implementation task
3. `NOT_STARTED` implementation task
4. `IN_PROGRESS` `[doc]` task
5. `NOT_STARTED` `[doc]` task

Do not pick a `[doc]` task before its prerequisite implementation tasks are done unless the user explicitly asks for documentation output first.

***

### 3. Implement

1. **Read relevant spec** from `.trae/skills/auto-coder/references/`:
   - Architecture: `05-architecture.md`
   - Tech details: `03-tech-stack.md`
   - Testing conventions: `04-testing.md`
2. **Extract** from spec: inputs/outputs, design principles (Pluggable? Config-driven? Factory?), file list, acceptance criteria.
3. **Plan** files to create/modify before writing any code.
4. **Code** — project-specific rules:
   - Treat spec as single source of truth
   - Use `config/settings.yaml` values, never hardcode
   - Match existing codebase patterns and style
5. **Write tests** alongside code:
   - Place in `tests/unit/` or `tests/integration/` per spec
   - Mock external deps in unit tests
6. **Self-review** before running tests: verify all planned files exist and tests import correctly.

***

### 4. Test & Auto-Fix

```

Round 0..2:
  Run pytest on relevant test file
  If pass → go to step 5
  If fail → analyze error, apply fix, re-run

Round 3 still failing → STOP, show failure report to user
```

***

### 5. Persist

1. **Update active dev spec**: change task marker `[ ]` → `[x]` in the resolved spec file
2. **Re-sync**: `python3 .trae/skills/auto-coder/scripts/sync_spec.py --force`
3. **Show summary & ask**:

```
✅ [A3] 配置加载与校验 — done
   Files: src/core/settings.py, tests/unit/test_settings.py
   Tests: 8/8 passed
   Commit: feat(config): [A3] implement config loader

   "commit" → git add + commit
   "skip"   → end
   "next"   → commit + start next task
```

On "next", loop back to step 1 and start the next task.

## Repository-Specific Notes

For this repository:
- Prefer the schedule in `dev-spec-gpt5.4.md` as the source of truth
- Treat stage-summary tasks (`A4/B4/C4/D4/E3`) and any task marked `[doc]` as documentation tasks to run only after the paired implementation tasks are complete
- Prefer the smallest meaningful commit, not arbitrary time-based slicing
- When a task modifies runtime assets under `backend/.deer-flow/`, make sure the corresponding versioned source or initialization logic is also updated if required by the spec
