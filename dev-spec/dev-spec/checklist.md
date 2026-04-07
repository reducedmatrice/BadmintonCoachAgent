# Phase 2 Checklist

## 需求与范围

- [x] 当前目标明确为 Phase 2 runtime 重构，而不是继续修补 Phase 1 prompt/skill
- [x] 当前 spec 已明确本期必须完成、建议完成和非目标
- [x] `safety gate` 仅作为接口预留，未被误写成完整风险系统
- [x] Persona 功能边界已明确，只影响风格与互动习惯

## 架构与设计

- [x] LangGraph 正式入口已切换为 `make_coach_agent()`
- [x] `lead_agent` 不再作为当前 coach 正式业务入口
- [x] `CoachIntakeMiddleware` 设计职责清晰
- [x] 结构化 intent schema 已定义
- [x] 组合路由顺序规则已明确
- [ ] route-specific writeback 策略已明确
- [x] `coach_profile.json` 被定义为 canonical state

## Middleware 取舍

- [x] `ThreadDataMiddleware` 已保留
- [x] `UploadsMiddleware` 已保留
- [x] `SandboxMiddleware` 已保留
- [x] `SummarizationMiddleware` 已保留
- [x] `MemoryMiddleware` 已保留
- [x] `ViewImageMiddleware` 已保留
- [x] `ToolErrorHandlingMiddleware` 已保留
- [x] `ClarificationMiddleware` 仅作为兼容层保留
- [x] `TodoMiddleware` 已移除
- [x] `SubagentLimitMiddleware` 已移除

## 实现

- [x] `make_coach_agent()` 已实现并接线
- [x] `CoachIntakeMiddleware` 已实现骨架
- [x] 单意图路由已实现
- [x] 复合意图路由已实现
- [x] `safety gate` hook 已预留
- [x] persona schema 已实现
- [ ] task/session override 已实现
- [ ] persona 已在 intake 层生效
- [ ] writeback 仍走 observation -> code merge

## 测试

- [x] 入口切换回归测试已通过
- [x] middleware 行为测试已通过
- [x] 单意图路由测试已通过
- [x] mixed intent 路由测试已通过
- [ ] persona 覆盖测试已通过
- [x] `risk_level` 结构字段测试已通过
- [ ] profile 写回边界测试已通过
- [ ] structured logs 在新入口下仍能输出 latency / token / route / memory hit / error
- [ ] run log 汇总报告可正常生成
- [ ] 离线评测报告可正常生成
- [ ] 离线评测样本覆盖至少一个 mixed intent 场景
- [ ] LLM Judge 扩展入口或 judge prompt 已保留

## 文档与评测

- [x] `dev-spec.md` 与实现一致
- [ ] `tasks.md` 与当前阶段拆解一致
- [x] 评测维度与指标定义已写入 spec
- [ ] 残留风险已记录
- [ ] 阶段总结已输出

## 风险复核与回滚预案

- [ ] 已确认入口替换带来的上游同步风险
- [ ] 已确认测试、脚本、配置中不再错误依赖 `lead_agent`
- [ ] 已准备入口切换失败时的最小回滚方案
- [ ] 已确认未关闭的待确认问题不会影响主路径实现
