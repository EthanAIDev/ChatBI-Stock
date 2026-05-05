# ChatBI 后台管理实施计划

## 摘要

基于当前项目现状，后台管理优先定位为轻量运营后台，先解决日常运维、用户管理、会话排查、模型配置和审计留痕，不在第一阶段引入组织、租户、审批流等企业级治理能力。

当前项目已具备以下基础：

- 用户表 `sys_user`
- 登录日志表 `sys_login_log`
- 会话表 `chat_sessions`
- 消息表 `chat_messages`
- `admin` 角色
- 聊天、会话、认证三条核心链路
- 一个最小后台页雏形

## 主流后台常见模块

### 1. 身份与权限

- 登录认证
- 用户管理
- 角色权限（RBAC）
- 登录审计
- 安全策略（锁定、重置、MFA、SSO）

### 2. 业务运营

- 会话/工单/内容列表
- 搜索、筛选、批量操作
- 详情页与操作记录
- 置顶、状态流转、标签分类

### 3. 系统配置

- 模型/接口配置
- 提示词模板配置
- 缓存策略
- 系统参数与开关
- 文件与资源管理

### 4. 可观测与审计

- 操作日志
- 登录日志
- 错误日志
- 请求链路/接口日志
- 告警与监控看板

### 5. 数据治理

- 数据源管理
- SQL 审计
- 查询历史
- 知识库/语义层管理
- 指标或元数据维护

### 6. 平台治理

- 组织/成员管理
- 权限矩阵
- 审批流
- API Key 管理
- 配额、限流、租户隔离

## 适合完善到当前项目的模块

### P0：优先立即补齐

#### 用户管理

- 查看用户列表、角色、状态、最后登录时间
- 管理员可启停账号
- 管理员可重置密码
- 管理员可调整角色

#### 登录日志

- 查看成功/失败登录记录
- 支持按用户名、时间、结果筛选

#### 会话管理

- 查看所有会话
- 按用户、时间、标题、关键词搜索
- 查看某个会话的完整问答记录
- 删除异常会话
- 标记重点会话

#### 系统概览

- 今日登录数
- 总用户数
- 活跃用户数
- 会话数
- 失败登录数

#### 管理员操作日志

- 谁删除了会话
- 谁修改了用户角色
- 谁改了系统配置

### P1：第二阶段补充

#### 模型配置管理

- 当前模型名
- API Base URL
- 超时
- 重试次数
- 默认上下文轮数

#### Prompt / 模板管理

- SQL 生成提示词
- 总结提示词
- Few-shot 示例配置

#### 查询审计

- 用户原始问题
- 生成 SQL
- 执行耗时
- 是否命中缓存
- 是否生成图表

#### 缓存管理

- 查询缓存列表
- 手动清理缓存
- TTL 配置

#### 图表与文件资源管理

- 已生成图表列表
- 失效文件清理

#### 错误中心

- LLM 请求失败
- SQL 执行失败
- 流式接口失败
- 图片生成失败

### P2：中后期再做

#### 细粒度权限控制

- 用户管理权限
- 会话查看权限
- 配置修改权限
- 日志查看权限

#### 数据源 / 语义层管理

- 股票库连接配置
- Schema 元数据维护
- 示例问答维护
- 向量库重建入口

#### 安全增强

- MFA
- SSO
- IP 白名单
- 高危操作二次确认

#### 通知告警

- 登录异常告警
- 模型不可用告警
- 查询错误率告警

#### 导出能力

- 用户列表导出
- 登录日志导出
- 会话审计导出

## 建议采用的后台菜单结构

- 仪表盘
- 用户与权限
- 会话运营
- AI 配置
- 数据与审计
- 系统设置

### 仪表盘

- 核心统计卡片
- 最近异常
- 最近登录

### 用户与权限

- 用户管理
- 登录日志
- 管理员操作日志

### 会话运营

- 会话列表
- 会话详情
- 异常查询记录

### AI 配置

- 模型配置
- Prompt 模板
- 缓存管理

### 数据与审计

- SQL 查询审计
- 图表资源
- 错误日志

### 系统设置

- 基础参数
- 安全设置

## MVP 建议范围

如果只做一版 MVP，优先实现以下 8 个模块：

1. 仪表盘统计
2. 用户管理
3. 登录日志
4. 会话列表
5. 会话详情
6. 查询审计
7. 模型配置
8. Prompt 模板管理

## 建议新增接口

- `/api/admin/overview`
- `/api/admin/users`
- `/api/admin/users/{id}`
- `/api/admin/login-logs`
- `/api/admin/action-logs`
- `/api/admin/sessions`
- `/api/admin/sessions/{session_id}`
- `/api/admin/query-audits`
- `/api/admin/model-settings`
- `/api/admin/prompt-templates`
- `/api/admin/cache`
- `/api/admin/errors`

## 建议新增前端类型

- `AdminOverview`
- `AdminUser`
- `AdminLoginLog`
- `AdminActionLog`
- `AdminSession`
- `AdminQueryAudit`
- `ModelSettings`
- `PromptTemplate`

## 测试与验收清单

- `admin` 登录后默认进入后台，不进入聊天页
- 普通用户访问 `/admin` 被拒绝并重定向
- 用户列表能显示角色、状态、最近登录
- 登录日志能正确区分成功/失败
- 会话列表支持按用户和时间筛选
- 会话详情能看到完整对话与 SQL
- 修改模型配置后能持久化并生效
- Prompt 模板更新后新请求使用新模板
- 删除会话、改角色、改配置都会写入管理员操作日志

## 假设与默认选择

- 后台定位默认采用轻量运营后台
- 第一阶段不做组织、租户、审批流
- 置顶、筛选、导出等交互优先在前端实现
- 复杂权限控制放到后续阶段
- `admin` 与 `superadmin` 都可进入后台
- 审计日志优先记录管理员动作和 AI 查询动作
- 暂不做全链路 observability
- 模块优先顺序为：用户/日志/会话 > AI 配置 > 数据治理 > 企业安全

## 参考依据

- Backstage Audit Events  
  <https://backstage.io/docs/next/features/software-catalog/audit-events>
- Supabase Auth  
  <https://supabase.com/docs/guides/auth>
- Supabase User Management  
  <https://supabase.com/docs/guides/auth/managing-user-data>
- Supabase Logging  
  <https://supabase.com/docs/guides/platform/logs>
- Supabase Auth Audit Logs  
  <https://supabase.com/docs/guides/auth/audit-logs>
- Supabase Platform Audit Logs  
  <https://supabase.com/docs/guides/security/platform-audit-logs>
- Appsmith  
  <https://www.appsmith.com/>
