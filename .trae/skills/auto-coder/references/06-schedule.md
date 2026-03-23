## 6. 项目排期
> 排期原则：先做出可演示 demo，再补强多模态和主动能力；每个阶段都必须同时产出“可跑结果 + 最小测试 + 阶段总结”。
### 阶段总览
| 阶段 | 目标 | 预计用时 | 是否属于 MVP |
|------|------|----------|--------------|
| A | Coach Agent 装配与技能骨架 | 0.5 天 | 是 |
| B | 赛前/赛后文本闭环 + 记忆更新 | 1 天 | 是 |
| C | Weather + Feishu 展示优化 + 日志落盘 | 0.5 天 | 是 |
| D | Health 图片链路 + 评估体系 | 0.5-1 天 | 建议完成 |
| E | 飞书多模态入站 + 主动提醒 | 1-2 天 | 否，Phase 2 |
如果只做最小可讲 demo，建议目标是 **2-3 天完成 A + B + C**。
### 📊 进度跟踪表 (Progress Tracking)
> 状态说明：`[ ]` 未开始 | `[~]` 进行中 | `[x]` 已完成
#### 阶段 A：Agent 装配
- [x] A1 创建 `badminton-coach` custom agent 运行时装配方案
- [x] A2 定义 `SOUL.md` 的角色边界、回复风格、安全约束
- [x] A3 建立最小可演示链路
- [x] A4 [doc] 产出阶段总结（1000-2000 字）
#### 阶段 B：文本主闭环
- [x] B1 跑通 `prematch` 文本路径
- [x] B2 跑通 `postmatch` 文本路径
- [x] B3 引入 `coach_profile.json` 与日期日志
- [x] B4 [doc] 产出阶段总结（1000-2000 字）
#### 阶段 C：上下文增强
- [x] C1 接入 Weather MCP
- [x] C2 优化飞书 card 输出模板与稳定性
- [x] C3 建立 structured logs
- [x] C4 [doc] 产出阶段总结（1000-2000 字）
#### 阶段 D：评估与增强
- [x] D1 跑通 Web 图片分析链路
- [x] D2 建立离线评测样本集
- [x] D3 建立延迟 / token / Judge 指标输出
- [x] D4 [doc] 产出阶段总结（1000-2000 字）
#### 阶段 E：Phase 2
- [x] E1 扩展飞书图片/语音/文件入站
- [x] E2 增加主动提醒调度能力
- [ ] E3 [doc] 产出阶段总结（1000-2000 字）
### 📈 总体进度
- 当前状态：`[~]` 阶段 B 已完成，阶段 C 待开始
- MVP 定义：完成 A + B + C
- 推荐演示版本：完成 A + B + C + D1
## 阶段 A：Agent 装配
### A1：定义 Coach Agent 装配方式
- **目标**：在不修改 `langgraph.json` 图注册、不新增 graph 的前提下，让会话通过 `context.agent_name` 稳定运行于 Coach 身份
- **输入**：现有 `make_lead_agent()`、`configurable.agent_name`、custom agent 机制、`ChannelManager._resolve_run_params()`
- **输出**：
  - `backend/.deer-flow/agents/badminton-coach/config.yaml`
  - `backend/.deer-flow/agents/badminton-coach/SOUL.md`
  - `backend/.deer-flow/agents/badminton-coach/memory.json`
  - 会话约定：`assistant_id` 继续使用 `lead_agent`，通过 `session.context.agent_name=badminton-coach` 切换 Coach 身份
- **依赖**：
  - `backend/packages/harness/deerflow/config/agents_config.py`
  - `backend/packages/harness/deerflow/agents/lead_agent/agent.py`
  - `backend/app/channels/manager.py`
- **完成定义（DoD）**：
  - `lead_agent` 在 `configurable.agent_name=badminton-coach` 时能加载 custom agent 配置
  - 能正确读取 per-agent `SOUL.md` 与 per-agent `memory.json`
  - Channel session 的 `context.agent_name` 能透传到 `runs.wait(..., context=...)`
  - 不修改现有 graph 注册与 assistant id 体系
- **测试方法**：
  - 扩展 `backend/tests/test_custom_agent.py`
  - 扩展 `backend/tests/test_channels.py`
### A2：定义 SOUL 与技能边界
- **目标**：让 Coach 具备稳定的人设、约束与提问方式
- **输入**：项目目标、业务边界、用户偏好
- **输出**：
  - `backend/.deer-flow/agents/badminton-coach/SOUL.md`
  - `skills/custom/badminton-coach/router/SKILL.md`
  - `skills/custom/badminton-coach/prematch/SKILL.md`
  - `skills/custom/badminton-coach/postmatch/SKILL.md`
  - `skills/custom/badminton-coach/health/SKILL.md`
- **依赖**：现有 skills loader 机制
- **完成定义（DoD）**：
  - Agent 能稳定使用教练语气与约束
  - 缺少关键信息时优先追问
  - Coach 自定义 skills 能被 loader 正常发现
- **测试方法**：
  - 固定样本人工 review
  - `backend/tests/test_skills_loader.py`
### A3：建立最小可演示链路
- **目标**：先跑通“飞书文本 -> Coach 回复”
- **输入**：Feishu channel、session config
- **输出**：
  - `config.example.yaml` 中的 Feishu Coach session 示例
  - `backend/tests/test_channels.py` 中的 Feishu Coach session 回归测试
- **依赖**：A1、A2
- **完成定义（DoD）**：
  - 回复能显示在 Feishu card 中
  - 会话不落回默认 agent
- **测试方法**：扩展 `backend/tests/test_channels.py`
### A4：[doc] 阶段总结
- **目标**：沉淀阶段 A 的架构决策、实现边界和后续风险
- **输入**：A1-A3 的实现结果、测试结果、配置约定
- **输出**：`docs/stage-a-summary.md`
- **依赖**：A1、A2、A3
- **完成定义（DoD）**：
  - 说明本阶段实际交付了什么
  - 说明为什么采用 `lead_agent + context.agent_name` 路线
  - 说明当前残留风险与阶段 B 的进入条件
- **测试方法**：人工 review
## 阶段 B：文本主闭环
### B1：实现 Pre-match 文本路径
- **目标**：让 Agent 对赛前咨询给出个性化训练建议
- **输入**：赛前文本、历史记忆、天气信息
- **输出**：
  - `backend/packages/harness/deerflow/domain/coach/prematch.py`
  - `backend/tests/test_coach_prematch_rules.py`
  - 训练重点、热身建议、风险提示
- **依赖**：A 阶段已完成
- **完成定义（DoD）**：
  - 有历史弱项时会引用
  - 能引用 `coach_profile.json` 或最近日期日志
  - 没有历史时会退回通用建议
- **测试方法**：`pytest -q tests/test_coach_prematch_rules.py`
### B2：实现 Post-match 文本路径
- **目标**：把赛后文本复盘转成结构化技术观察
- **输入**：赛后复盘文本
- **输出**：
  - `backend/packages/harness/deerflow/domain/coach/postmatch.py`
  - `backend/tests/test_coach_postmatch_extraction.py`
  - 技术总结、下次重点、记忆更新
- **依赖**：A 阶段已完成
- **完成定义（DoD）**：
  - 能识别弱项、进步点、下次重点
  - 不把情绪性表达误判为技术事实
- **测试方法**：`pytest -q tests/test_coach_postmatch_extraction.py`
### B3：引入 Coach Structured Profile 与日期日志
- **目标**：建立可持续演进的结构化档案和事件沉淀
- **输入**：postmatch / health 的结构化抽取结果
- **输出**：
  - `backend/packages/harness/deerflow/domain/coach/profile_store.py`
  - `backend/tests/test_coach_profile.py`
  - `backend/tests/test_coach_integration_flow.py`
  - `coach_profile.json` 与 `memory/reviews/YYYY-MM-DD.md`
- **依赖**：B2
- **完成定义（DoD）**：
  - 赛后复盘能回写技术档案
  - 会按日期追加训练日志
  - 下一次赛前能读取这些内容
- **测试方法**：`pytest -q tests/test_coach_profile.py tests/test_coach_integration_flow.py`
### B4：[doc] 阶段总结
- **目标**：沉淀文本主闭环的实现方式、数据流和残留风险
- **输入**：B1-B3 的规则层、持久化层和测试结果
- **输出**：`docs/stage-b-summary.md`
- **依赖**：B1、B2、B3
- **完成定义（DoD）**：
  - 说明赛前/赛后/档案闭环分别交付了什么
  - 说明当前还未进入模型编排和 MCP 的边界
  - 说明阶段 C 的进入条件
- **测试方法**：人工 review
## 阶段 C：上下文增强
### C1：接入 Weather MCP
- **目标**：让天气真实影响建议内容
- **输入**：天气查询结果
- **输出**：补水、时长、强度调整建议
- **依赖**：MCP 配置可用
- **完成定义（DoD）**：
  - 高温场景与普通场景输出明显不同
  - MCP 失败时按降级逻辑处理
- **测试方法**：集成测试 + MCP Mock
### C2：优化飞书回复模板
- **目标**：让输出更像产品，而不是普通聊天
- **输入**：Coach 回答文本
- **输出**：结构稳定、便于阅读的卡片内容
- **依赖**：现有 running card patch 机制
- **完成定义（DoD）**：
  - 标题、重点项、风险提示、下次建议结构清晰
- **测试方法**：`backend/tests/test_channels.py`
### C3：建立 structured logs
- **目标**：把评估与排障所需数据先以日志形式落地
- **输入**：每次请求的运行数据
- **输出**：延迟、token、路由、命中 memory 的结构化日志
- **依赖**：主链路已接入埋点
- **完成定义（DoD）**：
  - 能按请求输出主路由、耗时、token、memory 命中情况
- **测试方法**：固定样本回放 + 日志校验
## 阶段 D：评估与增强
### D1：Web 图片分析链路
- **目标**：先在 Web Workspace 跑通 Health 图片路径
- **输入**：运动截图
- **输出**：结构化健康观察与恢复建议
- **依赖**：视觉模型、上传能力
- **完成定义（DoD）**：
  - 至少支持 3 类常见截图样本
- **测试方法**：新增 Health 用例 + 人工验证
### D2：离线评测体系
- **目标**：量化建议质量与路由质量
- **输入**：样本集、Judge prompt
- **输出**：评估报告
- **依赖**：前序主路径稳定
- **完成定义（DoD）**：
  - 能输出均分、分项分、失败样本
- **测试方法**：评估脚本批量运行
### D3：性能与成本统计
- **目标**：让优化有量化依据
- **输入**：运行时日志与模型用量
- **输出**：延迟 / token / 错误率统计
- **依赖**：主链路已接入埋点
- **完成定义（DoD）**：
  - 能按场景输出 P50/P95 与平均 token
- **测试方法**：固定样本压测
## 阶段 E：Phase 2
### E1：飞书多模态入站
- **目标**：支持图片、文件、语音消息入站
- **输入**：飞书非文本消息
- **输出**：统一的结构化输入事件
- **依赖**：飞书 API 能力、文件下载/转写服务
- **完成定义（DoD）**：
  - 图片与语音都能进入 Coach 流程
- **测试方法**：扩展 `backend/tests/test_channels.py`
### E2：主动提醒
- **目标**：在训练前固定时间推送提醒
- **输入**：用户偏好、天气、历史档案
- **输出**：主动提醒卡片
- **依赖**：外部调度器或新增 scheduler
- **完成定义（DoD）**：
  - 指定时间自动推送
  - 不重复发送
- **测试方法**：集成测试 + 幂等验证
---