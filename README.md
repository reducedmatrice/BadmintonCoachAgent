# Badminton-Coach-Agent

Badminton-Coach-Agent 是一个面向羽毛球训练与身体恢复场景的垂直 Agent 项目。它的目标不是做通用聊天，而是构建一个能够持续理解用户训练状态、提供赛前建议、赛后复盘和恢复提醒的个人教练系统。

项目围绕三个高频场景展开：
- 赛前建议：结合近期训练记录、技术弱项、天气和身体状态，给出训练重点、热身建议和风险提醒
- 赛后复盘：将自然语言复盘整理为结构化观察，提炼问题点、进步点和下次训练重点
- 恢复分析：结合疲劳描述和健康截图，输出训练强度与恢复方向建议

## 产品特性

- 持续个性化：不是一次性回答，而是形成“赛前建议 -> 训练 -> 赛后复盘 -> 下次更精准建议”的闭环
- 多层记忆：同时维护叙事型记忆、结构化画像和按日期追加的训练日志
- 多场景 skill 驱动：将赛前、赛后、恢复、路由等能力拆成独立 skills，提升行为稳定性
- 飞书接入：支持在真实 IM 场景中交互，而不是只停留在本地 demo
- 可追溯性：支持 structured logs、离线评测和运行结果回放，便于排障和持续优化

## 技术实现

项目采用 `Harness + Runtime + Channel + Memory + Skills` 的 Agent 架构：

- `Runtime`：负责一次请求的实际执行，包括上下文装配、能力路由、模型调用和结果返回
- `Channel`：负责将飞书消息转换为统一输入结构，并将输出渲染为适合用户消费的卡片或文本
- `Skills`：负责组织赛前建议、赛后复盘、恢复分析等垂直能力，避免所有行为都依赖单一大 prompt
- `Memory`：负责沉淀长期记忆与训练历史，让 Agent 能够跨会话持续个性化

多层记忆设计是这个项目的核心之一：

- `memory.json`：保存叙事型长期记忆，用于保留历史背景和用户偏好
- `coach_profile.json`：保存结构化画像，包括技术弱项、身体状态、训练习惯等稳定特征
- `memory/reviews/YYYY-MM-DD.md`：按日期追加训练和复盘事件，保留可追溯的时间线

运行时会根据当前意图按需装配这些上下文。例如赛前路径会优先读取 profile、最近训练日志和天气信息；赛后路径会优先抽取技术反馈并回写记忆；恢复路径则更关注疲劳和健康相关输入。

## 技术栈

- Python
- LLM Runtime / Agent Harness
- Feishu Channel Integration
- YAML / Markdown 驱动配置
- JSON 文件持久化记忆
- Structured Logging
- Offline Evaluation Scripts
- Pytest

## 工程亮点

- 通过 `skills-driven` 方式组织 Agent 能力，而不是将所有逻辑堆进一个大 prompt
- 通过多层记忆实现“赛后更新、赛前读取”的持续个性化闭环
- 通过 channel 抽象隔离外部消息平台与内部运行时，降低接入耦合
- 通过 structured logs、样本集和评测脚本提升 Agent 系统的可观测性和可迭代性
- 采用 `spec-driven + vibe coding` 的开发方式，先定义目标、阶段和验收标准，再用 AI 生成和收敛实现，提升输出稳定性

## 项目结构

- [开发规格目录](./dev-spec)：按阶段归档的 spec、tasks 与 checklist
- [Coach 运行时资产](./backend/.deer-flow/agents/badminton-coach)：Agent 配置、记忆与角色定义
  其中默认教练人格资产位于 `meta.json`、`persona.md` 与 `SOUL.md`
- [自定义 Skills](./skills/custom/badminton-coach)：赛前、赛后、恢复和路由能力
- [Channel 层](./backend/app/channels)：渠道接入、消息转换、提醒与日志
- [Coach 领域逻辑](./backend/packages/harness/deerflow/domain/coach)：赛前、赛后、恢复、档案等核心实现
- [自动化测试](./backend/tests)：关键路径回归测试
- [文档与评测资料](./docs)：阶段总结与评测样本

## 快速开始（飞书本地开发）

启动前先确保 `.env.feishu.local` 已配置好模型和飞书凭证，然后：

```bash
# 加载环境变量（每次新终端都需要）
source .env.feishu.local

# 确认模型变量已正确加载
echo $DEERFLOW_OPENAI_MODEL   # 应输出 qwen3.5-plus

# 停掉旧进程并重启整套服务（推荐）
make stop
./scripts/run-feishu-local.sh --watch-logs
```

服务启动后访问 `http://localhost:3000` 验证前端，`http://localhost:8001` 验证网关。

如需分别手动启动三个进程（LangGraph / Gateway / Frontend）：

```bash
# 终端 1：LangGraph
cd backend && NO_COLOR=1 uv run langgraph dev --no-browser --allow-blocking --reload

# 终端 2：Gateway
cd backend && PYTHONPATH=. uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 --reload

# 终端 3：Frontend
cd frontend && pnpm run dev
```

**常见问题**
- 模型请求 500：确认 `DEERFLOW_OPENAI_MODEL=qwen3.5-plus`，模型名拼写不能有连字符 `-`
- 飞书连接失败：确认 VPN 已关闭，且 `ALL_PROXY` 等代理变量已 unset
- 飞书事件报 `processor not found`：去飞书开放平台后台取消 `im.message.reaction.created_v1` 事件订阅

## 运行测试

```bash
cd backend
uv run pytest -q tests/test_channels.py tests/test_skills_loader.py tests/test_coach_prematch_rules.py
```

如果你想先了解整体设计和阶段划分，建议先看 [`dev-spec/`](./dev-spec)，默认从最新版本阶段开始。
