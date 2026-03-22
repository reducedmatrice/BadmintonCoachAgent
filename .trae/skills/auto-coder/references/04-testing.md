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