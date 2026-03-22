## 3. 技术选型
### 3.1 总体技术路线
本项目采用“**custom agent + skills + MCP + hybrid memory + Feishu channel**”的组合路线，而不是新建一套独立 graph。
核心原因：
- 当前 `make_lead_agent()` 已支持 `agent_name`
- 当前仓库已经具备 custom agent、per-agent memory、skills、Feishu channel 基础设施
- 新增独立 graph 会让实现与现有产品能力脱节，且维护成本更高
### 3.2 已确认选型
| 层级 | 选型 | 说明 |
|------|------|------|
| Agent Runtime | 复用 `lead_agent` | 通过 `configurable.agent_name=badminton-coach` 定制化 |
| Agent 身份层 | custom agent | 使用独立 `config.yaml + SOUL.md + memory.json` |
| Channel | Feishu WebSocket Channel | 复用现有 `backend/app/channels/feishu.py` |
| 交互返回 | Feishu Interactive Card | 现有代码已支持 running card 与最终 card patch |
| 短期记忆 | LangGraph Checkpointer + SQLite | 已有 `checkpointer.type=sqlite` 配置能力 |
| 长期记忆 | `memory.json + coach_profile.json + memory/reviews/YYYY-MM-DD.md` | 叙事背景、稳定结构化状态、按日期事件沉淀三者分工 |
| Skills | `skills/custom/.../SKILL.md` | 用于业务工作流规范、术语约束、提问策略 |
| 外部上下文 | MCP | 首版只要求 Weather，Calendar/Notes 延后 |
| 评估 | `pytest + LLM as a Judge + structured logs` | 同时覆盖自动化测试与离线评测 |
### 3.3 明确不采用的方案
#### 3.3.1 不采用“首版就新增独立 LangGraph Graph”
原因：
- 当前系统只有 `lead_agent` 图入口
- 自定义 graph 会增加注册、部署、前端选择、运行时切换成本
- MVP 目标是验证 Coach 场景，不是重构 agent runtime
#### 3.3.2 不采用“首版就引入 PostgreSQL”
原因：
- 当前单用户 MVP 更适合本地文件 + SQLite
- 结构化档案写入量小，SQLite/JSON 足够
- 过早引入 DB 会增加迁移与运维成本
#### 3.3.3 不采用“首版就启用 subagent”
原因：
- 赛前/赛后问答强调低延迟与稳定性
- 当前场景不是典型并行研究任务
- 开启 subagent 会拉长链路并增加结果合成误差
默认策略：
- 交互式主路径：`subagent_enabled=false`
- 长文总结/周报：后续可单独开启
### 3.4 配置策略
建议在 `config.yaml` 中把 Coach 作为会话上下文注入，而不是改动 graph 注册。
推荐会话配置如下：
```yaml
channels:
  session:
    assistant_id: lead_agent
    context:
      agent_name: badminton-coach
      thinking_enabled: true
      subagent_enabled: false
```
说明：
- `assistant_id` 仍使用 `lead_agent`
- 通过 `context.agent_name` 装配 Coach 的身份与记忆
- 首版禁用 subagent，优先稳定与延迟
### 3.5 源码与运行时资产的分工
这是本项目的重要工程约束。
#### 3.5.1 版本化源码
应提交到仓库的内容：
- `skills/custom/...`
- `backend/app/channels/...`
- `backend/packages/harness/deerflow/agents/memory/...`
- `backend/tests/...`
- 评估脚本与测试样本
- 每阶段 1000-2000 字阶段总结
#### 3.5.2 运行时资产
由系统创建或初始化，不建议直接作为源码主载体：
- `backend/.deer-flow/agents/badminton-coach/config.yaml`
- `backend/.deer-flow/agents/badminton-coach/SOUL.md`
- `backend/.deer-flow/agents/badminton-coach/memory.json`
- `backend/.deer-flow/agents/badminton-coach/coach_profile.json`
- `backend/.deer-flow/agents/badminton-coach/memory/reviews/YYYY-MM-DD.md`
### 3.6 待确认技术项
以下项会影响实现细节，但不阻止本版 spec 成立。
#### 3.6.1 语音转写方案
- 状态：待确认
- 候选方案：飞书原生能力 / Whisper API / 本地 Whisper
- 决策依据：接入复杂度、费用、延迟、中文术语识别率
- 最晚决策点：进入 Phase 2 多模态前
- 需用户确认：是
#### 3.6.2 图片 OCR / 指标解析方案
- 状态：待确认
- 候选方案：视觉模型直接解析 / 独立 OCR 服务 + LLM 后处理
- 决策依据：结构化稳定性、图像质量鲁棒性、成本
- 最晚决策点：Health Analysis 从 Web 验证迁移到飞书前
- 需用户确认：是
#### 3.6.3 主动提醒的调度来源
- 状态：待确认
- 候选方案：外部 cron / 平台定时任务 / 仓库内新增 scheduler
- 决策依据：稳定性、部署复杂度、与飞书交互耦合度
- 最晚决策点：主动提醒开发开始前
- 需用户确认：是
---