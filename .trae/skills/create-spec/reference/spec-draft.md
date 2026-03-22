
项目概述 + 核心特点

该项目参考著名开源项目deerflow，采用harness + app的架构拆分。主要在agent层对deerflow的agent进行定制化，实现“羽毛球教练 + 身体指引 Coach”的功能。

羽毛球教练 + 身体指引 Coach”的 idea 非常棒！它不仅切中了程序员久坐、运动恢复的痛点，而且在技术实现上，完美契合了你想要展示的 **LangGraph 编排、Skills 驱动、MCP 外部上下文、以及跨 Session 记忆** 这几大核心能力。


我们不需要把项目做得像 DeerFlow 那么重，我们可以对它进行“外科手术式”的裁剪，只保留最核心的运行环境，专注于业务逻辑的实现。


### **1. 核心架构：基于 LangGraph 的单agent“状态机”流转**
你可以把这个 Agent 看作一个带有多个入口的状态机。LangGraph 的优势在于它能很好地处理“循环”和“记忆”。

- **Pre-match Node (赛前提醒)**：当你早上在飞书打卡或者询问“今天打球注意什么”时，Agent 触发此节点。它会从**长期记忆**中提取你上一次的复盘记录（比如：杀球压腕不够、后场步法慢），并结合**天气 MCP**（如果太热提醒补水）给出建议。
- **Post-match Node (赛后复盘)**：当你发送语音或文字复盘时，触发此节点。LLM 会提取技术要点，并更新到你的**长期记忆**中。
- **Health Analysis Node (身体数据)**：当你上传心率、卡路里截图时，调用 **Skills (OCR)** 识别数据，结合你的年龄、上班时长等背景信息，给出恢复建议。

### **2. Skills 驱动：处理多模态输入**
正如你所想，输入是多样化的，我们可以定义几个专门的 Skill：

- **`skill-vision-ocr`**：专门处理你运动手表的截图。它不只是简单的文字识别，还要能理解“心率区间”、“静息心率”与“疲劳度”的关系，输出结构化的 JSON。
- **`skill-voice-processor`**：处理飞书发送的语音复盘。利用 STT 转化为文字，再交给 LLM 进行语义提取。
- **`skill-badminton-knowledge`**：内置一些羽毛球专业术语库，防止 LLM 在处理复盘文字时把“劈吊”理解成别的词。

### **3. 记忆管理：跨 Session 的核心体现**
这是你最看重的点，我们可以分为两个层级：

- **短期记忆 (Checkpoints)**：利用 LangGraph 的 `checkpointer`，记录当前对话的上下文（比如你刚说完今天想练步法，接下来的几句对话它都记得这个目标）。
- **长期记忆 (Memory Store)**：
    - **技术档案**：记录你的弱点、进步曲线、常用球路。
    - **身体档案**：记录你的伤病史、耐力上限、近期疲劳趋势。
    - **实现方式**：可以利用 DeerFlow 原有的 `memory` 模块，或者在后端挂一个轻量级的持久化数据库（如 SQLite），在每个 Session 开始时，通过 `read_memory` 节点将其注入到 `System Prompt` 中。

### **4. MCP (Model Context Protocol) 的妙用**
MCP 的核心是让 Agent 拥有“感知外部世界”的能力。在你的教练场景下：

- **Weather MCP**：如果你在室外场打球，它可以感知气温。如果是 35 度高温，它会强制要求你缩短每局时间。
- **Calendar MCP**：读取你的日程。如果你下午有个高强度会议，它会建议你早上的打球强度控制在 60% 以内，避免下午“断电”。
- **Notion/Obsidian MCP**：如果你有自己写球评的习惯，Agent 可以直接从你的笔记库里同步信息。

### **5. 飞书作为载体：真正的“生产环境”感**
飞书的卡片消息（Interactive Cards）非常适合展示运动数据分析结果。

- 它可以发给你一个漂亮的卡片，上面有你本周的运动心率曲线图（生成的图片地址）。
- 它可以通过“延时任务”在你要去打球前半小时，主动给你弹个窗：“Tom，别忘了今天要多注意后场侧身！”

对性能做评估：
生成内容的延迟。
token的使用量
产出的水平 - llm as a judge
评估路线是否合理



**核心技术栈**：
基本架构Lead Agent + Subagent + harness的结构。

- **LangGraph**：实现记忆管理。状态机流转，记忆管理。
- **Skills (OCR, STT, LLM)**：处理多模态输入。
- **MCP (Weather, Calendar, Notion/Obsidian)**：感知外部环境。
- **飞书 API**：与用户交互。


根据我对项目架构的详细分析，以下是 note-agent (基于 DeerFlow) 的架构总结：

---

# 技术架构设计
以下内容基本与 DeerFlow 架构保持一致，只是在 Agent 层上进行了定制化。

#### 目录结构：
```
backend/
├── packages/
│   └── harness/                          # ✅ Harness 层（可发布的 Python 包）
│       ├── pyproject.toml               # 包定义：deerflow-harness
│       └── deerflow/                     # Python 包根（import 前缀: deerflow.*）
│           ├── agents/                  # Agent 工厂、middleware、state、memory
│           ├── subagents/               # 子 agent 委派系统
│           ├── sandbox/                 # 沙箱执行环境 （可选）
│           ├── tools/                   # 工具注册与发现
│           ├── mcp/                     # MCP 协议集成
│           ├── skills/                   # 技能加载、解析 
│           ├── models/                  # LLM 模型工厂
│           ├── community/               # 社区工具（tavily、jina 等）（删掉）
│           └── client.py                # 嵌入式 Python 客户端
│
├── app/                                 # ✅ App 层（不打包的应用代码）
│   ├── gateway/                         # FastAPI REST API
│   │   ├── routers/                     # API 路由（models, mcp, skills, uploads, artifacts 等）
│   │   └── app.py                      # FastAPI 应用入口
│   └── channels/                        # IM 平台集成（飞书、Slack、Telegram）
│
├── langgraph.json                       # LangGraph Server 配置
└── tests/                              # 测试代码
```

#### 关键设计原则：

| 原则 | 说明 |
|------|------|
| **单向依赖** | App → Harness（App 依赖 Harness，Harness 不依赖 App） |
| **Harness 可发布** | `deerflow-harness` 是一个独立的 Python 包，可单独安装使用 |
| **App 不打包** | App 是项目内部代码，直接运行（`PYTHONPATH=. uvicorn app.gateway.app:app`） |

---

#### 实际的编排机制：

DeerFlow 使用的是 **Lead Agent + Subagent** 的主从架构，而不是传统的 coordinator 模式：

```
┌─────────────────────────────────────────────────────────────┐
│                      Lead Agent                             │
│  (make_lead_agent in agent.py)                              │
│                                                             │
│  - 核心决策 agent                                            │
│  - 使用 middleware chain 处理请求                            │
│  - 通过 task_tool 调用 subagent                             │
└──────────────────────────┬──────────────────────────────────┘
                           │ task_tool 调用
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Subagent System                          │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────────────────────┐│
│  │ SubagentExecutor │───▶│ general-purpose subagent         ││
│  │  (executor.py)   │    │ (复杂多步骤任务)                  ││
│  └─────────────────┘    └─────────────────────────────────┘│
│  ┌─────────────────┐    ┌─────────────────────────────────┐│
│  │                 │───▶│ bash subagent                   ││
│  │                 │    │ (命令执行专家)                    ││
│  └─────────────────┘    └─────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

### 3. 核心架构组件

#### Agent 构建流程：

```
make_lead_agent(config)
    │
    ├── create_chat_model()        # 模型工厂
    ├── get_available_tools()       # 工具系统（内置 + MCP + 社区）
    │
    └── _build_middlewares()        # Middleware 链
        │
        ├── ThreadDataMiddleware     # 初始化 workspace/uploads/outputs
        ├── UploadsMiddleware       # 处理上传文件
        ├── SandboxMiddleware       # 获取沙箱环境
        ├── SummarizationMiddleware # 上下文压缩
        ├── TitleMiddleware         # 自动生成标题
        ├── TodoListMiddleware      # 任务跟踪（plan mode）
        ├── MemoryMiddleware        # 记忆系统
        ├── ViewImageMiddleware     # 视觉模型支持
        ├── LoopDetectionMiddleware # 循环检测
        ├── ClarificationMiddleware # 需求澄清
        └── ...
```

#### Subagent 执行流程：

```
Lead Agent 调用 task_tool
    │
    ▼
SubagentExecutor.execute_async()
    │
    ├── 在 ThreadPoolExecutor 中异步执行
    ├── 创建独立 agent 实例（使用不同 system prompt）
    └── 后台轮询结果，返回给 Lead Agent
```

---

### 4. 技术栈总结

| 层级 | 技术 |
|------|------|
| **Agent 框架** | LangGraph + LangChain |
| **模型集成** | OpenAI / Anthropic / DeepSeek / Google GenAI |
| **沙箱** | agent-sandbox (Local / Docker / K8s) |（可选，目前采用本地）
| **工具** | 内置工具 + MCP 适配器 + 社区工具 (Tavily, Jina, Firecrawl) |（暂时不用社区工具）
| **API** | FastAPI (Gateway) + LangGraph Server |
| **前端** | Next.js + React |


--- 
### **包装建议（针对简历/面试）**
既然你希望这个项目能体现能力，我们在设计方案时可以强调以下几点：

1.  **“多模态 RAG”**：不仅仅是搜文档，而是从运动截图和复盘语音中提取结构化知识进行检索。
2.  **“主动式 Agent”**：通过 Cron 或事件驱动，让 Agent 从“被动问答”转变为“主动关怀”，体现对业务场景的深度理解。
3.  **“轻量化 Harness”**：展示你如何精简了复杂的开源项目，保留了其高性能的 Sandbox 和扩展机制，定制化成了垂直领域的教练 Agent。