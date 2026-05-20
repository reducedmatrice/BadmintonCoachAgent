# Coach Agent Tool Capabilities — Training Log, Body Metrics & Memory Sync

## Context

Coach domain（prematch / postmatch / health / check_memory）目前全部通过纯 Python 函数生成结构化数据，不调用任何外部工具。这导致：
- 赛前建议无法引用用户的历史训练数据
- 身体状态分析缺乏趋势对比
- 长期记忆系统无法自动捕获训练规律

本设计为 coach agent 增加工具能力：训练日志管理、身体数据趋势分析，并将有意义的训练规律自动同步到 memory facts。信息获取类工具（天气、搜索）作为后续迭代。

遵循现有 harness 设计理念：确定性调用 + LLM 可调用 BaseTool + degrade/fallback 降级。

## Architecture Overview

```
用户消息 → intent 检测 → router 路由
  ├─ prematch:  fetch recent_training_log + body_trend → render
  ├─ postmatch: extract review → write training_log → extract facts → render
  ├─ health:    analyze → write body_metric → fetch body_trend → extract facts → render
  ├─ check_memory: (不变)
  └─ fallback:  LLM 可选调用 query_training_log / get_body_metrics_trend BaseTool
```

三层架构：
1. **数据存储层** — coach_profile.json 新增 training_log[] 和 body_metrics[]
2. **工具层** — training_data.py 提供读取工具（degrade 模式）+ BaseTool 注册
3. **Memory 同步层** — 写入后规则提取 facts → 写入 memory.json

---

## Part 1: Data Storage Layer

### Schema

**coach_profile.json 新增字段：**

```json
{
  "training_log": [
    {
      "date": "2026-05-21",
      "start_time": "19:30",
      "duration_min": 90,
      "calories_kcal": 680,
      "session_type": "match",
      "match_format": "doubles",
      "summary": "双打3局，反手过渡失误多",
      "focus_areas": ["反手", "网前"],
      "improvements": ["发球质量有提升"],
      "issues": ["反手过渡出界3次"],
      "source": "postmatch"
    }
  ],
  "body_metrics": [
    {
      "date": "2026-05-21",
      "fatigue_level": "medium",
      "avg_heart_rate": 145,
      "max_heart_rate": 172,
      "training_load": 120,
      "recovery_hours": 18,
      "calories_kcal": 680,
      "duration_min": 90,
      "soreness": ["肩膀"],
      "source": "exercise_screenshot"
    }
  ]
}
```

> `body_metrics` 中 `calories_kcal` 和 `duration_min` 为可选字段（来源截图可能缺失），`soreness` 为可选字符串数组。

### 与现有 health_profile.recent_metrics 的关系

`health_profile.recent_metrics` 保留不变，继续由现有 `persist_health_observation` / `update_profile_from_exercise_record` 写入。新增的 `body_metrics` 是其**可查询的结构化视图**：
- `health_profile.recent_metrics` — 保留最近 10 条，仅供 health 路由内部使用
- `body_metrics` — 保留最近 200 条，供趋势分析工具和 BaseTool 查询

两处写入可以同步进行：现有写入逻辑不动，新增 `append_body_metric` 额外追加到 `body_metrics`。

### Source 枚举值

- `training_log.source`: `"postmatch"` | `"manual"` | `"prematch_goal"`
- `body_metrics.source`: `"exercise_screenshot"` | `"health_report"` | `"manual"`

### Write Functions (profile_store.py 扩展)

- `append_training_log(entry: dict, *, agent_name: str) -> Path`
  - 从 postmatch review 结果提取结构化数据，追加到 `training_log`
  - 保留最近 **200 条**，滚动删除最旧的
  - 原子写入（复用 `save_coach_profile`）

- `append_body_metric(entry: dict, *, agent_name: str) -> Path`
  - 从 health 分析/截图数据提取，追加到 `body_metrics`
  - 保留最近 **200 条**
  - 原子写入

### Degradation

- 写入失败 → 记日志，不阻断回复（和现有 postmatch 写入行为一致）
- 数据超限 → 滚动删除最旧条目

---

## Part 2: Data Retrieval Tool Layer

### 新建文件：`backend/packages/harness/deerflow/domain/coach/training_data.py`

遵循 `weather.py` 的 degrade 模式。

### Tool 1: `get_recent_training_log(n, session_type?)`

```python
@dataclass
class TrainingLogContext:
    entries: list[dict[str, Any]]
    total_count: int
    source: str = "coach_profile"
    degraded: bool = False
    degrade_reason: str = ""
```

- 从 `coach_profile.training_log` 读取最近 N 条
- 可选按 `session_type` 过滤
- 降级场景：profile 不存在、数组为空、数据格式异常 → `degraded=True`

### Tool 2: `get_body_metrics_trend(days)`

```python
@dataclass
class BodyMetricsContext:
    entries: list[dict[str, Any]]
    trend_summary: dict[str, Any]  # 心率均值变化、疲劳趋势、训练负荷变化
    source: str = "coach_profile"
    degraded: bool = False
    degrade_reason: str = ""
```

- 从 `coach_profile.body_metrics` 读取最近 N 天的数据
- 计算趋势摘要：心率均值、疲劳分布、训练负荷变化方向
- 降级场景：数据不足（<2 条）→ `degraded=True, degrade_reason="insufficient_data"`

### BaseTool 注册（给 LLM 调用）

- `query_training_log` — 接受自由格式 query，内部调用 `get_recent_training_log` + 文本匹配/统计
- `get_body_metrics_trend_tool` — 接受 `days`（默认 14）和可选 `metric` 参数

通过 `get_available_tools()` 的 tool list 注册，和现有 tool 注册机制一致。

---

## Part 3: Router Integration

### Prematch 路由

- 自动调用 `get_recent_training_log(5)` → payload 新增 `recent_training`
- 自动调用 `get_body_metrics_trend(7)` → payload 新增 `body_trend`
- `degraded=True` → payload 标记 `recent_training_degraded: true`，渲染层 fallback 为通用建议

### Postmatch 路由

- 复盘提取完成后，从 `PostmatchReview` 构造训练日志条目
- 调用 `append_training_log()` 写入
- payload 新增 `training_log_persisted: bool`

### Health 路由

- 健康分析完成后，从 `HealthRecoveryAdvice` + `HealthImageObservation` 构造身体指标条目
- 调用 `append_body_metric()` 写入
- 调用 `get_body_metrics_trend(14)` → payload 新增 `body_trend`
- 降级处理同上

### Fallback 路由

- 不自动注入数据
- LLM 通过 BaseTool 自行查询

---

## Part 4: Memory Facts Sync

### 触发时机

- `append_training_log()` 成功后 → `extract_training_facts()`
- `append_body_metric()` 成功后 → `extract_body_facts()`

### 提取规则（纯 Python，零 LLM 调用）

| 触发条件 | Fact 内容 | category | confidence |
|---|---|---|---|
| 连续 3 次 `focus_areas` 含同一主题 | "近期反复训练XX" | behavior | 0.85 |
| 连续 3 次 `issues` 含同一问题 | "XX问题近期持续存在" | knowledge | 0.80 |
| 连续 2 次 `improvements` 含同一主题 | "XX方面有持续进步" | knowledge | 0.75 |
| body_metrics 连续 3 条 `fatigue_level=high` | "近期身体疲劳度偏高，需注意恢复" | context | 0.90 |
| `avg_heart_rate` 连续上升趋势 | "近期训练强度有上升趋势" | context | 0.80 |
| `calories_kcal` 单次 >800 | "单次训练消耗较大（XXkcal）" | behavior | 0.70 |

### 写入方式

- 复用现有 memory fact 结构：`{id, content, category, confidence, createdAt, source}`
- `source` 标记为 `"training_log"` 或 `"body_metrics"`
- 去重：同 category + 相似 content 不重复写入，只更新 `createdAt`
- 上限：和现有 `max_facts=100` 共享容量

### Degradation

- 提取失败 → 记日志，不影响训练日志写入
- memory.json 不可用 → 跳过，下次再试

---

## Files to Modify/Create

| File | Action |
|---|---|
| `backend/packages/harness/deerflow/domain/coach/training_data.py` | **新建** — 读取工具 + context dataclass |
| `backend/packages/harness/deerflow/domain/coach/profile_store.py` | **修改** — 新增 append_training_log, append_body_metric, extract_training_facts, extract_body_facts |
| `backend/packages/harness/deerflow/domain/coach/router.py` | **修改** — prematch/health 路由注入数据，postmatch/health 路由写入数据 |
| `backend/packages/harness/deerflow/domain/coach/response_renderer.py` | **修改** — 渲染层处理 degraded 状态 |
| `backend/packages/harness/deerflow/tools/tools.py` | **修改** — 注册新的 BaseTool |
| `backend/tests/test_training_data.py` | **新建** — 工具层单测 |
| `backend/tests/test_coach_memory_facts.py` | **新建** — facts 提取规则单测 |

## Non-Goals (本次不做)

- 外部数据源集成（手环 API、日历同步）
- LLM 提取 memory facts — 本轮只做规则提取
- 前端训练日志可视化
- 信息获取类工具（天气查询、运动医学搜索）— 下一轮迭代
