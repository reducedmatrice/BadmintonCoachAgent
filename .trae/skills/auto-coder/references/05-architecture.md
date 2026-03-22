## 5. 系统架构与模块设计
### 5.1 整体架构图
```text
                          +----------------------+
                          |  Feishu Text Channel |
                          +----------+-----------+
                                     |
                                     v
                         +-----------+------------+
                         | app/channels/feishu.py |
                         |  app/channels/manager  |
                         +-----------+------------+
                                     |
                assistant_id=lead_agent + context.agent_name=badminton-coach
                                     |
                                     v
                  +------------------+-------------------+
                  | deerflow.agents.make_lead_agent()    |
                  |  - load agent config / SOUL / memory |
                  |  - load enabled skills               |
                  |  - inject memory into prompt         |
                  +------------------+-------------------+
                                     |
                     +---------------+----------------+
                     |                                |
                     v                                v
          +----------+-----------+         +----------+-----------+
          | skills/custom/coach  |         | MCP Context Adapters |
          | router / prematch /  |         | weather              |
          | postmatch / health   |         |                      |
          +----------+-----------+         +----------+-----------+
                     |                                |
                     +---------------+----------------+
                                     |
                                     v
                    +----------------+----------------------------+
                    | Hybrid Memory Layer                         |
                    | - memory.json                               |
                    | - coach_profile.json                        |
                    | - memory/reviews/YYYY-MM-DD.md             |
                    | - checkpointer(SQLite)                      |
                    +----------------+----------------------------+
                                     |
                                     v
                          +----------+-----------+
                          | Feishu Interactive   |
                          | Card / final reply   |
                          +----------------------+
```
### 5.2 目录结构
本项目建议把“可提交源码”和“运行时资产”分开管理。
#### 5.2.1 建议新增的版本化源码
```text
skills/
└── custom/
    └── badminton-coach/
        ├── router/
        │   └── SKILL.md
        ├── prematch/
        │   └── SKILL.md
        ├── postmatch/
        │   └── SKILL.md
        └── health/
            └── SKILL.md

backend/
├── app/
│   └── channels/
│       ├── feishu.py
│       └── manager.py
├── packages/
│   └── harness/
│       └── deerflow/
│           └── agents/
│               └── memory/
│                   ├── coach_profile.py
│                   ├── coach_profile_prompt.py
│                   ├── coach_profile_updater.py
│                   └── review_log_store.py
└── tests/
    ├── test_coach_profile.py
    ├── test_coach_router.py
    ├── test_coach_prematch_rules.py
    ├── test_coach_postmatch_extraction.py
    ├── test_coach_health_rules.py
    └── test_coach_integration_flow.py
```
#### 5.2.2 运行时资产路径
```text
backend/.deer-flow/
└── agents/
    └── badminton-coach/
        ├── config.yaml
        ├── SOUL.md
        ├── memory.json
        ├── coach_profile.json
        └── memory/
            └── reviews/
                └── YYYY-MM-DD.md
```
### 5.3 模块说明
#### 5.3.1 Coach Custom Agent
**职责**
- 定义 Agent 身份、说话风格、边界、安全规则
- 限定 Coach 相关 skills 的使用方式
- 使用独立长期记忆，不污染默认 agent
**实现方式**
- 运行时通过 `agent_name=badminton-coach` 注入
- `SOUL.md` 负责人格、原则、场景边界
- `config.yaml` 负责模型和 tool group 的可选覆盖
**设计原则**
- 首版不改 graph 注册
- 首版不新增第二套 orchestrator
#### 5.3.2 Router Skill
**职责**
- 识别 `prematch / postmatch / health / fallback`
- 明确每类路径最少需要的信息
- 输入不足时先用上下文与 memory 补齐，再决定是否追问
**输出契约**
建议 Router 在内部形成如下结构化判断：
```json
{
  "route": "prematch",
  "sub_intent": "today_focus",
  "confidence": 0.92,
  "memory_used": ["coach_profile", "review_logs"],
  "missing_fields": [],
  "should_clarify": false
}
```
#### 5.3.3 Pre-match Skill
**职责**
- 读取近期弱项与训练主题
- 结合天气与工作负荷
- 输出 1-3 条训练关注点和一条风险提醒
**输出要求**
- 不给空泛鼓励
- 必须落到动作或策略
- 如果没有历史记忆，要显式说明“先用通用建议”
#### 5.3.4 Post-match Skill
**职责**
- 从复盘文本中提取技术观察
- 区分“事实描述”“主观情绪”“下次目标”
- 更新记忆、结构化档案和日期日志
**结构化抽取建议**
```json
{
  "technical_observations": [
    {
      "topic": "后场步法",
      "finding": "回位慢",
      "severity": 0.8,
      "evidence": "后场球后续衔接不上"
    }
  ],
  "improvements": [
    {
      "topic": "反手压腕",
      "evidence": "今天反手更敢发力了"
    }
  ],
  "next_focus": ["后场启动", "反手稳定性"]
}
```
#### 5.3.5 Health Skill
**职责**
- 解释主观疲劳描述和结构化运动指标
- 给出恢复建议与强度控制建议
**规则**
- 没有图像/指标时，只能给主观恢复建议
- 有图像但解析失败时，提示用户补充文字
- 不输出医学诊断
#### 5.3.6 Coach Profile Updater
这是本项目最关键的新增工程模块。
**职责**
- 将赛后复盘与身体数据转成稳定结构化档案
- 为后续赛前建议提供可检索、可比较的领域状态
**为什么必须新增**
- 现有 `memory.json` 更适合叙事性上下文，不适合保存稳定的技术弱项趋势和身体指标趋势
- 如果没有结构化档案，个性化建议容易漂移
**更新时机**
- `postmatch` 完成后
- `health` 完成后
- `prematch` 一般只读，不写
**合并规则**
- 同名弱项重复出现时，更新 `last_seen_at` 与 `severity`
- 7 天未再次出现的弱项不删除，只降低活跃度
- 风险项采用显式列表，不因一次正常训练自动清空
#### 5.3.7 Review Log Store
**职责**
- 以低复杂度方式保留最近训练事件原文摘要
- 为“最近发生了什么”提供可解释依据
**写入规则**
- 每次 `postmatch` 追加
- 一天多次训练可写同一文件多个条目
- 条目必须含时间、场景、问题、进步点、下次重点
#### 5.3.8 Context Adapter
**Weather MCP**
- MVP 必接
- 若温度过高、湿度过高，建议降低强度与延长补水间隔
**Calendar MCP**
- 首版不接
- 后续可作为增强项，根据工作日程修正训练强度
**Notes MCP**
- 首版不接
- 后续可把用户历史球评、训练笔记当作背景知识
**降级规则**
- 任一 MCP 失败，不中断主流程
- 仅在输出中说明“未获取该外部上下文”
#### 5.3.9 Feishu Delivery Layer
**职责**
- 负责 running card 与 final card 更新
- 保持用户在飞书内的连续反馈体验
**首版能力**
- 文本入站
- 卡片流式更新
- 最终态完成标记
**Phase 2 扩展**
- 图片/语音/文件入站解析
- 文件下载、转写、图像提取
### 5.4 数据流说明
#### 5.4.1 赛前文本流程
1. 用户在飞书发送赛前问题
2. `FeishuChannel` 解析文本并发布入站消息
3. `ChannelManager` 组装 `assistant_id=lead_agent` 与 `context.agent_name=badminton-coach`
4. `make_lead_agent()` 载入 Coach 的 `SOUL.md`、`memory.json`
5. Agent 读取 Coach 相关 skills
6. Router 判定为 `prematch`
7. 读取 `coach_profile.json`、最近日期日志与 Weather MCP
8. 生成建议并通过 Feishu card 返回
9. 对话进入通用记忆队列，必要时更新 `topOfMind`
#### 5.4.2 赛后文本流程
1. 用户发送赛后复盘文本
2. Router 判定为 `postmatch`
3. Post-match Skill 提取结构化技术观察
4. 响应用户复盘总结与下次训练重点
5. `memory.json` 更新叙事性记忆
6. `coach_profile.json` 更新结构化技术档案
7. `memory/reviews/YYYY-MM-DD.md` 追加当次训练条目
#### 5.4.3 身体数据流程
1. 用户上传图片或描述疲劳情况
2. 如果是飞书文本：先按主观疲劳路径处理
3. 如果是 Web 图片：走现有 uploads + 视觉模型能力
4. Health Skill 生成结构化健康观察
5. 更新 `coach_profile.json.health_profile`
6. 返回恢复与强度控制建议
#### 5.4.4 主动提醒流程（Phase 2）
1. 外部调度器触发指定时间任务
2. 系统读取 `coach_profile.json`、Weather
3. 生成赛前提醒卡片
4. 通过 Feishu 主动发送
### 5.5 配置驱动设计
#### 5.5.1 必要配置项
- `channels.session.assistant_id`
- `channels.session.context.agent_name`
- `channels.session.context.thinking_enabled`
- `channels.session.context.subagent_enabled`
- `memory.*`
- `checkpointer.*`
- `skills.container_path`
- `extensions_config.json` 中 Coach 相关 skills 与 MCP 的启停状态
#### 5.5.2 参数化策略
以下参数不应硬编码在 prompt 中，建议配置化：
- 高温阈值
- 高疲劳阈值
- 每次建议的最大关注点数量
- 是否启用日期日志检索
- 日期日志默认回看天数
### 5.6 错误处理与降级策略
| 异常场景 | 系统行为 |
|----------|----------|
| Weather MCP 超时 | 使用无天气上下文版本的建议，并显式说明 |
| `coach_profile.json` 读失败 | 降级为只读 `memory.json + review_logs` |
| 日期日志读失败 | 继续主流程，不影响回复 |
| 结构化更新失败 | 当前回复照常返回，同时记录错误日志 |
| 图像解析失败 | 提示用户补充文字版指标 |
| 输入信息不足 | 主动追问，而不是继续给建议 |
### 5.7 扩展性设计要点
- 通过新增 skill 继续扩展新场景，而不是把所有规则堆进一个 SOUL
- 通过新增 profile 字段扩展训练项目，而不是推翻整个存储结构
- 通过追加日期日志保留事件细节，而不是把所有信息塞进一个 JSON
- 当 prompt 路由不稳定时，可逐步升级为“轻规则 + LLM”混合路由
- 当单用户验证成功后，再迁移到 Postgres / 多档案方案
---