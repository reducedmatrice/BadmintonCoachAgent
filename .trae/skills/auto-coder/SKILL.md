***

name: auto-coder
description: Autonomous spec-driven development agent. Syncs the selected dev spec into chapter-based reference files, identifies the next pending task from the schedule, implements code following spec architecture and patterns, runs tests with up to 3 auto-fix rounds, and persists progress with small reviewable commits. Use when user says "auto code", "自动开发", "自动写代码", "auto dev", "一键开发", "autopilot", or wants fully automated spec-to-code workflow. Read specs from either the repository root `dev-spec*.md` files or the staged `dev-spec/` directory. If the user does not specify a spec file or version, default to the latest resolved spec across the supported layouts. If the user says a version or selector like "auto code 2.1 A1" or "auto code dev-spec-database2.1 A1", resolve the best matching spec first and then execute the task from the selected spec.
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Auto Coder

One trigger completes **read spec → find task → code → test → persist progress**.

Optional modifiers:
- append a task ID (e.g. `auto code B2`) to target a specific task in the latest resolved spec
- append a version selector plus task ID (e.g. `auto code 2.1 A1`) to target the matching versioned spec
- append an explicit spec selector plus task ID (e.g. `auto code dev-spec-database2.1 A1`)
- append `--no-commit` to skip git commit

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

Resolve the spec file from the user request before doing anything else.

Default behavior:

1. Read specs from the repository root `dev-spec*.md` files and from `dev-spec/` when that staged layout exists
2. If the user does not specify a version or spec selector, resolve the highest available version as the default active spec
3. If multiple minor versions are in progress in parallel, prefer the highest version number by default

Selector behavior:

1. If the user provides a version token such as `2.1`, resolve the matching stage folder whose spec version is `2.1`
2. If the user provides an explicit selector such as `dev-spec-database2.1`, resolve that exact or closest matching spec file or stage folder
3. After the spec file is resolved, read tasks from that spec's schedule section only

Examples:

- `auto code` → use the latest resolved spec across supported layouts (for example `dev-spec-memory2.2.md` or `dev-spec/dev-spec-memory2.2/dev-spec-memory2.2.md`)
- `auto code A1` → use the latest resolved spec, target task `A1`
- `auto code 2.1 A1` → use the spec file matching version `2.1`, then target task `A1`
- `auto code dev-spec-database2.1 A1` → use the best matching spec file, such as `dev-spec-database2.1.md` or `dev-spec/dev-spec-database2.1/dev-spec-database2.1.md`, then target task `A1`

Do not infer task state from archived specs unrelated to the resolved selector.

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
python3 .trae/skills/auto-coder/scripts/sync_spec.py [selector]
```

Where:

- omit `selector` when the user did not specify a version or file
- pass `2.1` for requests like `auto code 2.1 A1`
- pass `dev-spec-database2.1` for requests like `auto code dev-spec-database2.1 A1`

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

Pick the first `IN_PROGRESS` task, then the first `NOT_STARTED`. If user specified a task ID, use that directly inside the already resolved spec.

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
2. **Re-sync**: `python3 .trae/skills/auto-coder/scripts/sync_spec.py [selector] --force`
3. **Commit every completed task-sized increment**

For this repository, a task like `A1`, `A2`, `B1`, `B2` is the default commit boundary.

- If one task is completed and tested, create a commit immediately.
- Do not batch multiple completed tasks into one commit unless the user explicitly asks for a squash.
- `[doc]` tasks should also get their own commit after the paired documentation output is finished.

4. **Show summary & ask**:

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
- Prefer the resolved spec selected from the user request as the source of truth
- When the user says only `auto code`, default to the highest version across root-level `dev-spec*.md` files and `dev-spec/` staged specs
- When the user says a version like `2.1`, resolve the matching versioned spec before reading the schedule
- Treat stage-summary tasks (`A4/B4/C4/D4/E3`) and any task marked `[doc]` as documentation tasks to run only after the paired implementation tasks are complete
- Prefer the smallest meaningful commit, not arbitrary time-based slicing
- When a task modifies runtime assets under `backend/.deer-flow/`, make sure the corresponding versioned source or initialization logic is also updated if required by the spec
