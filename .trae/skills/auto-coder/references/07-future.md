## 7. 可扩展性与未来展望
### 7.1 业务扩展
- 从“赛前/赛后建议”扩展到“周期训练计划”
- 引入新手 / 进阶 / 竞技三级策略模板
- 增加伤病恢复期专用模式
- 输出周报与月度训练趋势总结
### 7.2 工程扩展
- 当 prompt 路由无法稳定收敛时，升级为代码级意图路由器
- 当单用户场景跑通后，把 `coach_profile.json` 迁移到 SQLite / PostgreSQL
- 针对 Health 场景引入独立 OCR/STT 组件，提高结构化稳定性
- 增加评估脚本与标准样本，形成可复用的垂类 Agent 评估模板
### 7.3 架构扩展
- 后续若需要显式状态机与节点可视化，再考虑新增独立 LangGraph graph
- 后续若要支持多种垂类 Agent，可把 `coach_profile + review_logs` 抽象成 domain profile hook
- 后续若要接入更多渠道，可复用同一 Coach Agent，只替换 channel adapter
### 7.4 当前仍待确认的问题
1. Phase 2 的 STT 最终选哪条路线？
2. Phase 2 的图片 OCR / 指标解析最终选哪条路线？
3. 主动提醒最终采用外部 cron 还是仓库内 scheduler？
