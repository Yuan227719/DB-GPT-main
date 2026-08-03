# 计划: 深度补充 research_new.md

## 概述
基于对项目源码的深度探索，在已有 17 个章节的基础上，新增 8 个章节补充未覆盖的子系统，并增强现有章节的细节。

## 新增章节

### 18. MCP 与连接器系统
- MCP 传输层 (SSE 自研实现 + Streamable HTTP 官方封装)
- MCPToolPack 工具包装器
- ConnectorManager 运行时管理
- ConnectorService 持久化与重启恢复
- catalog.json 内置连接器
- 凭证加密体系
- 工具命名空间前缀机制
- 连接器激活/测试/自愈流程

### 19. 可视化系统 (Vis)
- Vis 协议层次 (14 个 Vis 子类)
- VisChart/VisDashboard/VisThinking 核心实现
- VisClient 注册中心
- 从 LLM 输出到前端图表的数据流
- 图表类型支持 (8 种)

### 20. 场景系统 (Scene)
- ChatScene 枚举 (14 个场景)
- ChatFactory 分发机制
- BaseChat 核心执行流程
- chat_normal/chat_db/chat_data/chat_dashboard/chat_knowledge 各场景详解
- ExcelLearning 两阶段流程
- Prompt 注册与加载机制

### 21. 资源系统 (Resource)
- ResourceType 16 种类型
- Resource 抽象基类
- ResourcePack 容器
- ResourceManager 注册/构建/应用模式
- 具体资源实现 (DBResource/RetrieverResource/AppResource/SkillResource)

### 22. 工具系统 (Tool)
- BaseTool 抽象类
- FunctionTool 实现
- @tool 装饰器
- 参数解析三级 fallback 策略
- ToolPack 工具容器
- 工具输出格式
- 工具异常体系

### 23. Agent Profile 系统
- Profile 抽象接口
- ProfileConfig 核心配置类
- DefaultProfile 实现
- DynConfig 动态配置
- TTL 缓存机制
- ProfileFactory 体系

### 24. Skills 技能集成
- SkillType 枚举
- SkillBase 抽象类
- SkillManager 注册管理
- SkillLoader 多源加载
- SKILL.md 解析 (YAML frontmatter)
- 渐进式披露 (Progressive Disclosure)
- SkillsMiddleware 自动匹配
- 脚本执行与安全机制
- Connector 与 Skill 集成

### 25. API V1 深度分析
- 请求生命周期
- 流式/非流式路径
- Editor API (SQL 编辑器)
- Feedback API (聊天反馈)
- Agentic Data API (Agent 数据管理)

## 增强的现有章节

### 配置系统 (第5章)
- PolymorphicMeta 详细算法
- HookConfig 与 Hook 执行系统
- EnvVarSetHook 实现
- DynConfig 热加载
- ConfigurationManager._convert_value 边界情况

### 存储系统 (第13章)
- DatabaseManager 初始化流程
- Session 管理 (自动 commit/rollback)
- BaseDao CRUD 模式
- SQLite vs MySQL 差异
- SQLAlchemyStorage 适配器

### 代理 Provider (第6章)
- 21 个代理 Provider 完整列表
- OpenAILLMClient 详细流程
- 各 Provider 的继承复用模式

## 实现步骤
1. 读取 research_new.md 完整内容
2. 按上述计划逐章补充和新增内容
3. 确保所有文件路径和行号准确
4. 保持与原文档风格一致
