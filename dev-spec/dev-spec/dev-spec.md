# Developer Specification (DEV_SPEC)

> 版本：2.0 — Coach Runtime 重构

## 目录

- 项目概述
- 核心特点
- 技术选型
- 测试方案
- 系统架构与模块设计
- 项目排期
- 可扩展性与未来展望

***

## 1. 项目概述

### 1.1 项目定位

本项目是基于 DeerFlow 进行垂直化改造的 **Badminton Coach Agent**。Phase 1 已完成基于 `lead_agent` 的低侵入式定制，Phase 2 的目标是把系统从“挂在通用 lead runtime 上的教练 agent”升级为“拥有独立 runtime 入口、独立 intake 层和独立路由策略的 coach runtime”。

本阶段不追求功能扩张，而追求架构收敛。重点是让系统在真实飞书文本对话里具备更稳定的：

- 意图识别能力
- 复合意图处理能力
- 追问一致性
- 领域状态可控性
- persona 可配置性

### 1.2 项目目标

本阶段有三层目标。

**产品目标**

- 让用户在飞书里获得更稳定、更连续的赛前、赛后与恢复建议
- 支持用户按 task/session 配置教练人格、表达风格和提问习惯
- 减少无意义追问，提高混合意图场景下的回答稳定性

**工程目标**

- 将 LangGraph 业务入口切换为 `make_coach_agent()`
- 建立 `CoachIntakeMiddleware + 意图识别 + 组合路由` 的主执行链
- 固化结构化 memory 分层与 route-specific writeback
- 保留并增强 structured logs 与离线评测能力，使性能和质量可追踪

**学习 / 面试目标**

- 能清楚说明 DeerFlow 原设计与本项目改造点的关系
- 能解释 middleware 取舍、memory 分层、runtime 入口替换的原因与风险
- 能展示从通用 agent runtime 向垂类 runtime 收敛的工程化思路

### 1.3 目标用户与使用场景

#### 1.3.1 目标用户

- 主用户：你本人，程序员背景、久坐、高压工作环境、羽毛球爱好者
- 次用户：与主用户画像相近的试用者

#### 1.3.2 典型使用场景

| 场景 | 用户输入 | Agent 输出 |
| ---- | ---- | ---- |
| 赛前咨询 | “今晚打球注意什么？” | 训练重点、热身建议、风险提醒 |
| 赛后复盘 | “今天后场步法还是慢，反手有进步” | 结构化复盘、下次训练重点、状态更新 |
| 恢复建议 | “今天肩膀有点酸，明天强度要不要降？” | 恢复建议、强度建议、风险边界 |
| 复合意图 | “今晚打球前怎么热身？昨天肩膀也有点酸。” | 先恢复判断，再给赛前建议 |
| 风格配置 | 通过飞书 task 设置 strict/supportive 等 persona | 影响表达、提问、组织方式 |

### 1.4 MVP 范围

#### 1.4.1 本期必须完成

- 新建 `make_coach_agent()` 并作为正式业务入口
- 移除 `lead_agent` 作为当前 coach 主入口的依赖
- 新增 `CoachIntakeMiddleware`
- 实现“意图识别、槽位抽取与组合路由”的结构化输出
- 支持 `prematch`、`postmatch`、`health`、`fallback` 以及复合意图组合
- 保留并收敛 `memory.json`、`coach_profile.json`、`memory/reviews/*.md`
- 引入可配置 coach persona，并支持 task/session 覆盖
- 为 `safety gate` 预留接口

#### 1.4.2 本期建议完成

- Persona 配置文件化
- 混合意图评测样本补齐
- 入口切换与 middleware 重组后的回归测试
- 结构化日志汇总与离线评测报告模板更新

#### 1.4.3 本期不纳入 MVP

- 飞书图片 / 语音入站
- 主动提醒调度器
- 通用多 agent 平台兼容
- 深度医学安全系统
- 复杂 skill 自由编排

### 1.5 当前已知约束

- DeerFlow 原始架构以 `make_lead_agent(config)` 为单入口，当前项目要显式替换这一层
- 当前 coach 能力已分散存在于 `domain/coach/*`，但尚未成为 runtime 主链路
- 当前飞书入口以文本为主
- 仓库中 skills 与 auto-coder 工作流默认从 `dev-spec/` 目录解析 spec，并优先选择最新版本

### 1.6 关键假设

- 假设 A1：本阶段正式放弃通用 lead runtime 叙事，转向垂类 coach runtime
- 假设 A2：复合意图的结构化识别由 LLM 负责，执行顺序与边界由代码负责
- 假设 A3：Persona 只影响互动风格，不覆盖路由顺序和安全边界
- 假设 A4：`safety gate` 本阶段只做接口预留，不实现复杂风险规则

### 1.7 成功标准

#### 1.7.1 功能成功标准

- LangGraph 入口改为 `make_coach_agent()`
- `CoachIntakeMiddleware` 成为主追问决策层
- 复合意图输入能产出稳定结构化识别结果
- Persona 可通过默认配置和 task/session 覆盖生效
- `coach_profile.json` 仍由代码安全写回

#### 1.7.2 质量成功标准

- 主要文本链路回归通过率 >= 95%
- mixed intent 路由顺序准确率 >= 85%
- intake 误追问率低于 Phase 1
- 不出现 LLM 直接篡改 canonical state 的路径
- structured logs 可输出 latency / token / error / memory hit / route 信息
- 离线评测可输出 route、structure、actionability、grounding、safety 等维度结果

#### 1.7.3 评测与可观测性成功标准

- 可从 structured logs 统计赛前 / 赛后 / 恢复主链路的 P50 / P95 延迟
- 可从 structured logs 汇总平均 input / output / total tokens
- 可按 route 维度统计 error rate 与样本量
- 离线评测样本集覆盖 `prematch`、`postmatch`、`health` 与至少一种 mixed intent
- LLM Judge 允许作为后续增强能力预留，但本期至少完成规则化离线评测与报告输出

***

## 2. 核心特点

### 2.1 独立 Coach Runtime

Phase 2 的核心变化是：DeerFlow 继续作为 harness 保留，但 `lead_agent` 不再作为本项目的正式 coach 业务入口。系统改为直接进入 `make_coach_agent()`，由 coach runtime 自己装配 prompt、middlewares、tool policy 与 domain routing。

### 2.2 意图识别、槽位抽取与组合路由

路由不再主要依赖 skill prompt，而改为先输出结构化识别结果，再由代码决定执行顺序。意图识别采用四层结构：

1. **规则强约束层**：处理高确定性 override，例如明显健康风险词。
2. **LLM 结构化分类层**：输出 intent schema，而不是自由文本判断。
3. **代码归一化 / guard 层**：校验字段、补默认值、保护安全边界。
4. **澄清层**：低置信度或缺失信息过多时，不强行路由，优先追问。

向量检索不作为主路由判定器，而作为后续 grounding / case recall 的辅助召回能力。

结构化输出至少包含：

- `primary_intent`
- `secondary_intents`
- `slots`
- `missing_slots`
- `risk_level`
- `confidence`
- `needs_clarification`

### 2.3 统一 Intake 层

所有请求在进入业务链之前，必须先经过 `CoachIntakeMiddleware`。该层统一负责：

- 输入规范化
- 线程上下文补齐
- memory / profile / review log 汇总
- persona 加载
- 缺失信息判断
- 追问决策

### 2.4 Persona Pack

Coach 不再只依赖 SOUL 或 prompt 描述，而要具备结构化 persona 能力。该能力用于定义：

- 教练角色定位
- 语言风格
- 严格度
- 提问习惯
- 建议组织方式

支持默认 persona 与来自飞书 task 的 session override。

### 2.5 Memory 分层

- `memory.json`：叙事型长期背景
- `coach_profile.json`：稳定结构化状态
- `memory/reviews/YYYY-MM-DD.md`：事件证据日志

其中 `coach_profile.json` 是 canonical state。LLM 不直接改 profile，只先产出结构化 observation，再由代码 merge。

### 2.6 Safety Gate 接口预留

本阶段仅预留：

- `risk_level` 字段
- 组合路由中的 safety hook
- `health` 与 `health + prematch` 场景的未来扩展位

暂不实现完整安全规则系统。

### 2.7 评测与可观测性

本项目除了要“能工作”，还要“能评估自己是否变好”。Phase 2 保留并增强两类能力：

- **Structured Logs**：面向真实运行链路，记录 latency、token、route、memory hit、error
- **Offline Evaluation**：面向固定样本集，评估 route、structure、actionability、grounding、safety

补充：当前 structured logs 也记录 clarification 决策信号，包括是否触发追问、触发原因、缺失槽位与实际追问文案，便于后续统计 intake 误追问率与追问命中原因。

这两类能力共同构成可解释的证据链：

- structured logs 回答“系统在线上跑得怎么样”
- offline evaluation 回答“改动之后质量有没有变好”

***

## 3. 技术选型

### 3.1 Runtime 入口

- LangGraph 入口：`make_coach_agent()`
- DeerFlow：继续作为 harness / runtime 基础设施
- 不再以 `make_lead_agent()` 为当前项目正式业务入口

### 3.2 Middleware 取舍

#### 3.2.1 保留

- `ThreadDataMiddleware`
- `UploadsMiddleware`
- `SandboxMiddleware`
- `SummarizationMiddleware`
- `MemoryMiddleware`
- `ViewImageMiddleware`
- `ToolErrorHandlingMiddleware`

#### 3.2.2 兼容保留

- `ClarificationMiddleware`

说明：暂时不删除，但不再负责主追问策略，只作为兼容与中断承载层。

#### 3.2.3 删除

- `TodoMiddleware`
- `SubagentLimitMiddleware`
- lead prompt 里的 subagent / plan mode 泛化语义

#### 3.2.4 新增

- `CoachIntakeMiddleware`
- `CoachPersonaMiddleware`（可选；当前实现采用 intake + response renderer，不单独拆 middleware）

### 3.3 路由实现原则

- LLM 负责结构化识别
- 代码负责执行顺序与边界控制
- 强规则场景优先使用代码而不是 prompt 技巧
- 向量检索只作为辅助召回，不直接替代 intent classifier

### 3.4 Persona 配置来源

建议引入两层：

- 默认 persona 配置文件
- session / task override

优先级约定：

- `default persona < session override < task override`
- 运行时上下文优先使用 `persona_overrides.session` 与 `persona_overrides.task`
- 为兼容不同接入层，也允许 `session_persona` 与 `task_persona` 作为别名

建议字段：

- `tone`
- `strictness`
- `verbosity`
- `questioning_style`
- `encouragement_style`

### 3.5 风险与迁移取舍

- 入口替换会增加与上游 DeerFlow 的偏离
- 现有测试、脚本、配置可能默认假设 `lead_agent`
- 但这样可以让架构叙事更干净，避免继续在 lead runtime 上叠 prompt/skill

### 3.6 评测与日志能力复用

当前仓库已存在可复用基础：

- `backend/app/channels/structured_logging.py`
- `backend/packages/harness/deerflow/evaluation/run_log_report.py`
- `backend/packages/harness/deerflow/evaluation/coach_eval.py`
- `scripts/summarize_run_logs.py`
- `scripts/evaluate_coach.py`

Phase 2 不从零重写评测体系，而是在 runtime 重构后继续保持这些能力可用，并补足 mixed intent、persona 和新入口相关指标。

***

## 4. 测试方案

### 4.1 设计理念：测试驱动开发 (TDD)

本项目继续采用 TDD 作为核心开发范式。Phase 2 的测试重点不是功能堆叠，而是保证 runtime 重构后行为稳定、边界清晰、可回归。

### 4.2 测试分层策略

#### 4.2.1 单元测试 (Unit Tests)

目标：

- `CoachIntakeMiddleware` 的上下文汇总逻辑
- 意图识别输出结构
- 组合路由顺序决策
- Persona 注入和 merge 规则
- profile 写回逻辑

#### 4.2.2 集成测试 (Integration Tests)

目标：

- `make_coach_agent()` 装配链路
- 飞书文本请求进入 coach runtime
- 复合意图完整处理链
- 入口替换后关键路径不回退

#### 4.2.3 端到端测试 (End-to-End Tests)

目标：

- 赛前咨询闭环
- 赛后复盘闭环
- `health + prematch` 复合意图闭环
- Persona 覆盖在真实请求中的表现

### 4.3 核心测试场景

- 入口从 `lead_agent` 切换到 `make_coach_agent()`
- `CoachIntakeMiddleware` 缺信息时正确追问
- 已有上下文足够时不多问
- `prematch/postmatch/health/fallback` 单意图正常
- `health + prematch`、`postmatch + health`、`prematch + postmatch` 组合顺序正确
- `coach_profile.json` 只经代码 merge 更新
- `risk_level` 能进入结构化识别结果
- structured logs 在新入口下仍能正确记录 route / latency / token / memory hit / error
- 离线评测在新入口和 mixed intent 场景下仍可产出维度化报告

### 4.4 评测维度

#### 4.4.1 Structured Logs 指标

- `latency_ms`
- `token_usage.input_tokens`
- `token_usage.output_tokens`
- `token_usage.total_tokens`
- `route.agent_name / assistant_id`
- `memory_hits`
- `error / error_type`

#### 4.4.2 Offline Evaluation 维度

- `route`
- `structure`
- `actionability`
- `grounding`
- `safety`

#### 4.4.3 后续可扩展维度

- `mixed_intent_ordering`
- `clarification_quality`
- `persona_consistency`
- `writeback_correctness`

#### 4.4.4 LLM Judge 策略

本阶段不要求完整接入真实 LLM Judge 执行链，但需要保留 judge prompt 与评分接口，保证后续可扩展为固定样本集 + 固定 rubric + 模型评分 + 人工抽检复核。

### 4.5 测试工具链与 CI/CD 集成

- 优先跑最小相关 pytest 集合
- 回归测试聚焦 coach runtime、domain/coach、middleware、channels
- 若入口文件或 langgraph 配置变更，增加一次入口级冒烟测试
- 日志汇总脚本与离线评测脚本应可独立运行并产出 Markdown 报告

***

## 5. 系统架构与模块设计

### 5.1 整体架构图

```
Feishu / Web Request
        |
        v
 make_coach_agent()
        |
        v
Base Runtime Middlewares
        |
        v
CoachIntakeMiddleware
        |
        v
Intent Recognition Result
        |
        v
Composable Coach Router
        |
        +--> prematch chain
        +--> postmatch chain
        +--> health chain
        +--> fallback chain
        |
        v
Route-specific writeback
```

### 5.2 目录结构

Phase 2 预期重点落在以下区域：

- `backend/packages/harness/deerflow/agents/`
- `backend/packages/harness/deerflow/agents/middlewares/`
- `backend/packages/harness/deerflow/domain/coach/`
- `backend/langgraph.json`
- `backend/tests/`

### 5.3 模块说明

#### 5.3.1 `make_coach_agent()`

- 负责模型、工具、middleware、prompt、runtime state 的装配
- 替代当前项目里的 `lead_agent` 入口职责

#### 5.3.2 `CoachIntakeMiddleware`

- 统一规范化输入
- 拉取 thread context
- 汇总 memory/profile/reviews/persona
- 决定是否追问

#### 5.3.3 Intent Recognition

- 输出结构化识别对象
- 提供后续组合路由的统一契约

#### 5.3.4 Composable Router

- 根据 `primary_intent + secondary_intents + missing_slots + risk_level` 决定执行链
- 支持复合意图顺序控制

#### 5.3.5 Route-specific Writeback

- 赛后复盘更新 structured observation
- 由代码 merge 到 `coach_profile.json`
- review log 与 narrative memory 各自按职责更新

### 5.4 数据流说明

1. 用户输入进入 coach runtime
2. Intake 层收集上下文与 persona
3. 意图识别层输出结构化结果
4. 组合路由决定执行顺序
5. route chain 生成回答
6. structured logs 记录运行信息
7. 必要时执行 writeback

### 5.5 配置驱动设计

- persona 使用配置文件 + task/session override
- runtime 行为尽量通过 config 和 schema 驱动
- profile 写回和 intent schema 尽量显式定义，而不是散落在 prompt 中

### 5.6 扩展性设计要点

- `safety gate` 作为独立 hook 预留
- persona 未来可扩展为模板系统
- 复合意图路由可继续加入更细 domain chain
- 后续多模态扩展优先接在 intake 和 route 层，而不是直接堆 skill
- 评测体系可继续扩展 mixed intent、persona consistency 与 LLM Judge

## 6. 项目排期

> 排期原则：
>
> - 先完成 runtime 入口与 middleware 收敛，再做意图和 persona
> - 每一阶段都要有明确测试和可验证产出
> - 文档、实现、测试同步推进，避免只改 prompt 不改结构

### 阶段总览（大阶段 → 目的）

- 阶段 A：入口与中间件重构
- 阶段 B：意图识别与组合路由
- 阶段 C：Persona 与配置注入
- 阶段 D：测试、评测与文档收敛

***

### 📊 进度跟踪表 (Progress Tracking)

> 状态说明：`[ ]` 未开始 | `[~]` 进行中 | `[x]` 已完成

#### 阶段 A：入口与中间件重构

- [x] A1 新建 `make_coach_agent()` 并切换入口
- [x] A2 完成 middleware 裁剪与重组
- [x] A3 引入 `CoachIntakeMiddleware` 骨架

#### 阶段 B：意图识别与组合路由

- [x] B1 定义 intent schema
- [x] B2 实现单意图路由
- [x] B3 实现复合意图组合路由
- [x] B4 预留 `safety gate` 接口

#### 阶段 C：Persona 与状态写回

- [x] C1 定义 persona config schema
- [x] C2 支持 task/session override
- [x] C3 persona 接入 intake 层
- [x] C4 固化 route-specific writeback

#### 阶段 D：测试与文档收敛

- [x] D1 入口与 middleware 回归测试
- [x] D2 mixed intent 与 persona 测试
- [x] D3 可观测性与离线评测收敛
- [x] D4 文档与阶段总结

### 📈 总体进度

- 当前阶段：Phase 2 已完成，实现与文档已基本收敛

***

## 阶段 A：入口与中间件重构

### A1：切换 LangGraph 入口到 `make_coach_agent()`

### A2：保留基础 middleware，去掉通用编排中间件

### A3：新增 `CoachIntakeMiddleware` 骨架

## 阶段 B：意图识别与组合路由

### B1：定义结构化 intent schema

### B2：实现单意图路由

### B3：实现复合意图组合路由

### B4：预留 `safety gate` hook

## 阶段 C：Persona 与状态写回

### C1：定义 persona 配置结构

### C2：支持 task/session 覆盖

### C3：将 persona 纳入 intake

### C4：固化 route-specific writeback

## 阶段 D：测试与文档收敛

### D1：入口与 middleware 回归测试

### D2：mixed intent 与 persona 测试

### D3：可观测性与离线评测收敛

### D4：文档与阶段总结

### 实现对照补充

- Persona 当前通过 `CoachIntakeMiddleware` 完成注入，通过 `response_renderer.py` 落到表达层，而不是单独增加 `CoachPersonaMiddleware`
- run log 汇总脚本为 `scripts/summarize_run_logs.py`
- offline eval CLI 为 `scripts/run_coach_eval.py`
- 评测样本与报告位于 `docs/eval/`

## 7. 可扩展性与未来展望

### 7.1 Safety Gate 深化

后续可从接口预留升级到更细粒度风险分层与医疗边界规则。

### 7.2 Persona 模板化

未来可扩展为多模板 persona，例如严格型、鼓励型、恢复优先型。

### 7.3 多模态扩展

待 runtime 架构稳定后，可继续接飞书图片、语音与运动截图。

### 7.4 评测体系扩展

后续评测可扩展到：

- mixed intent 顺序正确率
- 追问质量
- persona 一致性
- safety gate 命中率
- writeback 正确率
- 真实 LLM Judge + 人工抽检复核
