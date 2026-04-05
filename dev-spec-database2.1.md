# Developer Specification (DEV_SPEC)

> 版本：2.1 — Structured Log Warehouse & Analytics Dashboard

## 目录

- 项目概述
- 核心特点
- 技术选型
- 测试方案
- 系统架构与模块设计
- 项目排期
- 可扩展性与未来展望

***

## 1. 项目概述

### 1.1 项目定位

本项目面向当前仓库已经具备的 structured logs 能力，建设一套从日志文件到数据库、再到前端统计页的轻量分析链路。目标不是替换现有运行时日志体系，而是在不破坏 `logs/gateway.log` 写法的前提下，为日志分析、性能追踪、错误定位和后续云端扩展提供一个稳定的数据底座。

本阶段采用 SQLite 作为首期落地存储，优先解决“能持续入库、能稳定查询、能直观展示”的 MVP 问题，同时为后续迁移 PostgreSQL / ClickHouse 和接入云端定时任务、告警服务预留清晰扩展边界。

### 1.2 项目目标

本阶段有四层目标。

**产品目标**

- 让 structured logs 不再只停留在日志文件里，而能被结构化查询
- 让开发者通过前端统计页直观看到延迟、token、错误率、route 分布与 memory hit 情况
- 让日志链路可支持本地调试、阶段复盘和后续云端部署

**工程目标**

- 保留当前 `gateway.log` 中 `[ManagerStructured]` JSON 输出格式
- 新增日志解析与批量入库链路
- 建立面向统计页的后端查询接口
- 建立 SQLite 数据表、索引、去重策略和增量导入机制
- 建立基础告警规则和可迁移的存储抽象

**运维目标**

- 支持本地定时任务或手动任务持续导入新增日志
- 支持云端部署场景下的周期同步、失败重试和幂等导入
- 支持对高错误率、高延迟、导入失败等异常发出基础告警

**学习 / 面试目标**

- 能清楚解释“文件日志 -> 解析 -> 入库 -> 聚合 -> 可视化”的完整后端数据链路
- 能解释为什么 SQLite 适合作为 MVP，为什么数据库比纯日志文件更适合查询和统计
- 能说明如何从单机方案平滑迁移到云端数据库与托管调度

### 1.3 目标用户与使用场景

#### 1.3.1 目标用户

- 主用户：你本人，负责本地调试、日志排障、项目演示和性能观察
- 次用户：未来试用项目的开发者或面试官，需要看到系统是否稳定、性能如何、错误是否可追踪

#### 1.3.2 典型使用场景

| 场景 | 用户动作 | 系统输出 |
| ---- | ---- | ---- |
| 本地排障 | 运行飞书机器人后查看统计页 | 显示最近 24 小时请求数、错误率、P50/P95 延迟 |
| 性能复盘 | 比较新改动前后表现 | 按 route 查看平均 token、延迟和错误率 |
| 线上观察 | 云端定时导入日志后查看趋势 | 查看天级请求量、错误峰值和慢请求分布 |
| 异常告警 | 导入失败或错误率升高 | 记录告警事件并触发基础通知 |
| 扩展迁移 | 数据量增大 | 保持字段契约稳定，切换数据库实现 |

### 1.4 MVP 范围

#### 1.4.1 本期必须完成

- 保留 structured logs 文件输出能力
- 定义 SQLite 表结构与索引
- 实现 structured logs 解析与增量入库脚本
- 实现幂等去重导入
- 实现后端聚合查询接口
- 实现前端统计页 MVP
- 实现基础时间范围筛选、route 筛选和关键指标卡片
- 实现基础告警规则与告警记录
- 输出云端部署和迁移设计

#### 1.4.2 本期建议完成

- 支持定时任务状态页或最近导入记录展示
- 支持错误样本明细查看
- 支持按 channel、agent_name、assistant_id 的多维过滤
- 支持导出日报或 markdown 摘要

#### 1.4.3 本期不纳入 MVP

- 直接接入 Elasticsearch / Loki / Kafka
- 实时流式日志消费平台
- 复杂多租户权限系统
- 大规模 OLAP 优化
- 企业级告警编排平台

### 1.5 当前已知约束

- 当前 structured logs 来源于 `gateway.log` 中的 `[ManagerStructured]` JSON 行
- 当前已有离线汇总逻辑，但仅面向文件，不面向数据库查询
- 当前仓库尚未引入专门的生产数据库服务
- 前端统计页应尽量复用现有前端栈与 API 风格
- 现有日志字段中部分值可能缺失，入库设计必须允许空值

### 1.6 关键假设

- 假设 A1：当前 structured log JSON 契约可以作为数据库字段设计基础
- 假设 A2：SQLite 足以支撑当前单机和低并发规模
- 假设 A3：导入任务以批处理为主，不要求真正实时
- 假设 A4：前端统计页优先查看聚合结果，不优先构建复杂明细检索系统
- 假设 A5：告警以规则阈值为主，不构建复杂预测性告警系统

### 1.7 成功标准

#### 1.7.1 功能成功标准

- 新增日志导入任务可稳定从 `gateway.log` 读取 structured records 并写入数据库
- 重复执行导入任务不会造成重复数据
- 后端可返回总请求数、错误率、P50/P95 延迟、平均 token 等聚合指标
- 前端统计页可展示趋势图、关键指标卡片和 route 维度统计
- 基础告警规则能记录并查询高错误率、高延迟、导入失败事件

#### 1.7.2 质量成功标准

- 单次导入任务对已有日志的重复处理不会写出重复记录
- 统计接口返回结果与日志样本计算值一致
- 时间范围和 route 过滤查询结果正确
- 前端页面在空数据、缺失字段和导入失败场景下可降级显示
- 本地与云端部署方案都保留回滚路径

#### 1.7.3 可观测性成功标准

- 可按天查看请求量、错误率和延迟变化趋势
- 可按 route 查看请求数、P50/P95、平均 token 和错误率
- 可查看最近导入状态、告警事件与导入失败原因
- 可保留从数据库回溯到原始日志时间窗口的能力

***

## 2. 核心特点

### 2.1 文件日志与数据库双轨保留

本阶段不移除原有文件日志，而是在原有 structured logs 基础上新增数据库入库链路。文件日志继续承担原始证据职责，数据库承担查询与聚合职责。

### 2.2 轻量入库架构

日志入库采用“解析脚本 + 增量游标 + 幂等去重”的轻量方案，优先降低复杂度。MVP 不要求引入消息队列或专门日志平台。

### 2.3 面向前端统计页的查询模型

数据库设计和查询接口围绕前端使用场景构建，而不是先做通用日志平台。优先支持：

- KPI 总览
- 时间趋势
- route 维度统计
- 错误样本与告警记录

### 2.4 云端可迁移设计

虽然 MVP 先使用 SQLite，但从字段、仓储接口和调度方式上预留迁移空间，后续可替换为 PostgreSQL / ClickHouse，而不要求前端和上层查询逻辑大改。

### 2.5 基础告警能力

日志系统除了“能看”，还要“能提醒”。本期至少支持：

- 导入任务失败告警
- 错误率超过阈值告警
- P95 延迟超过阈值告警

### 2.6 开发者可解释性

所有统计结果必须能解释来源，保证从“前端图表 -> 聚合接口 -> 数据库记录 -> 原始 structured log 字段”形成清晰映射链。

***

## 3. 技术选型

### 3.1 存储方案

- MVP 存储：SQLite
- 数据文件建议位置：`backend/.deer-flow/analytics/structured_logs.db` 或项目约定的可写数据目录
- 迁移目标：PostgreSQL / ClickHouse
- 决策理由：
  - SQLite 零运维、单文件、适合个人项目和单机场景
  - 当前 structured logs 体量较小，优先快速落地
  - 数据库字段和查询接口先抽象，后续迁移成本可控

### 3.2 数据模型

建议至少拆分三类表：

- `structured_log_runs`
  - 保存每条 structured run record
  - 字段建议：`id`、`source_file`、`source_line_hash`、`created_at`、`channel`、`thread_id`、`assistant_id`、`agent_name`、`latency_ms`、`response_length`、`artifact_count`、`error`、`error_type`、`input_tokens`、`output_tokens`、`total_tokens`、`memory_hits_json`、`route_json`、`raw_json`
- `structured_log_import_jobs`
  - 保存每次导入任务状态
  - 字段建议：`id`、`started_at`、`finished_at`、`status`、`source_file`、`records_scanned`、`records_inserted`、`records_skipped`、`error_message`
- `structured_log_alerts`
  - 保存告警事件
  - 字段建议：`id`、`created_at`、`alert_type`、`severity`、`window_start`、`window_end`、`threshold_value`、`observed_value`、`status`、`payload_json`

### 3.3 去重与幂等策略

- 以 structured log 原始 JSON payload 的稳定 hash 作为去重键之一
- 同时记录来源文件和来源行指纹，便于排查
- 导入任务重复执行时：
  - 已存在记录跳过
  - 不抛出整体失败
  - 导入结果统计插入数与跳过数

### 3.4 导入方式

- 本地模式：CLI 手动触发 + cron 定时触发
- 云端模式：容器内 cron、平台 scheduler、GitHub Actions、云函数定时器等
- 首期采用批量扫描日志文件，不要求实时 tail 消费

### 3.5 后端接口

建议新增 analytics 模块与路由，至少提供：

- `GET /api/analytics/summary`
- `GET /api/analytics/timeseries`
- `GET /api/analytics/by-route`
- `GET /api/analytics/errors`
- `GET /api/analytics/import-jobs`
- `GET /api/analytics/alerts`
- `POST /api/analytics/import`

### 3.6 前端技术

- 复用当前前端框架和页面组织方式
- 首期不新增外部图表库，优先使用 React + SVG 完成轻量趋势图
- 数据层采用 `frontend/src/core/analytics` 下的 API + hooks 组织方式
- 页面优先实现：
  - 指标卡片
  - 折线图 / 柱状图
  - route 表格
  - 告警列表
  - 导入状态列表
- 页面路由落点为 `/workspace/analytics`

### 3.7 告警实现

- 告警规则引擎先采用代码规则，不引入复杂 CEP 系统
- 规则来源可先写死在配置或 YAML 中，后续再扩展 UI 配置
- 通知方式首期可只写数据库 + 日志；建议预留 Feishu webhook / 邮件通知接口
- 首期已落地规则包括：`import_failed`、`high_error_rate`、`high_p95_latency`

***

## 4. 测试方案

### 4.1 单元测试

- structured log 解析测试
- 去重 hash 计算测试
- SQLite 仓储写入与查询测试
- 聚合指标计算测试
- 告警规则计算测试

### 4.2 集成测试

- 从示例 `gateway.log` 到 SQLite 的完整导入链路测试
- 从数据库到 API 返回的聚合结果测试
- 从 API 到前端统计页展示的联调测试
- 至少一条从 `POST /api/analytics/import` 到 `GET /api/analytics/summary` 的端到端校验

### 4.3 回归测试

- 现有 `scripts/summarize_run_logs.py` 与新数据库聚合统计结果保持一致
- structured log 原始文件输出不被破坏
- 机器人主链路运行不依赖数据库导入是否成功

### 4.4 失败场景测试

- 空日志文件
- 非法 JSON 行
- 重复日志导入
- 数据库文件不存在
- 数据库锁冲突
- 告警阈值配置异常
- 查询接口在无数据时的返回格式

### 4.5 验收测试

- 导入一份真实 `gateway.log` 后，统计页能展示请求量、错误率、P50/P95、token 指标
- route 维度统计与日志样本人工核对一致
- 制造一个高错误率窗口后，系统可写入告警事件
- 部署说明可支持本地和云端两种运行方式
- 空数据库、导入失败、无告警场景下页面空态与异常态稳定

***

## 5. 系统架构与模块设计

### 5.1 总体流程

系统流程如下：

1. Gateway 将 `[ManagerStructured]` JSON 持续写入 `logs/gateway.log`
2. 导入任务扫描日志文件，提取 structured records
3. 解析器将 JSON payload 规范化为数据库记录
4. 仓储层执行幂等写入 SQLite
5. 后端 analytics API 从数据库聚合查询
6. 前端统计页调用 API 展示指标、趋势、route 统计和告警信息

### 5.2 后端模块划分

#### 5.2.1 Parser 层

职责：

- 从日志文本中提取 `[ManagerStructured]` 行
- 校验 JSON 格式
- 归一化 token、route、memory_hits、error 字段
- 生成去重键

#### 5.2.2 Importer 层

职责：

- 扫描指定日志文件
- 跟踪导入任务状态
- 处理批量写入、跳过、失败统计
- 触发告警规则评估

#### 5.2.3 Repository 层

职责：

- 管理 SQLite 连接和建表迁移
- 提供 run/import_job/alert 的增删查聚合接口
- 隔离未来数据库迁移差异

#### 5.2.4 Analytics Service 层

职责：

- 计算 summary、timeseries、route 聚合
- 处理时间范围、route、channel 等过滤参数
- 输出前端友好的响应结构

#### 5.2.5 Alert Evaluator 层

职责：

- 根据导入窗口或最近时间段数据计算告警
- 支持阈值型规则
- 写入告警记录并预留通知接口

### 5.3 前端模块划分

建议新增一个 analytics 页面，包含：

- Summary 区
  - 总请求数
  - 错误率
  - P50 / P95 延迟
  - 平均 total tokens
- Timeseries 区
  - 请求量趋势
  - 错误率趋势
  - 延迟趋势
- Route Breakdown 区
  - 按 route 展示请求数、延迟、token、错误率
- Alerts 区
  - 最近告警记录
- Import Jobs 区
  - 最近导入任务状态
- Filters / Import 区
  - 时间窗口、route、channel、assistant_id 筛选
  - 手动导入日志入口

### 5.4 数据库设计原则

- 原始 payload 保留，避免后续字段扩展时丢信息
- 高频过滤字段建立索引
- JSON 扩展字段可先以 JSON 文本保存
- 所有聚合查询都要支持时间窗口

建议索引：

- `created_at`
- `agent_name`
- `assistant_id`
- `channel`
- `error`
- `dedupe_hash`

### 5.5 云端部署设计

#### 5.5.1 本地模式

- 日志文件写在本地 `logs/`
- 定时任务使用 cron 或手动脚本
- SQLite 文件与应用一起部署

#### 5.5.2 云端模式

- 应用容器写运行日志
- 定时任务使用平台 scheduler 周期执行导入命令
- 初期仍可挂载持久卷保存 SQLite
- 后续若切换 PostgreSQL，则仅替换仓储实现和连接配置

#### 5.5.3 失败与回滚

- 导入逻辑失败不影响主机器人处理链路
- 数据库不可用时，系统仍保留文件日志
- 可通过关闭 scheduler 或切回文件分析脚本完成回滚

### 5.6 告警规则设计

首期规则建议：

- 最近 15 分钟 error rate > X%
- 最近 15 分钟 P95 latency > Y ms
- 最近一次导入任务失败
- 最近 N 次导入无新增记录且日志文件仍增长

告警状态建议：

- `open`
- `acknowledged`
- `resolved`

### 5.7 安全与数据治理

- 不在前端展示原始敏感 payload
- 对数据库保留必要字段，避免写入明文秘钥和无关敏感数据
- 原始日志字段展示时优先脱敏
- 导入脚本出错日志不能泄露 API key 或环境变量

***

## 6. 项目排期

### 阶段 A：数据模型与导入链路

- 设计 SQLite schema
- 实现 parser / repository / importer
- 完成幂等导入与导入任务记录

### 阶段 B：查询接口与告警规则

- 实现 analytics API
- 实现 summary / timeseries / by-route / errors / import-jobs / alerts 查询
- 实现基础告警规则与记录

### 阶段 C：前端统计页

- 实现统计页布局
- 接入 summary、趋势图、route 表格、告警列表、导入状态列表
- 处理空态、加载态、异常态

### 阶段 D：云端部署与文档收敛

- 完成本地 cron 与云端 scheduler 方案说明
- 完成迁移 PostgreSQL / ClickHouse 的边界设计
- 完成自检、回归、文档和验收总结

### 阶段 E：测试、验收与收敛

- 补齐导入到查询的端到端测试
- 补齐文件汇总脚本与数据库统计的交叉验证
- 完成统计页基础验收、空态回归与最终文档收敛

***

## 7. 可扩展性与未来展望

### 7.1 存储迁移

- 从 SQLite 迁移到 PostgreSQL：优先满足多人访问、服务化部署和更稳定的并发读写
- 从 PostgreSQL 迁移到 ClickHouse：优先满足高体量日志、低成本聚合分析和更复杂报表

### 7.2 更丰富的分析能力

- 增加按 agent / assistant / channel / error_type 的更多维度分析
- 增加按小时、天、周的自动汇总表
- 增加 top slow requests、top error routes 等榜单

### 7.3 更丰富的通知能力

- 接入 Feishu webhook
- 接入邮件通知
- 支持告警静默、阈值配置和确认闭环

### 7.4 与评测系统联动

- 将 structured logs 与离线评测结果统一展示
- 支持线上运行指标与离线质量指标并列分析
- 支持按版本对比改动前后质量变化
