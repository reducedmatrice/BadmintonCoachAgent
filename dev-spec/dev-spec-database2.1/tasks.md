# Structured Log Warehouse & Analytics Dashboard 2.1 Tasks

本文件从 [dev-spec-database2.1.md](./dev-spec-database2.1.md) 映射而来，按阶段拆分实现任务。

## 阶段 A：数据模型与入库基础

### A1 设计 SQLite schema 与数据目录

- 状态：已完成
- 目标：建立 structured logs 数据库存储基础
- 输入：现有 structured log JSON 字段、日志文件路径约定、SQLite 落地决策
- 输出：数据库路径约定、建表脚本或初始化逻辑、表结构文档
- 依赖：无
- 完成定义（DoD）：
  - `structured_log_runs`、`structured_log_import_jobs`、`structured_log_alerts` 三张表已定义
  - 高频查询字段索引已明确
  - 原始 payload 保留策略已明确
- 并行项：可与 A2 设计同步进行
- 阻塞项：无

### A2 设计去重键与幂等导入策略

- 状态：已完成
- 目标：保证重复导入不会写出重复数据
- 输入：structured log JSON payload、日志来源文件与行信息
- 输出：dedupe hash 方案、唯一约束、重复导入行为定义
- 依赖：A1
- 完成定义（DoD）：
  - 去重键生成规则可复现
  - 重复导入时仅跳过，不影响任务整体成功
  - 插入数、跳过数、失败数的统计口径已明确
- 并行项：可与 A3 并行
- 阻塞项：无

### A3 实现 structured log parser

- 状态：已完成
- 目标：从 `gateway.log` 中提取 `[ManagerStructured]` JSON 记录
- 输入：现有 structured log 行格式、字段定义
- 输出：parser 模块、字段归一化逻辑、解析测试
- 依赖：A1
- 完成定义（DoD）：
  - 可从日志文本稳定提取结构化记录
  - 非法 JSON 行可跳过且不导致整体失败
  - token、route、memory_hits、error 字段归一化行为可测试
- 并行项：可与 A2 并行
- 阻塞项：无

### A4 实现 importer 与导入任务记录

- 状态：已完成
- 目标：建立可重复执行的入库任务
- 输入：parser、schema、去重策略
- 输出：导入 CLI / service、导入任务记录、失败与统计输出
- 依赖：A2、A3
- 完成定义（DoD）：
  - 能从日志文件批量导入数据库
  - 导入任务状态写入 `structured_log_import_jobs`
  - 重复执行不产生重复 run records
- 并行项：无
- 阻塞项：无

## 阶段 B：分析查询与告警

### B1 实现 repository 与 analytics service

- 状态：已完成
- 目标：建立数据库访问与统计聚合能力
- 输入：SQLite schema、导入后的 run 数据
- 输出：repository、analytics service、聚合查询接口
- 依赖：A4
- 完成定义（DoD）：
  - 支持 summary、timeseries、by-route、errors、import-jobs、alerts 查询
  - 支持时间范围过滤
  - 支持 route、channel、assistant_id 等基础过滤维度
- 并行项：可与 B2 设计并行
- 阻塞项：无

### B2 实现 analytics API 路由

- 状态：已完成
- 目标：向前端提供稳定的数据接口
- 输入：analytics service、现有 gateway router 组织方式
- 输出：analytics API 路由、响应 schema、接口测试
- 依赖：B1
- 完成定义（DoD）：
  - 至少包含 summary、timeseries、by-route、errors、import-jobs、alerts、import 手动触发接口
  - 空数据场景有稳定响应结构
  - 错误响应不泄露内部敏感信息
- 并行项：无
- 阻塞项：无

### B3 实现基础告警规则

- 状态：已完成
- 目标：让系统具备最小异常提醒能力
- 输入：最近导入结果、聚合统计数据、阈值规则
- 输出：alert evaluator、告警入库逻辑、规则测试
- 依赖：B1
- 完成定义（DoD）：
  - 至少覆盖导入失败、高错误率、高 P95 延迟三类规则
  - 告警写入 `structured_log_alerts`
  - 告警状态流转字段已定义
- 并行项：可与 B2 并行
- 阻塞项：无

## 阶段 C：前端统计页

### C1 设计统计页信息架构

- 状态：已完成
- 目标：确定统计页展示层级与交互结构
- 输入：summary、timeseries、route 统计、alerts、import-jobs 接口
- 输出：页面布局方案、组件拆分、空态与异常态定义
- 依赖：B2
- 完成定义（DoD）：
  - 页面包含 KPI 卡片、趋势图、route 表格、告警列表、导入任务列表
  - 已明确筛选器位置与交互方式
  - 已定义无数据时展示策略
- 并行项：可与 C2 图表选型并行
- 阻塞项：无

### C2 实现统计页数据接入

- 状态：已完成
- 目标：打通前端与 analytics API
- 输入：analytics API、页面布局方案
- 输出：前端页面、数据请求 hooks、错误与加载态处理
- 依赖：C1
- 完成定义（DoD）：
  - 指标卡片可展示总请求数、错误率、P50/P95、平均 total tokens
  - 趋势图可按时间窗口切换
  - route 表格可按核心维度展示统计结果
- 并行项：无
- 阻塞项：无

### C3 补充告警与导入状态展示

- 状态：已完成
- 目标：让运维信息在页面上可见
- 输入：alerts、import-jobs 接口
- 输出：告警列表、导入任务列表、最近失败状态提示
- 依赖：C2
- 完成定义（DoD）：
  - 可查看最近告警事件
  - 可查看最近导入任务成功/失败状态
  - 失败状态下页面可提供清晰降级提示
- 并行项：无
- 阻塞项：无

## 阶段 D：调度、云端部署与迁移设计

### D1 实现本地调度入口

- 状态：已完成
- 目标：让日志入库支持周期执行
- 输入：importer、项目脚本组织方式
- 输出：CLI 命令、cron 示例、运行说明
- 依赖：A4
- 完成定义（DoD）：
  - 可手动触发导入任务
  - 可通过 cron 周期执行
  - 导入失败可写任务状态并可被告警模块识别
- 并行项：可与 D2 并行
- 阻塞项：无

### D2 设计云端部署方案

- 状态：已完成
- 目标：为未来线上运行提供可执行设计
- 输入：SQLite MVP、定时任务方案、容器部署约束
- 输出：云端部署设计、持久化方案、迁移说明
- 依赖：B3、D1
- 完成定义（DoD）：
  - 已给出本地与云端两套调度方案
  - 已说明 SQLite 持久卷方案与风险
  - 已说明迁移 PostgreSQL / ClickHouse 时的替换边界
- 并行项：无
- 阻塞项：无

### D3 制定回滚与故障隔离策略

- 状态：已完成
- 目标：确保 analytics 子系统不会影响主机器人链路
- 输入：导入链路、数据库依赖、前端统计页
- 输出：回滚方案、故障隔离说明、风险文档
- 依赖：D1、D2
- 完成定义（DoD）：
  - 数据库不可用时主机器人功能不受阻
  - 可关闭导入任务而保留文件日志
  - 统计页异常不会影响业务主页面
- 并行项：无
- 阻塞项：无

## 阶段 E：测试、验收与文档收敛

### E1 补齐单元与集成测试

- 状态：已完成
- 目标：保证解析、导入、聚合、告警逻辑稳定
- 输入：parser、importer、repository、analytics service
- 输出：单元测试、集成测试、测试夹具日志
- 依赖：B3、C3
- 完成定义（DoD）：
  - parser、dedupe、repository、aggregator、alert evaluator 均有测试
  - 至少有一条真实日志导入到查询的端到端测试
  - 与现有文件汇总脚本结果可交叉验证
- 并行项：可与 E2 并行
- 阻塞项：无

### E2 前端验收与空态回归

- 状态：已完成
- 目标：验证统计页在多种数据状态下可用
- 输入：前端统计页、真实或夹具数据
- 输出：页面验收结果、异常态修复、展示一致性检查
- 依赖：C3
- 完成定义（DoD）：
  - 正常数据场景展示正确
  - 空数据库、导入失败、无告警场景展示稳定
  - 图表与表格数据口径一致
- 并行项：可与 E1 并行
- 阻塞项：无

### E3 文档与阶段总结

- 状态：已完成
- 目标：让 spec、任务、验收结果与最终实现一致
- 输入：实现结果、测试结果、部署设计
- 输出：更新后的文档、自检记录、风险总结
- 依赖：E1、E2
- 完成定义（DoD）：
  - `dev-spec-database2.1.md`、`tasks.md`、`checklist.md` 与实现一致
  - 风险与迁移边界已记录
  - 后续版本演进建议已补充
- 并行项：无
- 阻塞项：无
