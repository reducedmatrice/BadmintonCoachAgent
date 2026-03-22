# 阶段 A 总结

阶段 A 的目标不是把完整教练能力一次做完，而是先把“这个项目能不能以最小代价站起来”这件事做实。最终选择的路线是复用现有 `lead_agent`，通过 `context.agent_name=badminton-coach` 装配 Coach 身份，而不是新建独立 graph。这样做的核心原因有三个：第一，当前仓库已经具备 custom agent、per-agent memory 和 skills 基础设施，继续沿用现有运行时可以减少分叉；第二，飞书消息链路已经稳定接入 `lead_agent`，只要把 session context 传对，就能把 Coach 放进真实沟通场景；第三，这条路线把复杂度集中在“身份约束、技能边界、领域记忆”上，而不是浪费在重复造底座。

这一阶段实际完成了四类交付。第一，建立了 `badminton-coach` 的 runtime 资产，包括 `config.yaml`、`SOUL.md` 和 `memory.json`，验证了 custom agent 能被正确加载。第二，补齐了 Coach 的身份边界，把语气、追问策略、安全约束和输出结构写进 `SOUL.md`，避免后续实现时回复风格漂移。第三，新增了 Router、Pre-match、Post-match、Health 四个 custom skills，把业务场景拆成清晰的工作流骨架，后面做路由和规则时就不会继续把所有约束都塞进一个 prompt。第四，打通了 Feishu 侧的最小装配约定：`assistant_id` 继续使用 `lead_agent`，通过 `channels.feishu.session.context.agent_name=badminton-coach` 让飞书文本会话默认进入 Coach 身份。

从验证结果看，阶段 A 已经形成一个可解释的最小闭环。A1/A2/A3 相关回归测试已经覆盖了 custom agent 加载、per-agent memory 隔离、skills 发现，以及 Feishu/ChannelManager 对 `agent_name` 的透传。当前还没有真正完成的部分，不在装配层，而在业务层：赛前建议、赛后复盘和结构化档案更新还没有进入可用状态。这也是为什么阶段 B 应该聚焦文本主闭环，而不是继续在装配层反复打磨。

当前残留风险主要有三类。第一，虽然 Feishu 会话已经能进入 Coach 身份，但回复内容还主要依赖 `SOUL.md` 和 skills 提示，缺少领域规则和真实历史数据时，输出仍可能偏泛化。第二，`coach_profile.json` 和日期日志的写回链路还没建立，长期个性化效果目前只停留在基础 memory 层。第三，A2 里的 skills 目前是工作流骨架，还没有细化成稳定的路由判定和提取规则。

阶段 B 的进入条件已经比较明确：一是把 `prematch` 和 `postmatch` 变成可测试的文本路径；二是建立结构化档案和日期日志的读写；三是让下一次赛前建议能够真实引用上一次复盘结果。只要这三件事完成，项目就会从“装配好的 Coach Agent”进入“开始提供连续训练价值”的阶段。
