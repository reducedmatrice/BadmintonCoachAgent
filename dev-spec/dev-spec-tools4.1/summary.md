# Coach Agent Tool Capabilities — Implementation Summary

## 我们做了什么

为 badminton coach agent 增加了三层能力：结构化数据存储、趋势分析工具、自动记忆同步。

### 1. 数据存储层

在 `coach_profile.json` 中新增两个数组字段：

- **`training_log[]`** — 训练日志，每次 postmatch 复盘后自动写入，包含日期、时长、卡路里、训练类型、重点、改进点、问题点
- **`body_metrics[]`** — 身体指标，每次 health 分析后自动写入，包含心率、训练负荷、疲劳度、恢复时间、酸痛部位

两个数组各保留最近 **200 条**，滚动淘汰最旧数据。

### 2. 数据检索工具层

新建 `training_data.py`，提供两个读取工具：

- **`get_recent_training_log(n, session_type?)`** — 返回最近 N 条训练记录，可按类型过滤
- **`get_body_metrics_trend(days)`** — 返回最近 N 天的身体指标 + 自动计算趋势摘要（心率变化方向、训练负荷趋势、高疲劳占比）

两个工具都遵循 `weather.py` 的降级模式：数据不足时返回 `degraded=True` + 原因字符串，渲染层据此降级为通用建议，不会报错中断。

同时注册了两个 **LLM 可调用的 BaseTool**（`query_training_log`、`get_body_metrics_trend`），fallback 路由下 LLM 可以自行查询训练数据。

### 3. 路由层集成

| 路由 | 行为 |
|------|------|
| **prematch** | 自动拉取最近训练记录 + 身体趋势，注入 payload，赛前建议可以引用历史数据 |
| **postmatch** | 复盘提取完成后，自动将结构化数据写入 `training_log` |
| **health** | 健康分析完成后，自动将身体指标写入 `body_metrics`，同时拉取趋势数据 |
| **fallback** | 不自动注入，LLM 通过 BaseTool 自行查询 |

### 4. 记忆事实自动同步

纯规则提取（零 LLM 调用），写入后自动触发：

| 触发条件 | 生成的 fact |
|----------|------------|
| 连续 3 次 `focus_areas` 含同一主题 | "近期反复训练XX" |
| 连续 3 次 `issues` 含同一问题 | "XX问题近期持续存在" |
| 连续 2 次 `improvements` 含同一主题 | "XX方面有持续进步" |
| 连续 3 条 `fatigue_level=high` | "近期身体疲劳度偏高，需注意恢复" |
| `avg_heart_rate` 连续上升趋势 | "近期训练强度有上升趋势" |
| `calories_kcal` 单次 >800 | "单次训练消耗较大（XXkcal）" |

Fact 写入 `memory.json`，同 category + 相似 content 自动去重。

### 5. 日志可观测性

Coach 域此前零日志。本次为所有新增模块补齐 `logging.getLogger(__name__)`：
- 数据读取成功/降级 → INFO / WARNING
- 数据写入成功/失败 → INFO / ERROR（含 traceback）
- Fact 提取命中/跳过 → INFO / WARNING
- 路由数据注入 → INFO

---

## 为什么这么做

### 问题

Coach agent 的所有回复都是一次性的——赛前建议无法引用用户的历史训练数据，身体状态分析缺乏趋势对比，长期记忆系统无法自动捕获训练规律。用户每次对话都是从零开始。

### 设计决策

**1. 数据存在 `coach_profile.json` 而非独立数据库**

Coach profile 已经是用户状态的单一数据源（运动员档案、技术档案、健康档案、偏好设置），训练日志和身体指标本质上是同一类数据的延伸。复用现有存储避免引入新依赖，原子写入机制（temp + rename）保证数据完整性。

**2. 降级而非报错**

Agent harness 的核心理念：外部数据不可用时应该优雅降级，而非中断对话。所有数据检索工具返回 `degraded` 标记，渲染层据此降级为通用建议。用户感知到的是"建议可能不够个性化"，而非"系统报错了"。

**3. 规则提取而非 LLM 提取**

Memory fact 同步用纯规则实现，原因：
- **零延迟** — 不需要额外的 LLM 调用
- **零成本** — 不消耗 token
- **确定性** — 相同输入一定产生相同输出，可测试、可预测
- **够用** — 训练数据已经是结构化的，规则足以捕获有意义的规律

**4. BaseTool 给 fallback 路由**

prematch/postmatch/health 路由自动注入数据（确定性调用），但 fallback 路由不注入。此时 LLM 可以通过 `query_training_log` / `get_body_metrics_trend` 两个 BaseTool 自行查询。这是"路由层确定性 + LLM 层灵活性"的混合模式，兼顾效率和能力。

**5. 200 条上限**

平衡存储开销和分析需求。200 条约等于半年的训练数据（假设每周 3-4 次），足够做趋势分析，不会造成文件膨胀。超出时滚动删除最旧条目。

---

## 技术细节

### 新增文件

| 文件 | 职责 |
|------|------|
| `domain/coach/training_data.py` | 数据读取工具 + context dataclass |
| `tools/builtins/training_tools.py` | LLM 可调用的 BaseTool 封装 |
| `tests/test_training_data.py` | 读取工具单测（7 个） |
| `tests/test_training_log_write.py` | 写入函数单测（4 个） |
| `tests/test_coach_memory_facts.py` | Fact 提取规则单测（8 个） |
| `tests/test_training_basetools.py` | BaseTool 调用单测（5 个） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `domain/coach/profile_store.py` | 新增 `append_training_log`、`append_body_metric`、`extract_training_facts`、`extract_body_facts` + logger |
| `domain/coach/router.py` | prematch 注入训练数据、postmatch/health 写入数据 + logger |
| `domain/coach/response_renderer.py` | 渲染层处理 degraded 状态 + 训练上下文渲染 |
| `domain/coach/__init__.py` | 新增导出 |
| `tools/tools.py` | 注册新 BaseTool |
| `tests/test_coach_single_intent_router.py` | 路由集成测试（4 个新测试） |

### 测试覆盖

37 个测试全部通过，覆盖：
- 正常读取、过滤、降级场景
- 写入 + 200 条上限滚动
- 6 种 fact 提取规则
- BaseTool 正常调用 + 降级返回
- 路由层数据注入 + 持久化
