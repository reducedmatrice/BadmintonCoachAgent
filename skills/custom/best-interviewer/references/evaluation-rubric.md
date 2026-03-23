# Evaluation Rubric

仅在需要更细评分或更具体追问时读取本文件。

## Scorecard

按 1-5 分记录内部判断：

- Problem framing: 是否清楚业务目标、用户、输入输出与成功标准
- Architecture: 是否能解释 Agent 编排、工具、记忆、降级与边界
- Model understanding: 是否理解幻觉、Prompt、检索、微调、Schema、稳定性
- Engineering rigor: 是否有测试、评测、日志、监控、回归和复盘
- Decision quality: 是否能解释 trade-off，而不是事后合理化
- Ownership: 是否能讲清自己负责的部分、实际改动和结果

## Generic Follow-up Bank

根据回答选择一个继续追问：

- “为什么这个场景必须做 Agent，而不是规则流或普通 RAG？”
- “你们为什么选这个 Agent 架构，而不是 ReAct / Plan-and-Execute / AutoGen 的另一种路线？”
- “工具调用的入参和出参怎么约束？如果模型输出不符合 schema，系统怎么修复？”
- “你们如何判断这是 hallucination 还是上游数据缺失？”
- “长期记忆和当前上下文分别承载什么？你们怎么避免记忆污染？”
- “你们做过哪些失败复盘？最典型的一次线上问题是什么？”
- “延迟和成本是怎么拆账的？优化前后有数字吗？”
- “如果重来一次，你最想改哪一个架构决策？为什么？”

## Project-Specific Follow-ups For This Repo

如果候选人声称参与了当前仓库对应项目，可优先从这些点里选一个：

- “Spec 明确不建议首版新建 LangGraph graph。你们为什么复用 `lead_agent`，这给调试和部署带来了什么收益或限制？”
- “为什么 `coach_profile.json` 不能直接用 `memory.json` 替代？两者边界怎么控制？”
- “为什么日期日志只回看最近 3 份？这个检索优先级是怎么定的？”
- “首版为什么默认 `subagent_enabled=false`？如果未来打开，你最担心什么问题？”
- “Weather MCP 失败时系统如何降级，怎样避免把缺失外部上下文说成既定事实？”
- “你们的 Judge 维度、structured logs 和 pytest 回归之间是如何互相补位的？”

## Strong Evidence

高分回答通常会自然包含这些证据：

- 真实线上或准线上场景，而不是纯 demo
- 明确的输入输出契约、工具接口或 schema 设计
- 具体的 latency / token / cost / success-rate / judge-score 数字
- 至少一个失败案例与修复过程
- 能说清为何不用某个流行框架或方案

## Weak Evidence

低分回答常见模式：

- 大量概念词，几乎没有系统边界与数据流
- “我们用了 LangChain / AutoGen” 但说不清调度逻辑
- 把 Prompt 调一调当成全部优化手段
- 只讲 happy path，没有降级、监控和评测
- 无法区分模型能力问题、系统设计问题和数据问题
