# Coach Observability 3.0 Checklist

## Phase 1：成本拆账口径定义

- [ ] 已明确 `router_tokens`
- [ ] 已明确 `memory_context_tokens`
- [ ] 已明确 `generation_tokens`
- [ ] 已明确 `total_tokens`
- [ ] 已明确“现有已有字段”
- [ ] 已明确“当前缺失字段”
- [ ] 缺失字段存在显式降级策略
- [ ] 成本拆账结果可输出

## Phase 2：route 维度聚合

- [ ] 可区分 `prematch`
- [ ] 可区分 `postmatch`
- [ ] 可区分 `health`
- [ ] 可区分 `fallback`
- [ ] 已输出 `request_count`
- [ ] 已输出 `avg_latency_ms`
- [ ] 已输出 `p95_latency_ms`
- [ ] 已输出 `avg_total_tokens`
- [ ] 已输出 `fallback_rate`
- [ ] 已明确 coach 语义 route 的归一化方法

## Phase 3：500 条 golden dataset 构建

- [ ] 总样本数达到 500
- [ ] 存在 `multi_turn` 类样本
- [ ] 存在 `mixed_intent` 类样本
- [ ] 存在 `health` 类样本
- [ ] 存在 `safety` 类样本
- [ ] 存在 `fallback` 类样本
- [ ] 每条样本都有来源标记
- [ ] 不全是纯合成数据

## Phase 4：测试与结果沉淀

- [ ] 成本拆账存在测试覆盖
- [ ] route 聚合存在测试覆盖
- [ ] golden dataset 存在 schema / 分类测试覆盖
- [ ] 存在可复现的日志样本
- [ ] 已产出至少 1 份统计结果
- [ ] 已沉淀至少 3 条面试可复述结论
