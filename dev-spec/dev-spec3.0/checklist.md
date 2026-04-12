# Coach Multimodal Intake 3.0 Checklist

## Phase 1：飞书图片入站与原图获取

- [ ] 飞书图片消息不再固定退化为占位文本
- [ ] coach runtime 能拿到可消费的图片输入或临时文件句柄
- [ ] 原图获取失败存在明确降级策略
- [ ] 默认不做长期原图存储
- [ ] 原图获取位置固定在 channel 侧

## Phase 2：多模态抽取与强 Schema 校验

- [ ] 运动截图结构化 Schema 已明确
- [ ] 多模态抽取主链路采用 VLM，而非纯 OCR
- [ ] 核心字段抽取范围已明确
- [ ] 低置信度与缺失字段分支已定义
- [ ] 抽取失败不会强行进入 profile 写回
- [ ] 多模态抽取使用单独视觉模型配置

## Phase 3：事件证据写回与 canonical state merge

- [ ] 单次运动明细写入 `memory/reviews/YYYY-MM-DD.md`
- [ ] `coach_profile.json` 只保留聚合后的稳定状态
- [ ] `health_profile` 写回边界清晰
- [ ] 低置信度结果不会直接更新 profile
- [ ] 不新增与 Memory 2.2 冲突的落盘路径

## Phase 4：状态回忆与回答表达

- [ ] `CoachIntakeMiddleware` 能装配最近一次相关身体状态
- [ ] `health` 场景可稳定引用最近一次健康/运动记录
- [ ] `prematch` 场景可在高疲劳 / 高负荷时主动 recall
- [ ] recall 表达使用回忆式措辞，不伪装成实时事实
- [ ] recall 失败不会阻断主回答

## Phase 5：测试、观测与灰度验证

- [ ] 新增单元测试覆盖多模态抽取与写回边界
- [ ] 新增集成测试覆盖“发图 -> 写回 -> 下次 recall”
- [ ] structured logs 能区分图片获取失败、抽取失败、写回跳过
- [ ] 离线评测新增图像输入与 recall 样本
- [ ] 存在可执行的回滚预案
- [ ] 同步抽取链路延迟可被观测

## Phase 6：缓存治理与清理

- [ ] 临时图片缓存默认保留 30 天
- [ ] 删除前会校验 `memory/reviews` 已写入
- [ ] 删除前会校验 `coach_profile.json` 已完成必要写回
- [ ] 校验失败时会延后删除并记录日志
