# BadmintonCoachAgent

BadmintonCoachAgent 是基于 `note-agent` / DeerFlow 基座做的垂直场景定制项目，目标是把通用 Agent 能力收敛到一个真实可用的「羽毛球教练 + 身体恢复建议」助手。项目复用现有的 `lead_agent`、memory、skills、MCP 和 IM channel 机制，不新增 graph，而是通过 `context.agent_name=badminton-coach` 装配 Coach 身份。

当前版本优先解决三个核心场景：
- 赛前提醒：根据近期复盘、天气、训练重点和疲劳状态，给出今天该练什么、怎么热身、有哪些风险点。
- 赛后复盘：把用户的文本总结转成结构化观察，沉淀为下次训练可复用的记忆。
- 身体恢复：结合主观疲劳描述与后续图片数据，输出恢复建议和强度控制建议。

项目的核心设计是混合记忆与低侵入扩展：
- Agent 级 `memory.json` 保存长期叙事记忆。
- `coach_profile.json` 负责稳定的结构化运动档案。
- `memory/reviews/YYYY-MM-DD.md` 追加训练与比赛日志。
- `skills/custom/badminton-coach/` 下的 Router、Pre-match、Post-match、Health skill 负责场景边界与工作流提示。

当前实现约束也很明确：
- `backend/langgraph.json` 只有 `lead_agent` 一个入口。
- 飞书首版只做文本闭环。
- 多模态图片/语音入站和主动提醒放到后续阶段。
- Coach 给出的是训练与恢复建议，不提供医疗诊断。

当前阶段进度：
- A1 已完成：`badminton-coach` custom agent 已能通过 `agent_name` 装配，并有最小回归测试。
- A2 已完成：补齐 Coach `SOUL.md` 与 4 个 custom skills 骨架，明确回复风格、追问策略和安全边界。
- 后续优先做 A3/B1/B2：跑通飞书文本回复、赛前建议和赛后复盘主闭环。

## 目录

- 主 spec：[`dev-spec.md`](./dev-spec.md)
- Coach runtime 资产：[`backend/.deer-flow/agents/badminton-coach`](./backend/.deer-flow/agents/badminton-coach)
- Coach skills：[`skills/custom/badminton-coach`](./skills/custom/badminton-coach)
- 后端测试：[`backend/tests`](./backend/tests)

## 快速开始

1. 生成配置：`make config`
2. 配置模型与环境变量
3. 本地开发启动：`make dev` 或 Docker 启动：`make docker-start`
4. 运行针对性测试：

```bash
cd backend
uv run pytest -q tests/test_custom_agent.py tests/test_skills_loader.py tests/test_channels.py
```

如果你要看当前开发计划和阶段目标，直接从 `dev-spec.md` 开始。
