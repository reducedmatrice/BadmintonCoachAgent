# Coach Multimodal Intake 3.0 Tasks

本文件从 [dev-spec3.0.md](./dev-spec3.0.md) 映射而来，按阶段拆分实现任务。

## Phase 1：飞书图片入站与原图获取

- 状态：待开始
- 目标：让飞书图片消息进入 coach 可消费链路，而不是只生成占位文本
- 输入：现有 `backend/app/channels/feishu.py`、附件元数据结构、线程上下文
- 输出：图片消息解析增强、原图获取方案、失败降级约束
- 依赖：无
- 并行项：可与 Phase 2 的 Schema 设计并行
- 阻塞项：无
- 完成定义（DoD）：
  - 飞书图片消息不再固定回退为“请补文字描述”
  - coach runtime 能拿到可消费的图片输入或临时文件句柄
  - 原图获取失败有明确降级策略
  - 不引入长期原图存储

## Phase 2：多模态抽取与强 Schema 校验

- 状态：待开始
- 目标：将运动截图转为可写回、可测试的结构化记录
- 输入：图片输入、图文混合文本、视觉模型配置
- 输出：运动记录 Schema、多模态抽取节点、置信度与缺失字段策略
- 依赖：Phase 1
- 并行项：可与 Phase 4 的日志字段设计并行
- 阻塞项：无
- 完成定义（DoD）：
  - 存在强 Schema 的结构化输出约定
  - 能抽取核心字段：时长、心率、训练负荷/压力、热量、恢复提示
  - 支持缺失字段与低置信度分支
  - 不采用纯 OCR 作为主链路
  - 使用单独视觉模型，不污染文本主链路

## Phase 3：事件证据写回与 canonical state merge

- 状态：待开始
- 目标：把单次运动记录安全地落到 Memory 2.2 体系中
- 输入：结构化运动记录、现有 `profile_store.py`、`memory/reviews` 约定
- 输出：event evidence 追加写入、`health_profile` 聚合更新、写回边界规则
- 依赖：Phase 2
- 并行项：可与 Phase 4 的 recall policy 设计并行
- 阻塞项：无
- 完成定义（DoD）：
  - 单次运动明细写入 `memory/reviews/YYYY-MM-DD.md`
  - `coach_profile.json.health_profile` 只保留聚合状态
  - 低置信度结果不会直接更新 profile
  - 不新增与现有设计冲突的顶层 profile 结构

## Phase 4：状态回忆与回答表达

- 状态：待开始
- 目标：让 agent 在合适场景主动提起上一次相关身体状态
- 输入：`CoachIntakeMiddleware`、`response_renderer.py`、现有 `prematch` / `health` 路由
- 输出：recall context、recall policy、回忆式表达策略
- 依赖：Phase 3
- 并行项：可与 Phase 5 的样本评测准备并行
- 阻塞项：recall 时间窗口与触发阈值待确认
- 完成定义（DoD）：
  - `CoachIntakeMiddleware` 可装配最近一次相关身体状态
  - `health` 场景可优先引用最近一次健康/运动记录
  - `prematch` 场景在高疲劳 / 最近高负荷时可主动 recall
  - recall 表达使用“回忆到的上下文”语气，不伪装成实时事实

## Phase 5：测试、观测与灰度验证

- 状态：待开始
- 目标：确保多模态链路可测、可观测、可回滚
- 输入：现有 `backend/tests/`、structured logging、离线评测框架
- 输出：新增单元 / 集成 / E2E 测试、日志字段、灰度与回滚策略
- 依赖：Phase 1-4
- 并行项：无
- 阻塞项：无
- 完成定义（DoD）：
  - 图片入站、多模态抽取、双写、recall 均有测试覆盖
  - structured logs 能区分关键失败类型
  - 至少 1 条“发图 -> 写回 -> 下次主动 recall”的集成用例通过
  - 回滚时可关闭多模态入口并回退到文本链路
  - 同步抽取链路延迟可被观测

## Phase 6：缓存治理与清理任务

- 状态：待开始
- 目标：为临时图片缓存提供可回收、可校验的治理机制
- 输入：channel 侧临时图片文件、event evidence、profile 写回结果
- 输出：30 天保留策略、删除前校验规则、清理任务与重试日志
- 依赖：Phase 1-3
- 并行项：可穿插执行
- 阻塞项：无
- 完成定义（DoD）：
  - 临时图片缓存默认保留 30 天
  - 删除前会校验 `memory/reviews` 与 `coach_profile.json` 写回完成
  - 校验失败时会延后删除并记录日志
  - 清理机制不会误删尚未完成沉淀的图片
