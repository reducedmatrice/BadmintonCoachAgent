# Structured Log Warehouse & Analytics Dashboard 2.1 Checklist

## 需求与范围

- [ ] 当前目标明确为 structured logs 入库、查询、统计页、云端部署与基础告警
- [ ] 本期必须完成、建议完成和非目标已在 spec 中明确
- [ ] SQLite 被明确为 MVP 存储方案
- [ ] 云端部署与迁移边界已写入 spec
- [ ] 告警能力被限定为基础规则引擎而非复杂告警平台

## 数据模型与存储

- [x] `structured_log_runs` 表已定义
- [x] `structured_log_import_jobs` 表已定义
- [x] `structured_log_alerts` 表已定义
- [x] 原始 structured log payload 保留策略已明确
- [x] 去重键与唯一约束已定义
- [x] 高频查询字段索引已定义
- [x] SQLite 数据文件路径已明确

## 导入链路

- [x] 能从 `gateway.log` 提取 `[ManagerStructured]` JSON 行
- [x] 非法 JSON 行会被安全跳过
- [x] 导入任务具备幂等性
- [x] 重复导入不会写出重复 run records
- [x] 每次导入任务都会记录开始、结束、状态和统计信息
- [ ] 导入失败不会影响主机器人处理链路

## 查询与统计接口

- [x] summary 查询接口已定义
- [x] timeseries 查询接口已定义
- [x] by-route 查询接口已定义
- [x] errors 查询接口已定义
- [x] import-jobs 查询接口已定义
- [x] alerts 查询接口已定义
- [x] 手动触发 import 接口已定义
- [x] 时间范围过滤已支持
- [x] route 维度过滤已支持
- [x] 空数据场景返回结构已定义

## 前端统计页

- [x] 页面包含 KPI 指标卡片
- [x] 页面包含请求量或延迟趋势图
- [x] 页面包含 route 统计表格
- [x] 页面包含最近告警列表
- [x] 页面包含最近导入任务状态列表
- [x] 加载态、空态、异常态已定义
- [ ] 图表与表格的数据口径一致

## 告警与运维

- [x] 导入失败告警规则已定义
- [x] 高错误率告警规则已定义
- [x] 高 P95 延迟告警规则已定义
- [x] 告警记录会写入数据库
- [x] 本地 cron 或等效调度方式已定义
- [x] 云端 scheduler 方案已定义
- [x] 数据库不可用时的回滚与降级方案已定义

## 测试

- [x] parser 单元测试已覆盖
- [x] 去重逻辑测试已覆盖
- [x] repository 测试已覆盖
- [x] 聚合统计测试已覆盖
- [x] 告警规则测试已覆盖
- [x] 导入链路集成测试已覆盖
- [x] 数据库查询到 API 的集成测试已覆盖
- [x] 前端统计页基础验收已通过
- [x] 新数据库统计结果与文件汇总结果已交叉验证

## 文档与发布

- [x] `dev-spec-database2.1.md` 已完成
- [x] `tasks-2.1.md` 已完成
- [x] `checklist-2.1.md` 已完成
- [x] 风险、回滚和迁移边界已记录
- [x] 待确认问题已关闭或明确标注为后续事项
