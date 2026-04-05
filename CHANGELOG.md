# Changelog

## 2026-04-06

### Coach Runtime Phase 2 收口

- 完成 `make_coach_agent()` 入口收敛、coach middleware 组合、intent schema、mixed intent router、safety gate hook
- 完成 `task/session` persona override、response renderer、route-specific writeback
- 完成 offline eval CLI、run log summary 脚本、评测样本与报告生成
- 完成 Phase 2 文档收口与阶段总结

### Clarification Pipeline

- 新增 coach clarification policy，把 `intent + missing_slots + persona` 映射为结构化追问请求
- `CoachIntakeMiddleware` 现在会直接产出 `intent` 和 `clarification_request`
- channel 最终响应链支持在当前 turn 无 AI 文本时回退到 `clarification_request.question`
- 新增 `CoachClarificationMiddleware`，在模型调用前短路出标准 `ask_clarification` tool call，并复用现有 `ClarificationMiddleware` 完成中断

### Observability / Analytics

- structured logs 新增 `clarification` 字段，记录 `requested / reason / missing_slots / question`
- analytics summary 和 by-route 聚合新增 clarification 指标：
  - `clarification_requested_count`
  - `clarification_request_rate`
  - `clarification_reasons`

### Reports

- `docs/eval/coach_eval_report.md`
- `docs/eval/coach_eval_report.json`
- `docs/eval/run_log_summary.md`
