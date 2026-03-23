# Developer Specification (DEV_SPEC)
> 版本：1.1 - 羽毛球教练 + 身体指引 Coach
## 目录
- 项目概述
- 核心特点
- 技术选型
- 测试方案
- 系统架构与模块设计
- 项目排期
- 可扩展性与未来展望
---
## 1. 项目概述
### 1.1 项目定位
本项目基于现有 `note-agent` 仓库做垂直场景定制，目标是在 DeerFlow 现有的 `Harness + App` 基座之上，落地一个可真实使用、可持续迭代的 **羽毛球教练 + 身体指引 Coach Agent**。
本项目不追求复刻 DeerFlow 的完整能力，而是采用“低侵入增量开发”方式，只补齐与教练场景直接相关的能力：
- 赛前提醒：根据近期复盘、天气、工作负荷给出训练重点与风险提醒
- 赛后复盘：把用户赛后文字复盘转为结构化技术反馈
- 身体恢复：结合主观疲劳描述与后续图片数据，输出恢复建议
- 跨 Session 记忆：通过 per-agent `memory.json`、结构化 `coach_profile.json`、按日期追加的训练日志持续追踪技术弱项、身体状态和偏好
- 飞书交互：把 Agent 放进真实沟通场景，而不是只停留在 Web Demo
### 1.2 项目目标
本项目有三层目标。
**产品目标**
- 让用户在飞书里获得可执行、连续性的训练与恢复建议
- 形成“赛前提醒 -> 训练 -> 赛后复盘 -> 下次提醒更准”的闭环
- 在真实使用中验证个性化建议是否优于通用健身/羽毛球建议
**工程目标**
- 体现 `LangGraph runtime`、`custom agent`、`skills`、`MCP`、`memory`、`Feishu channel` 的组合设计能力
- 尽量复用现有仓库能力，不重写底座
- 输出可测试、可评估、可扩展的工程规范，而非停留在 demo prompt
**学习/面试目标**
- 首版优先服务“面试展示技术亮点”，不是产品完备度
- 每个阶段结束都产出 1000-2000 字阶段总结，包含：核心知识点、方案选择理由、踩坑、残留风险、下一阶段关注点
- 阶段总结要能单独作为复盘材料，帮助你解释为什么这么设计，而不是只会展示结果
### 1.3 目标用户与使用场景
#### 1.3.1 目标用户
- 主用户：你本人，程序员背景、久坐、高压工作环境、羽毛球爱好者
- 次用户：与主用户画像相近的内部试用者
#### 1.3.2 典型使用场景
| 场景 | 用户输入 | Agent 输出 |
|------|----------|------------|
| 赛前咨询 | “今晚打球，注意什么？” | 当日训练重点、热身提醒、风险点 |
| 赛后复盘 | “今天后场步法还是慢，反手有进步” | 技术总结、下次训练重点、记忆更新 |
| 身体恢复 | “今天感觉很累，心率也高” 或上传运动数据 | 恢复建议、强度控制建议 |
| 主动关怀 | 打球前 30 分钟 | 主动提醒卡片、重点提示 |
### 1.4 MVP 范围
本版 spec 按“先做出一个可演示、可讲清楚技术亮点的简单 demo”来定义 MVP。首版重点不是功能全，而是主闭环、扩展性和可解释性。
#### 1.4.1 本期必须完成
- 基于现有 `lead_agent`，通过 `configurable.agent_name=badminton-coach` 装配独立 Coach Agent
- 飞书文本消息闭环跑通
- `Pre-match` 与 `Post-match` 两条主路径可用
- 读取并更新 Agent 级长期记忆
- 引入结构化领域档案 `coach_profile.json`
- 引入按日期追加的训练日志 `memory/reviews/YYYY-MM-DD.md`
- 天气上下文接入并提供降级逻辑
- 响应延迟、token 成本、LLM Judge 质量评分、路由合理性评估可追踪
#### 1.4.2 本期建议完成
- `Health Analysis` 先通过 Web Workspace 上传图片进行验证
- 输出结构化运行日志，支持后续复盘和简单统计
- 完成 A、B、C 三阶段后分别输出阶段总结
#### 1.4.3 本期不纳入 MVP
- 飞书入站图片/语音解析
- Calendar / Notes MCP 接入
- 主动提醒调度器
- 复杂周计划排程
- 多用户权限与租户隔离
- 商业化计费、运营后台、复杂报表
- 重写 DeerFlow 的 graph 注册方式或新增独立 LangGraph graph
### 1.5 当前已知约束
这些约束不是建议，而是当前仓库事实，spec 必须围绕它们设计。
- `backend/langgraph.json` 当前只有一个图入口：`lead_agent`
- `make_lead_agent()` 已支持 `configurable.agent_name`，因此 Coach 适合实现为 **custom agent**，而不是额外 graph
- `FeishuChannel` 当前入站仅解析文本消息，不处理图片、文件、语音
- 仓库中的 `skills` 本质上是 **提示词工作流与参考资料**，不是自动可执行 Python 插件
- 当前长期记忆机制是基于 `memory.json` 的通用叙事记忆，不天然适合保存稳定的运动数值趋势
- 当前仓库没有现成的业务定时调度器，因此“主动提醒”必须延期或由外部调度触发
### 1.6 关键假设
- 假设 A1：MVP 主入口为飞书文本，图片/语音先不强行纳入飞书首版
- 假设 A2：Coach 提供的是运动建议与恢复建议，不提供医疗诊断
- 假设 A3：首版默认单用户使用，不考虑多人档案冲突
- 假设 A4：如果 Weather MCP 不可用，系统仍应给出降级建议，而不是报错中断
- 假设 A5：默认用中文回复，必要时保留英文技术名词
- 假设 A6：首版优先展示“记忆设计、路由设计、评估设计”，而不是 IM 多模态覆盖率
### 1.7 成功标准
#### 1.7.1 功能成功标准
- 用户能在飞书中完成赛前咨询与赛后复盘
- 下一次赛前建议能引用上一次复盘中的技术弱项
- 天气上下文会真实影响建议内容
- 赛后复盘会同时更新叙事记忆、结构化档案和日期日志
#### 1.7.2 质量成功标准
- 关键路径成功率 >= 95%
- 赛前/赛后文本请求 P50 延迟 <= 8s，P95 延迟 <= 20s
- LLM Judge 平均分 >= 4.2/5
- 路由合理性准确率 >= 85%
- 无“把缺失数据当既定事实”的严重幻觉
这些指标的量化方式如下：
- 成功率：通过自动化样本集统计 `通过样本数 / 总样本数`
- 延迟：从 structured logs 中统计开始时间、首个可见输出时间、完成时间，计算 P50/P95
- Judge 质量：对固定样本集按 1-5 分 rubric 打分，取平均分和最低分
- 路由准确率：`预测主路由 == 标注主路由` 的比例
- 幻觉红线：人工抽检和失败样本集回归中不得出现“虚构身体指标”“虚构外部上下文”“无依据医学判断”
---
## 2. 核心特点
### 2.1 三条核心业务路径
#### 2.1.1 Pre-match Coach（赛前提醒）
**触发条件**
- 用户发送“今天打球注意什么”“今晚要不要练杀球”“打球前提醒我一下”等文本
- 主动提醒能力上线后，也可由外部调度触发
**输入**
- 当前文本意图
- Agent 长期记忆 `memory.json`
- 结构化教练档案 `coach_profile.json`
- 最近日期日志 `memory/reviews/YYYY-MM-DD.md`
- Weather MCP 数据
**输出**
- 今日训练重点 1-3 条
- 热身建议
- 强度/补水/恢复风险提醒
- 一条可执行的训练动作建议
**必须具备的个性化依据**
- 上次训练暴露的弱项
- 最近两周的训练主题
- 当天气温或工作负荷
#### 2.1.2 Post-match Review（赛后复盘）
**触发条件**
- 用户发送赛后总结文本
- 后续 Phase 2 可扩展到飞书语音/图片
**输入**
- 用户复盘文本
- 当前 Agent 记忆
- 术语规范化规则
**输出**
- 技术观察清单
- 进步点与退步点
- 下次训练优先级
- 是否需要更新长期记忆与结构化档案
**更新目标**
- 技术弱项变化
- 训练关注点变化
- 用户对建议风格的偏好
#### 2.1.3 Health Analysis（身体数据分析）
**首版定位**
- 首版作为增强能力，不作为飞书文本 MVP 的必交项
- 建议先在 Web Workspace 通过上传截图验证
**输入**
- 心率/卡路里/运动截图
- 用户主观描述，如“今天特别累”“腿有点紧”
- 历史恢复档案
**输出**
- 疲劳等级
- 恢复建议
- 次日训练强度建议
- 风险提示
**边界**
- 不输出明确医疗诊断，可以给出恢复与就医建议边界
- 出现胸痛、眩晕、持续剧痛等关键词时直接建议暂停运动并寻求专业帮助
### 2.2 路由能力要求
Coach 必须先判断用户输入属于哪类意图，再决定调用哪些能力。首版不只要有主路由，还要有更细的子意图粒度，并尽量利用上下文和 memory 补齐信息，而不是动不动就追问。
#### 2.2.1 主路由与子意图
| 主路由 | 子意图 | 最低必要信息 | 优先补齐来源 |
|--------|--------|--------------|--------------|
| `prematch` | 今日打球注意点、训练重点、场地/天气影响、赛前热身 | 今日是否打球、想练什么、近期弱项 | 当前线程上下文 -> `coach_profile.json` -> `memory.json` |
| `postmatch` | 技术复盘、进步/退步、下次训练目标 | 今天发生了什么、用户主观判断、动作/场景描述 | 当前消息 -> 当前线程最近 5 轮 -> 日期日志 |
| `health` | 疲劳判断、恢复建议、强度下调 | 主观疲劳、心率/卡路里/睡眠等线索 | 当前消息 -> `coach_profile.json.health_profile` |
| `fallback` | 总结、规划、泛化建议、信息不足 | 任务目标 | 当前线程上下文 -> `memory.json` |
#### 2.2.2 路由决策顺序
1. 先读当前消息，判断主路由候选
2. 读取当前线程最近 5 轮消息，识别是否已有补充信息
3. 读取 `coach_profile.json`，尝试补齐技术弱项、疲劳状态、偏好
4. 读取 `memory.json` 与最近 3 份日期日志，补齐长期背景
5. 若仍缺关键信息，再发起最小追问
#### 2.2.3 追问策略
- `prematch` 缺信息时优先追问：今天是单打还是双打、室内还是室外、想练什么
- `postmatch` 缺信息时优先追问：今天最明显的问题发生在哪个环节、是体能问题还是动作问题
- `health` 缺信息时优先追问：是主观疲劳还是有具体数据、是否有明显疼痛或不适
- 追问必须一次只问 1-2 个高价值问题，避免问卷化
#### 2.2.4 记录要求
- 每次请求必须记录主路由、子意图、是否追问、是否使用了 memory 补齐
- 路由结果进入评估日志，支持后续统计准确率和误判类型
### 2.3 多模态策略
多模态是项目亮点，但必须基于当前仓库事实分阶段推进。
#### 2.3.1 Phase 1
- 飞书：只支持文本
- Web Workspace：支持图片上传，可借助现有上传能力和视觉模型做结构化解析
#### 2.3.2 Phase 2
- 扩展 `backend/app/channels/feishu.py`，支持飞书图片/文件/语音消息入站
- 对接 STT/OCR 能力，把多模态也放进飞书主入口
#### 2.3.3 为什么这样分阶段
- 当前飞书入站代码只解析 `content["text"]`
- 当前 skills 系统适合管理工作流知识，不适合直接承担文件下载、语音转写等执行逻辑
- 如果强行把语音/图片放进首版 MVP，会显著拉高实现复杂度与不确定性
### 2.4 记忆体系
本项目采用“短期会话记忆 + 通用长期记忆 + 结构化档案 + 日期日志”的混合方案。这一设计会参考 OpenClaw 的记忆理念，但不会原样照搬它的全部目录结构或检索链路。
#### 2.4.1 短期记忆
- 依赖现有 `checkpointer`
- 用于保存当前对话上下文、澄清结果、当前训练目标
- 生命周期：单线程、多轮会话
- 可直接复用现有 LangGraph 状态持久化能力
#### 2.4.2 通用长期记忆
- 依赖现有 `memory.json`
- 作用：把用户背景、偏好、训练关注点注入 prompt
- 优点：复用现有系统，低侵入，适合叙事性背景
- 局限：不适合高稳定度的结构化数值趋势
#### 2.4.3 结构化教练档案
新增 `coach_profile.json` 作为教练领域的 canonical data，保存稳定的训练与恢复结构化信息。
建议结构如下：
```json
{
  "athlete_profile": {
    "dominant_hand": "right",
    "experience_level": "intermediate",
    "constraints": ["久坐", "工作日高强度脑力工作"],
    "injury_history": []
  },
  "tech_profile": {
    "focus_topics": ["后场步法", "反手压腕"],
    "weaknesses": [
      {
        "name": "后场步法回位慢",
        "severity": 0.8,
        "trend": "stable",
        "last_seen_at": "2026-03-22",
        "evidence": "连续两次复盘提到后场回位慢"
      }
    ],
    "strengths": [],
    "recent_reviews": []
  },
  "health_profile": {
    "fatigue_level": "medium",
    "risk_flags": [],
    "recent_metrics": []
  },
  "preferences": {
    "reply_style": "concise",
    "preferred_language": "zh-CN",
    "wants_proactive_reminder": true
  },
  "last_updated_at": "2026-03-22T00:00:00Z"
}
```
#### 2.4.4 日期日志
为了吸收 OpenClaw 里“按时间沉淀长期记忆”的优点，建议新增追加式训练日志：
- 路径：`backend/.deer-flow/agents/badminton-coach/memory/reviews/YYYY-MM-DD.md`
- 每次 `postmatch` 完成后追加一条摘要
- 每条日志至少包含：时间、场景、技术问题、进步点、身体状态、下次重点
- 日志是“原始事实沉淀”，`coach_profile.json` 是“结构化聚合结果”，两者用途不同
#### 2.4.5 检索优先级
首版检索优先级如下：
1. 当前线程上下文
2. `coach_profile.json`
3. 最近 3 份 `memory/reviews/YYYY-MM-DD.md`
4. `memory.json`
这样做的原因是：
- `coach_profile.json` 适合回答“当前最重要的稳定状态是什么”
- 日期日志适合回答“最近具体发生了什么”
- `memory.json` 适合回答“长期偏好和背景是什么”
#### 2.4.6 为什么不完全照搬 OpenClaw
- OpenClaw 的目录、检索工具链更偏通用型 Agent 工作空间
- 这里的单用户教练场景更强调低复杂度和可解释性
- 首版只吸收它的核心思想：短期记忆压缩、长期记忆沉淀、日期化事件日志
### 2.5 安全与边界控制
Coach 的建议必须遵守以下规则：
- 不伪造未提供的身体数据
- 不把常识性建议伪装成“精确医学判断”
- MCP 不可用时明确提示“未获取到外部上下文”
- 用户描述伤病或高风险症状时，不给继续高强度训练建议
- 遇到不明确输入时优先追问，而不是直接给教练结论
### 2.6 评估导向设计
本项目不是只看“能不能答”，而是要持续衡量四类指标：
- 响应延迟
- token 消耗
- 内容质量
- 路由合理性
其中“内容质量”至少覆盖：
- 是否个性化
- 是否引用历史上下文
- 是否可执行
- 是否避免过度自信
首期不建议为了这些指标额外接 LlamaIndex 可视化。首版目标是先把指标以 **structured logs + JSON/Markdown 报告** 的形式落下来，保证可追踪、可复盘。后续如果需要 dashboard，再考虑接可视化层。
---
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
## 4. 测试方案
### 4.1 设计理念：测试驱动开发（TDD）
Coach 项目必须以行为测试为核心，而不是“写完后看看像不像能用”。
核心原则：
- 先定义输入与输出契约，再写实现
- 关键场景一律有自动化回归
- 外部依赖默认 Mock
- 评估不仅覆盖正确性，也覆盖可用性与个性化
### 4.2 测试分层策略
#### 4.2.1 单元测试（Unit Tests）
**目标**
- 保证最小逻辑单元稳定
- 快速发现路由、结构化更新、提示模板退化
**重点覆盖**
- 路由分类逻辑
- `coach_profile.json` 合并与更新规则
- 日期日志追加与检索规则
- 赛前建议规则分支
- 天气阈值判断
- 术语标准化
- 记忆注入格式化
**建议新增测试文件**
- `backend/tests/test_coach_profile.py`
- `backend/tests/test_coach_router.py`
- `backend/tests/test_coach_prematch_rules.py`
- `backend/tests/test_coach_postmatch_extraction.py`
- `backend/tests/test_coach_health_rules.py`
#### 4.2.2 集成测试（Integration Tests）
**目标**
- 验证跨模块协作是否符合预期
**重点覆盖**
- `ChannelManager` 是否能正确把 `agent_name=badminton-coach` 传入运行上下文
- `make_lead_agent()` 是否能加载 per-agent SOUL 和 per-agent memory
- 赛后复盘后，叙事记忆、结构化档案、日期日志是否同步更新
- Weather MCP 失败时是否按降级逻辑返回
- Feishu streaming card 是否正确更新并在最终态打 `DONE`
**建议新增/扩展测试文件**
- `backend/tests/test_channels.py`
- `backend/tests/test_custom_agent.py`
- `backend/tests/test_memory_prompt_injection.py`
- `backend/tests/test_coach_integration_flow.py`
#### 4.2.3 端到端测试（End-to-End Tests）
**目标**
- 模拟真实用户完整链路
**首版 E2E 核心场景**
| 场景 | 输入渠道 | 预期 |
|------|----------|------|
| E2E-1 | 飞书文本赛前咨询 | 生成个性化赛前建议卡片 |
| E2E-2 | 飞书文本赛后复盘 | 生成复盘总结并写回记忆 |
| E2E-3 | Web Workspace 图片上传 | 解析截图并生成恢复建议 |
**暂不纳入首版 E2E**
- 飞书语音入站
- 飞书图片/文件入站
- 主动定时提醒
### 4.3 评估数据集设计
为了衡量“产出的水平”和“路由是否合理”，需要构建离线样本集。
#### 4.3.1 样本分类
- `prematch_simple`：信息充分的赛前咨询
- `prematch_missing_context`：缺少关键信息，需要追问
- `postmatch_technical`：纯技术复盘
- `postmatch_mixed`：技术 + 身体感受混合
- `health_subjective`：只有主观疲劳描述
- `health_visual`：带截图的身体数据分析
- `unsafe_medical`：包含潜在医疗风险描述
#### 4.3.2 样本规模建议
- MVP 最少 30 条
- 建议 50 条以上
- 每类至少 5 条
#### 4.3.3 Judge 维度
| 维度 | 说明 | 目标 |
|------|------|------|
| Personalization | 是否引用历史记忆与用户特征 | >= 4/5 |
| Actionability | 是否给出可执行建议 | >= 4/5 |
| Correctness | 是否符合输入事实，不乱编 | >= 4.5/5 |
| Safety | 是否避免危险建议 | 必须通过 |
| Route Fitness | 是否选对主路径 | >= 85% |
### 4.4 性能与成本评估
必须记录以下指标：
- 请求开始到首个可见响应时间
- 请求完成总耗时
- prompt tokens / completion tokens / total tokens
- MCP 调用次数与失败率
- 平均每类场景成本
- 是否命中 `coach_profile.json`
- 是否命中日期日志
建议门槛：
- `prematch` 平均 total tokens <= 6000
- `postmatch` 平均 total tokens <= 8000
- Health 图片场景可放宽，但应记录单次成本
首期输出形式：
- 结构化日志
- 每阶段汇总 Markdown
- 可选 JSON/CSV 导出
不作为首期目标：
- 实时 dashboard
- LlamaIndex 可视化面板
### 4.5 测试工具链与 CI/CD 集成
建议测试命令以“最快相关检查优先”为原则。
#### 4.5.1 快速回归
```bash
cd backend && pytest -q tests/test_custom_agent.py tests/test_channels.py tests/test_memory_prompt_injection.py
```
#### 4.5.2 Coach 相关回归
```bash
cd backend && pytest -q tests/test_coach_profile.py tests/test_coach_router.py tests/test_coach_integration_flow.py
```
#### 4.5.3 发布前完整验证
```bash
cd backend && pytest -q
```
### 4.6 验收红线
以下任一不通过，则不允许进入“可演示版本”：
- 赛前建议无法引用历史弱项
- 赛后复盘不能稳定更新记忆
- 外部上下文失败会导致整体报错
- Health 场景输出带有明显医疗诊断口吻
- Judge 质量均分低于 4.0/5
---
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
- [ ] C4 [doc] 产出阶段总结（1000-2000 字）
#### 阶段 D：评估与增强
- [ ] D1 跑通 Web 图片分析链路
- [ ] D2 建立离线评测样本集
- [ ] D3 建立延迟 / token / Judge 指标输出
- [ ] D4 [doc] 产出阶段总结（1000-2000 字）
#### 阶段 E：Phase 2
- [ ] E1 扩展飞书图片/语音/文件入站
- [ ] E2 增加主动提醒调度能力
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
