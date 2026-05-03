# Developer Specification (DEV_SPEC)

> 版本：3.0 — Coach 可观测性与成本拆账

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

本阶段目标不是继续给 `Badminton Coach Agent` 增加新功能，而是把现有链路补成一个可以被解释、被量化、被诊断的工程系统。

当前项目已经具备：

- coach 路由能力
- 多层记忆能力
- structured logs 基础
- analytics 统计能力
- 离线评测与测试资产

但在面试和工程复盘里，还缺三类关键证据：

- 单次请求到底贵在哪
- 哪条 route 最慢、最贵、最容易 fallback
- 现有日志是否足够支撑定位问题

因此本阶段聚焦三件事：

1. 成本拆账：把一次请求拆成 `router / memory-context / final generation` 三类成本
2. route 维度统计：按 `prematch / postmatch / health / fallback` 统计请求数、延迟、token 和 fallback
3. golden dataset：构建 500 条可复用的 coach 评测集，覆盖多轮承接、跨场景混合、健康恢复和安全边界场景

### 1.2 项目目标

本阶段有三层目标。

**工程目标**

- 明确一次 coach 请求的最小成本结构
- 产出 route 维度的性能统计视图
- 让 structured logs 足以支撑“为什么慢、为什么贵、为什么 fallback”
- 产出一份 500 条的 golden dataset，供路由、memory、fallback、安全和连续对话评测复用

**诊断目标**

- 能识别 token 大头来自 router、memory 注入还是最终生成
- 能识别哪条 route 的 P95 latency 最高
- 能识别 fallback 主要集中在哪些 route
- 能区分“连续追问承接失败”“跨场景误路由”“健康恢复误判”“高风险边界收口失败”等典型 case

**面试目标**

- 能稳定回答“你怎么做可观测和成本分析”
- 能用指标而不是感觉描述系统瓶颈
- 能把项目讲成一个被量化分析过的 Agent case study

### 1.3 目标用户与使用场景

#### 1.3.1 目标用户

- 主用户：当前项目维护者本人
- 次用户：未来阅读项目、评估项目成熟度的面试官 / 团队同事

#### 1.3.2 典型使用场景

| 场景 | 输入 | 输出 |
| ---- | ---- | ---- |
| 成本复盘 | 一段真实 gateway / structured logs | 拆出 router、memory、final generation 的 token 占比 |
| route 统计 | 一批 coach 请求日志 | 输出各 route 的请求数、平均 latency、P95、平均 token、fallback 率 |
| 面试表达 | “你怎么做可观测和成本控制？” | 给出可量化指标、字段和优化方向 |
| 评测建设 | 现有 memory log / eval case / gateway log | 产出可持续扩展的 500 条 golden dataset |

### 1.4 MVP 范围

#### 1.4.1 本期必须完成

- 明确 coach 请求的成本拆账口径
- 支持 route 维度的统计聚合
- 至少能输出 `request_count / avg_latency / p95_latency / avg_total_tokens / fallback_rate`
- 至少能识别 `router_tokens / memory_context_tokens / generation_tokens`
- 产出一份可复用的统计结果或报告
- 产出一份 500 条 coach golden dataset，并给出场景分类与构造来源

#### 1.4.2 本期建议完成

- 为 fallback 增加原因分类字段
- 为 memory 注入增加长度或命中字段
- 为单次请求保留阶段级 token 明细
- 为 golden dataset 增加来源标签、场景标签和风险标签

#### 1.4.3 本期不纳入 MVP

- 新功能开发
- 大规模 dashboard 重构
- 外接 Langfuse / Phoenix 平台级接入
- 复杂告警系统
- 自动优化闭环

### 1.5 当前已知约束

- 当前 structured logs 已存在，但阶段级成本字段不一定完整
- analytics 已具备部分统计能力，但未必满足 route + 成本拆账视角
- 当前 run log 仅稳定记录 `latency_ms`、总 token、memory_hits、clarification、multimodal 状态，不等于已经具备阶段级成本拆账
- 当前 `route` 字段主要是 `assistant_id / agent_name`，不等于已经具备 `prematch / postmatch / health / fallback` 这类 coach 语义 route
- 当前没有现成的 500 条 golden dataset，需要从现有 memory log、eval case、gateway log 和人工补边界样本共同构建
- 1 天多时间不足以重做整套 observability 体系
- 本阶段必须优先选择“最小但可讲清楚”的方案

### 1.6 关键假设

- 假设 A1：现有日志链路足以支撑最小可用统计，不需要新引入外部平台
- 假设 A2：成本拆账优先按逻辑阶段口径做，不追求绝对精确到每个 token 来源
- 假设 A3：route 维度统计优先面向 coach 场景，不先泛化到整个 DeerFlow
- 假设 A4：fallback 的定义可先沿用当前 coach 路由 / 澄清链路已有约定
- 假设 A5：golden dataset 允许“真实样本 + 基于真实样本扩写 + 人工构造边界样本”混合组成，但必须保留来源标记

### 1.7 成功标准

#### 1.7.1 功能成功标准

- 能输出单次请求的三段式成本拆账
- 能输出 route 维度统计表
- 能区分 `prematch / postmatch / health / fallback`
- 能产出 500 条带标签的 golden dataset

#### 1.7.2 质量成功标准

- 统计字段来源清晰，不依赖人工猜测
- 计算逻辑可被测试覆盖
- 对缺失字段有明确降级处理
- golden dataset 的来源和分类清晰，不是纯大模型凭空造数据

#### 1.7.3 面试成功标准

- 能回答“token 主要花在哪”
- 能回答“最慢的是哪条 route”
- 能回答“fallback 集中在哪”
- 能回答“你的评测集怎么构建、覆盖了哪些场景、为什么这 500 条有代表性”

***

## 2. 核心特点

### 2.1 先做拆账，再谈优化

本阶段不直接优化 token 或 latency，而是先把成本结构看清楚。只有先知道贵在哪，优化才不是拍脑袋。

### 2.2 route 维度优先，而不是全局均值优先

全局平均值会掩盖不同业务链路的差异。本阶段优先按 route 统计，让性能和业务语义绑定。

### 2.3 面向 coach 场景的最小可观测闭环

本阶段不追求搭一套通用监控平台，而是优先满足 coach 项目的工程复盘和面试表达需要。

### 2.4 先补字段缺口，再做统计结论

经现状检查，当前日志链路里“已有”和“缺失”是分开的：

- 已有：`latency_ms`、`input_tokens / output_tokens / total_tokens`、`memory_hits`、`clarification`、`multimodal.status`
- 缺失或不充分：`router_tokens`、`memory_context_tokens`、`generation_tokens`、阶段级 latency、明确的 coach 语义 route、fallback reason、cache hit

因此本阶段不能假设“数据已经齐全”，而应先把字段缺口显式写出来，再决定是补字段、近似估算还是暂不支持。

### 2.5 成本拆账采用阶段口径

一次请求优先拆成：

- `router_cost`
- `memory_context_cost`
- `final_generation_cost`

这种拆法虽然比底层 token tracing 粗，但最符合当前项目规模和面试叙事。

### 2.6 golden dataset 以场景分类驱动，而不是只按 route 分类

这 500 条数据集不能只是“prematch 多少条、health 多少条”这么粗。为了真正服务评测和面试表达，至少要覆盖：

- 连续追问 / 多轮承接场景
- 跨场景混合问题
- 身体健康与恢复场景
- 安全 / 边界 / 高风险场景
- fallback / 澄清 / 模糊表达场景

建议的初始配比：

- 连续追问 / 多轮承接：150 条
- 跨场景混合问题：120 条
- 身体健康与恢复：100 条
- 安全 / 边界 / 高风险：80 条
- fallback / 澄清 / 模糊表达：50 条

来源建议：

- 现有 `memory/*.md` 与训练记录
- 现有 `docs/eval/coach_eval_cases.json`
- 现有 gateway / structured logs
- 基于真实样本扩写的近邻表达
- 人工构造的边界安全样本

### 2.7 缺失字段可降级，但不可沉默

如果日志里缺某个统计字段，本阶段允许用 `unknown`、`0` 或近似值降级，但必须显式标出字段缺失，而不是静默吞掉。

***

## 3. 技术选型

### 3.1 日志来源

- 主来源：现有 structured logs / analytics 导入链路
- 非目标：新接外部可观测平台

理由：

- 当前仓库已有 analytics 与日志处理基础
- 时间有限，优先复用已有资产

### 3.2 成本拆账口径

采用“阶段级口径”而不是“模型内部精细 tracing”。

理想字段：

- `router_tokens`
- `memory_context_tokens`
- `generation_tokens`
- `total_tokens`

现状检查结论：

- `total_tokens`：已有
- `input_tokens / output_tokens`：已有
- `router_tokens`：当前未稳定落日志
- `memory_context_tokens`：当前未稳定落日志
- `generation_tokens`：当前未稳定落日志

因此本阶段要先定义这些字段，再决定通过新增日志字段还是从现有结果近似推导。

理由：

- 便于面试表达
- 便于快速统计
- 对当前规模足够实用

### 3.3 route 统计口径

最小 MVP 统一输出：

- `request_count`
- `avg_latency_ms`
- `p95_latency_ms`
- `avg_total_tokens`
- `fallback_rate`

建议扩展字段：

- `avg_router_tokens`
- `avg_memory_context_tokens`
- `avg_generation_tokens`
- `error_rate`
- `fallback_reason_breakdown`
- `avg_multimodal_extraction_latency_ms`

现状检查结论：

- 当前 analytics 可稳定聚合 `latency`、`token`、`error`、基础 `route`
- 但当前 `route` 更接近 agent 标识，不足以直接代表 coach 业务 route
- 因此若要做 `prematch / postmatch / health / fallback` 统计，需要补 coach 语义 route 字段或增加归一化逻辑

### 3.4 golden dataset 数据结构

建议每条样本至少包含：

- `case_id`
- `source_type`：`memory_log / eval_case / gateway_log / synthetic_boundary`
- `scenario_type`：`multi_turn / mixed_intent / health / safety / fallback`
- `message` 或对话片段
- `expected_primary_route`
- `expected_secondary_routes`
- `expected_execution_order`
- `expected_fallback`
- `expected_safety_level`
- `expected_memory_use`
- `notes`

### 3.5 输出形式

- 开发期：Markdown 报告或 JSON 聚合结果
- 非目标：本阶段不强依赖前端 dashboard

理由：

- 先确保统计逻辑成立
- 先服务工程复盘和面试表达

***

## 4. 测试方案

### 4.1 单元测试

- 成本拆账字段计算正确
- route 维度聚合正确
- 缺失字段降级逻辑正确
- golden dataset schema 校验正确
- golden dataset 分类配比统计正确

### 4.2 集成测试

- 从一份真实或半真实日志样本中跑出统计结果
- route 分类结果与人工预期一致
- 从现有 memory log / eval case 生成一批 golden dataset 样本

### 4.3 回归测试

- 不影响现有 analytics 导入链路
- 不破坏原有 structured log 解析

### 4.4 验收方式

至少提供：

- 1 份 route 统计结果
- 1 份成本拆账结果
- 1 条可以直接复述的结论
- 1 份 500 条 golden dataset 清单或生成结果

***

## 5. 系统架构与模块设计

### 5.1 成本拆账层

负责把单次请求按阶段拆成可统计字段。

核心职责：

- 从现有日志中提取阶段级 token
- 在缺失时做显式降级
- 为后续聚合提供统一结构

### 5.2 route 聚合层

负责按 route 汇总：

- 请求数
- latency
- token
- fallback

### 5.3 golden dataset 构建层

负责把现有项目资产转成可评测样本。

核心职责：

- 从真实 memory log、eval cases、gateway log 中抽取 seed 样本
- 按场景分类组织样本
- 支持在真实 seed 基础上扩写近邻表达
- 为安全 / 边界场景补人工构造样本

### 5.4 报告层

负责把统计结果转换成可读的输出形式：

- Markdown
- JSON

### 5.5 与现有系统的边界

- 不重做 logger
- 不改 coach 核心业务逻辑
- 优先在 analytics / evaluation / report 层实现

***

## 6. 项目排期

### Phase 1：成本拆账口径定义

- 状态：待开始
- 目标：明确一次请求三段式成本结构

### Phase 2：route 维度聚合

- 状态：待开始
- 目标：输出 route 统计核心指标

### Phase 3：500 条 golden dataset 构建

- 状态：待开始
- 目标：构建一份覆盖多轮、混合场景、健康恢复和安全边界的评测集

### Phase 4：测试与结果沉淀

- 状态：待开始
- 目标：让统计结果可复现、可复述

***

## 7. 可扩展性与未来展望

- 后续可接 Langfuse / Phoenix 做更细 tracing
- 后续可增加 fallback reason 分类
- 后续可增加 memory hit / cache hit 统计
- 后续可把 markdown 报告升级为前端 dashboard
- 后续可把 golden dataset 接入自动回归和版本对比评测
