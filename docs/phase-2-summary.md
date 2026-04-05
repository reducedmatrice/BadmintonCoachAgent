# Phase 2 总结

## 结果

Phase 2 已完成从通用 `lead_agent` 挂载模式到独立 coach runtime 的收敛。

当前主线能力包括：

- LangGraph 入口切换到 `make_coach_agent()`
- `CoachIntakeMiddleware` 统一汇总线程上下文、memory、profile 与 persona
- `prematch`、`postmatch`、`health`、`fallback` 单意图路由
- mixed intent 组合顺序控制与 `safety gate` 预留接口
- `task/session` 级 persona override
- route-specific writeback，继续保持 `coach_profile.json` 由代码 merge
- structured logs、run log markdown 汇总、offline eval 报告链路

## 本阶段产出

- 运行时入口：`backend/packages/harness/deerflow/agents/coach_agent/agent.py`
- intake 中间件：`backend/packages/harness/deerflow/agents/middlewares/coach_intake_middleware.py`
- 意图与路由：`backend/packages/harness/deerflow/domain/coach/intent.py`、`backend/packages/harness/deerflow/domain/coach/router.py`
- persona 与渲染：`backend/packages/harness/deerflow/domain/coach/persona.py`、`backend/packages/harness/deerflow/domain/coach/response_renderer.py`
- writeback：`backend/packages/harness/deerflow/domain/coach/profile_store.py`
- 可观测性与评测：`backend/app/channels/structured_logging.py`、`backend/packages/harness/deerflow/evaluation/run_log_report.py`、`backend/packages/harness/deerflow/evaluation/coach_eval.py`
- 评测资产：`docs/eval/coach_eval_cases.json`、`docs/eval/coach_eval_report.md`、`docs/eval/run_log_summary.md`

## 验证结果

- 入口 / middleware / router / persona / writeback / eval 相关测试已补齐
- D3 评测链路已经可直接运行：
  - `python3 scripts/run_coach_eval.py --cases docs/eval/coach_eval_cases.json --output docs/eval/coach_eval_report.md --json-output docs/eval/coach_eval_report.json`
  - `python3 scripts/summarize_run_logs.py --log-file backend/tests/fixtures/analytics_stage_e_gateway.log --output docs/eval/run_log_summary.md`
- 当前离线评测报告：
  - case 数：7
  - 平均分：4.78 / 5

## 关键取舍

- 保留 DeerFlow 作为 harness，但不再把 coach 业务主链路挂在 `lead_agent` prompt 编排上
- persona 只作用于表达层，不覆盖 route / risk / writeback 边界
- `coach_profile.json` 继续作为 canonical state，LLM 不直接写入
- `safety gate` 本阶段只保留 hook，不引入复杂医学规则
- 先完成规则化 offline eval，把 LLM Judge 保持为下一阶段扩展入口

## 残留风险

- `CoachIntakeMiddleware` 已完成上下文汇总与 persona 注入，但“主追问决策层”仍然偏骨架化，后续若要降低误追问率，需要补更明确的 clarification policy
- 当前 persona 已进入 response renderer，但尚未贯穿到更完整的 agent 最终回答链，如果后续切回更多 LLM 生成内容，需要继续做 persona contract 约束
- offline eval 目前以规则打分为主，`grounding` 等维度对“无历史上下文样本”有保守惩罚，报告阅读时需要结合样本语义解释
- `safety gate` 仅完成接口预留，尚未形成真实风险分级和阻断策略

## 下一阶段建议

- 优先方向 1：把 intake 从“上下文汇总层”推进到“明确追问决策层”，补 clarification policy、缺失槽位策略和追问测试
- 优先方向 2：补真正的 coach response assembly，把 router payload、persona renderer 和 channel 最终响应链打通
- 优先方向 3：在保留当前规则评测的前提下，尝试接入 LLM Judge 批评测与人工抽样复核
