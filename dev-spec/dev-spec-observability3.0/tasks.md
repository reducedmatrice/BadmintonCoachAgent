# Coach Observability 3.0 Tasks

本文件从 [dev-spec-observability3.0.md](./dev-spec-observability3.0.md) 映射而来，按阶段拆分实现任务。

## Phase 1：成本拆账口径定义

- 状态：待开始
- 目标：把单次 coach 请求拆成 `router / memory-context / final generation` 三类成本
- 输入：现有 structured logs、analytics 字段、coach 请求链路
- 输出：成本拆账字段定义、字段来源说明、缺失字段降级策略
- 依赖：无
- 并行项：可与 Phase 2 的 route 指标定义并行
- 阻塞项：若现有日志缺字段，需要明确补字段还是近似估算
- 完成定义（DoD）：
  - 明确 `router_tokens / memory_context_tokens / generation_tokens / total_tokens`
  - 能解释各字段的来源或近似口径
  - 缺失字段不会静默失败
  - 结果可输出为 JSON 或 Markdown
  - 明确说明哪些字段当前已有，哪些字段当前缺失

## Phase 2：route 维度聚合

- 状态：待开始
- 目标：按 `prematch / postmatch / health / fallback` 输出核心统计
- 输入：structured logs、route 字段、latency 和 token 字段
- 输出：route 维度聚合结果
- 依赖：Phase 1 建议完成，但不是硬阻塞
- 并行项：可与 Phase 3 的测试样本准备并行
- 阻塞项：route 字段若存在历史兼容格式，需要统一归一化
- 完成定义（DoD）：
  - 至少输出 `request_count / avg_latency_ms / p95_latency_ms / avg_total_tokens / fallback_rate`
  - 能区分四条 coach 主 route
  - 结果可被人工复核
  - 如果现有 route 字段不足，必须补归一化方案

## Phase 3：500 条 golden dataset 构建

- 状态：待开始
- 目标：构建一份覆盖核心 coach 场景的 500 条评测集
- 输入：现有 `memory/*.md`、`docs/eval/coach_eval_cases.json`、gateway / structured logs、人工构造边界样本
- 输出：golden dataset 文件、分类方案、来源标记规则
- 依赖：无
- 并行项：可与 Phase 1-2 并行
- 阻塞项：若真实样本不足，需要定义可接受的扩写比例
- 完成定义（DoD）：
  - 总样本数达到 500 条
  - 至少覆盖 `multi_turn / mixed_intent / health / safety / fallback`
  - 每条样本都带来源标记
  - 不允许 500 条全部是纯合成数据
  - 至少给出各类场景样本数配比
## Phase 4：测试与结果沉淀

- 状态：待开始
- 目标：让统计逻辑可复现、可回归、可用于面试表达
- 输入：真实或半真实日志样本、现有 analytics 测试框架
- 输出：单元测试、集成测试、统计结果样例
- 依赖：Phase 1-3
- 并行项：无
- 阻塞项：无
- 完成定义（DoD）：
  - 至少有 1 组成本拆账测试
  - 至少有 1 组 route 聚合测试
  - 至少有 1 组 golden dataset schema / 分类测试
  - 至少产出 1 份统计结果
  - 至少沉淀 3 条可以直接复述的结论
