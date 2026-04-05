# Phase 2 Tasks

本文件从 [`dev-spec.md`](/Users/reducedmatrice/Documents/github/note-agent/dev-spec.md) 映射而来，按阶段拆分实现任务。

## 阶段 A：入口与中间件重构

### A1 入口切换到 `make_coach_agent()` `Done`

- 目标：建立独立 coach runtime，并将 LangGraph 正式入口切到 `make_coach_agent()`
- 输入：现有 `lead_agent` 装配逻辑、`backend/langgraph.json`、coach 相关 domain 能力
- 输出：新的 coach agent 入口、更新后的 LangGraph 配置、最小回归测试
- 依赖：无
- 完成定义（DoD）：
  - 新入口可正常装配并运行
  - 当前 coach 流程不再依赖 `lead_agent` 作为正式入口
  - 相关测试和文档已更新
- 并行项：可与 A2 设计同步讨论，但代码改动建议串行
- 阻塞项：若入口切换影响现有运行脚本，需要先统一入口命名

### A2 Middleware 裁剪与重组 `Done`

- 目标：保留必要基础中间件，去掉不适合 coach runtime 的通用编排中间件
- 输入：现有 middleware 链、已确认取舍规则
- 输出：新的 middleware 组合、兼容说明、测试覆盖
- 依赖：A1
- 完成定义（DoD）：
  - 保留 `ThreadData/Uploads/Sandbox/Summarization/Memory/ViewImage/ToolErrorHandling`
  - 去掉 `Todo/SubagentLimit`
  - `ClarificationMiddleware` 仅作为兼容层保留
- 并行项：可与 A3 schema 设计并行
- 阻塞项：无

### A3 新增 `CoachIntakeMiddleware` 骨架 `Done`

- 目标：建立统一 intake 层，为后续 persona、意图识别和追问策略提供入口
- 输入：线程上下文、memory/profile/reviews、persona 配置需求
- 输出：middleware 骨架、状态结构、基本测试
- 依赖：A2
- 完成定义（DoD）：
  - 能汇总输入与上下文
  - 能暴露后续识别层所需结构
  - 为追问和 persona 注入预留清晰接口
- 并行项：可与 B1 并行设计
- 阻塞项：无

## 阶段 B：意图识别与组合路由

### B1 定义 intent schema `Done`

- 目标：建立统一结构化识别结果
- 输入：已确认的主意图、复合意图与缺失槽位规则
- 输出：intent schema、解析接口、单元测试
- 依赖：A3
- 完成定义（DoD）：
  - 至少包含 `primary_intent`、`secondary_intents`、`slots`、`missing_slots`、`risk_level`
  - schema 在单意图和复合意图场景都可复用
- 并行项：可与 C1 schema 设计并行
- 阻塞项：无

### B2 实现单意图路由 `Done`

- 目标：让 `prematch/postmatch/health/fallback` 都通过结构化路由进入正确链路
- 输入：intent schema、现有 `domain/coach/*`
- 输出：单意图路由器、测试样本
- 依赖：B1
- 完成定义（DoD）：
  - 四类主路由可稳定命中
  - 已知强规则优先代码控制
- 并行项：无
- 阻塞项：无

### B3 实现复合意图组合路由 `Done`

- 目标：支持 mixed intent 场景下的顺序控制与稳定输出
- 输入：intent schema、组合规则
- 输出：组合路由逻辑、集成测试
- 依赖：B2
- 完成定义（DoD）：
  - 至少覆盖 `health + prematch`、`postmatch + health`、`prematch + postmatch`
  - 输出顺序与边界稳定
- 并行项：无
- 阻塞项：无

### B4 预留 `safety gate` 接口 `Done`

- 目标：在当前不深做安全系统的前提下，为后续 safety gate 预留清晰 hook
- 输入：组合路由结构、`risk_level` 字段
- 输出：接口位置、轻量测试、文档说明
- 依赖：B3
- 完成定义（DoD）：
  - 路由链存在可插入的 safety hook
  - 当前代码不引入复杂医学逻辑
- 并行项：可与 D1 测试完善并行
- 阻塞项：无

## 阶段 C：Persona 与状态写回

### C1 定义 persona config schema `Done`

- 目标：将教练人格与风格做成结构化配置
- 输入：tone、strictness、verbosity、questioning_style 等需求
- 输出：persona schema、默认配置
- 依赖：A3
- 完成定义（DoD）：
  - 字段边界清晰
  - 不允许 persona 覆盖安全边界与路由主逻辑
- 并行项：可与 B1 并行
- 阻塞项：无

### C2 支持 task/session override `Done`

- 目标：让用户可以在飞书 task 中设置 persona 覆盖项
- 输入：persona schema、task/session 上下文
- 输出：override 合并逻辑、测试
- 依赖：C1
- 完成定义（DoD）：
  - 默认 persona 可被局部覆盖
  - 合并逻辑稳定且可测试
- 并行项：无
- 阻塞项：需要明确 task 上下文字段来源

### C3 Persona 接入 intake 层 `Done`

- 目标：在真正进入意图和路由前就完成 persona 注入
- 输入：`CoachIntakeMiddleware`、persona schema、override
- 输出：intake 注入逻辑、行为测试
- 依赖：C2
- 完成定义（DoD）：
  - persona 影响语气、提问和组织方式
  - 不影响路由顺序和写回边界
- 并行项：无
- 阻塞项：无

### C4 固化 route-specific writeback `Done`

- 目标：把 profile 更新继续锁定在 observation -> code merge 路径
- 输入：现有 `profile_store.py`、postmatch/health 观察结果
- 输出：稳定 writeback 策略、测试
- 依赖：B2
- 完成定义（DoD）：
  - `coach_profile.json` 不存在 LLM 直接写路径
  - review log 与 narrative memory 继续分层
- 并行项：可与 D2 并行补测试
- 阻塞项：无

## 阶段 D：测试与文档收敛

### D1 入口与 middleware 回归测试 `Done`

- 目标：确保 runtime 重构不破坏现有主链路
- 输入：新入口、middleware 组合
- 输出：回归测试集、冒烟测试
- 依赖：A1、A2、A3
- 完成定义（DoD）：
  - 关键路径测试通过
  - 入口切换后的文档已同步
- 并行项：可与 B4 并行
- 阻塞项：无

### D2 mixed intent 与 persona 测试 `Done`

- 目标：验证复合意图和 persona 的真实行为
- 输入：路由逻辑、persona 注入逻辑
- 输出：单元测试和集成测试样本
- 依赖：B3、C3、C4
- 完成定义（DoD）：
  - mixed intent 顺序正确
  - persona 覆盖结果可验证
- 并行项：无
- 阻塞项：无

### D3 可观测性与离线评测收敛 `Done`

- 目标：确保 runtime 重构后仍具备结构化日志与离线评测能力
- 输入：structured logging、run log summary、coach eval 样本与脚本
- 输出：更新后的日志字段、汇总报告、离线评测报告、补充样本
- 依赖：D1、D2
- 完成定义（DoD）：
  - structured logs 能输出 latency / token / route / memory hit / error
  - 可生成 run log markdown 汇总
  - 离线评测至少覆盖 `prematch`、`postmatch`、`health` 与一种 mixed intent
  - 保留 LLM Judge 扩展入口
- 并行项：可与 D4 文档整理部分并行
- 阻塞项：无

### D4 文档、评测与阶段总结 `Done`

- 目标：完成 Phase 2 文档收敛和阶段总结
- 输入：实现结果、测试结果、评测结果
- 输出：更新后的 spec、自检结果、阶段总结
- 依赖：D3
- 完成定义（DoD）：
  - 文档与实现一致
  - 残留风险和下一阶段关注点已记录
- 并行项：无
- 阻塞项：无
