# PROJECT_STRUCTURE

## 项目概述

ChatBI 助手是一个面向股票数据查询与分析的智能 BI 应用，提供 FastAPI 后端、React 管理/聊天前端、SQLite 数据查询、LLM 语义解析与图表生成能力。

## 技术栈

- 后端：Python、FastAPI、Pydantic Settings、SQLite、JWT、bcrypt
- AI/LLM：OpenAI SDK 兼容接口、DashScope、LangChain、Chroma
- 前端：React、TypeScript、Vite、Ant Design、Zustand、Axios、React Router
- 可视化与内容渲染：ECharts、react-markdown、highlight.js、KaTeX、streamdown
- 数据分析：SQLite、Excel 数据生成脚本、ARIMA / statsmodels

## 目录结构

以下结构已排除 `.git/` 与 `.cleanup_backup_20260505/` 临时备份目录。

```text
ChatBI助手/
├─ .gitignore
├─ .env.example
├─ LICENSE
├─ PROJECT_STRUCTURE.md
├─ README.md
├─ requirements.txt
├─ AI-Agent-智能客服前端美化实施方案.md
├─ ChatBI后台管理实施计划.md
├─ backend/
│  ├─ __init__.py
│  ├─ callbacks.py
│  ├─ config.py
│  ├─ llm.py
│  ├─ main.py
│  ├─ memory.py
│  ├─ requirements-arima.txt
│  ├─ schemas.py
│  ├─ vector_store.py
│  ├─ engine/
│  │  ├─ base.py
│  │  └─ sqlite_engine.py
│  ├─ graph/
│  │  ├─ __init__.py
│  │  ├─ nodes.py
│  │  └─ state.py
│  ├─ models/
│  │  ├─ admin.py
│  │  ├─ auth.py
│  │  ├─ chat.py
│  │  └─ common.py
│  ├─ prompts/
│  │  ├─ analyst.py
│  │  ├─ classify.py
│  │  ├─ common.py
│  │  ├─ correction.py
│  │  └─ sql_generator.py
│  ├─ routers/
│  │  ├─ admin.py
│  │  ├─ auth.py
│  │  ├─ chat.py
│  │  ├─ chat_stream.py
│  │  └─ session.py
│  └─ services/
│     ├─ admin_service.py
│     ├─ arima_stock.py
│     ├─ auth_service.py
│     ├─ chat_service.py
│     ├─ security.py
│     └─ session_service.py
├─ frontend/
│  ├─ .gitignore
│  ├─ eslint.config.js
│  ├─ index.html
│  ├─ package-lock.json
│  ├─ package.json
│  ├─ tsconfig.app.json
│  ├─ tsconfig.json
│  ├─ tsconfig.node.json
│  ├─ vite.config.ts
│  └─ src/
│     ├─ App.tsx
│     ├─ index.css
│     ├─ main.tsx
│     ├─ components/
│     ├─ hooks/
│     ├─ layouts/
│     ├─ pages/
│     ├─ services/
│     ├─ stores/
│     └─ types/
├─ logger_utils.py
├─ prepare_stock_data.py
├─ semantic_layer.py
└─ stock_prices.sql
```

## 核心文件与目录说明

- `backend/`：FastAPI 后端源码目录，包含 API 路由、认证、会话、聊天编排、SQL 执行、语义层调用、管理后台服务等核心逻辑，应保留。
- `backend/main.py`：后端应用入口，创建 FastAPI 实例，注册路由，初始化 LangChain 缓存、业务表、认证表、管理表、语义元数据和 Chroma 向量库，应保留。
- `backend/config.py`：配置中心，通过 `.env` 与环境变量读取模型、数据库路径、图表目录、CORS 等配置。真实 `.env` 不应提交，建议后续补充 `.env.example`。
- `backend/routers/`：API 路由层，包含登录鉴权、聊天、流式聊天、会话和管理后台接口，应保留。
- `backend/services/`：业务服务层，包含认证、会话、聊天、管理后台、ARIMA 分析和 SQL 安全校验，应保留。
- `backend/models/`：Pydantic 请求/响应模型，应保留。
- `backend/prompts/`：LLM 分类、SQL 生成、分析和纠错提示词模板，应保留。
- `backend/engine/`：SQL 执行引擎抽象与 SQLite 实现，应保留。
- `backend/graph/`：LangGraph 相关节点与状态定义；当前属于后端业务能力的一部分，应保留。
- `backend/requirements-arima.txt`：ARIMA 分析额外依赖，建议后续整合到统一依赖文件或在 README 中说明。
- `frontend/`：React + Vite 前端工程目录，应保留。
- `frontend/src/App.tsx`：前端路由、权限守卫和 Ant Design 主题配置，应保留。
- `frontend/src/services/`：Axios API 封装，负责调用后端 `/api` 接口，应保留。
- `frontend/src/hooks/useSSE.ts`：流式聊天 SSE 请求逻辑，应保留。
- `frontend/package.json`：前端依赖和脚本定义，应保留。
- `frontend/package-lock.json`：npm 锁文件，应保留，用于保证依赖安装可复现。
- `semantic_layer.py`：语义层、元数据种子、SQL 示例、缓存和向量相关工具，被后端主流程引用，应保留。
- `logger_utils.py`：日志工具，被后端回调和语义层引用，应保留。
- `prepare_stock_data.py`：股票数据获取与导出脚本，可生成 `stock_prices.xlsx`、`stock_prices.sql` 和 `stock_prices.db`。依赖 `TUSHARE_TOKEN`，应保留为数据重建工具。
- `stock_prices.sql`：`stock_prices` 表结构和索引定义，可作为数据库重建参考，应保留。
- `README.md`：项目说明、启动方式、环境变量、默认账号和 GitHub 上传注意事项，应保留。
- `.env.example`：环境变量模板，不包含真实密钥，应保留并纳入版本控制。
- `requirements.txt`：Python 后端和数据脚本依赖清单，应保留。
- `LICENSE`：项目开源许可证，当前采用 MIT License，应保留。
- `AI-Agent-智能客服前端美化实施方案.md`、`ChatBI后台管理实施计划.md`：开发规划文档。若准备公开仓库，可保留为历史设计说明，也可后续迁移到 `docs/`。

## 已清理或应忽略内容

- `frontend/node_modules/`：前端依赖目录，已移至 `.cleanup_backup_20260505/`，由 `npm install` 重建。
- `frontend/dist/`：前端构建产物，已移至 `.cleanup_backup_20260505/`，由 `npm run build` 重建。
- `__pycache__/`、`*.pyc`：Python 编译缓存，已移至 `.cleanup_backup_20260505/`，应忽略。
- `logs/`、`*.log`：运行日志，已移至 `.cleanup_backup_20260505/`，应忽略。
- `chroma_db/`：Chroma 向量库持久化目录，已移至 `.cleanup_backup_20260505/`，可由启动逻辑重建，应忽略。
- `image_show/`：运行生成图表目录，已移至 `.cleanup_backup_20260505/`，应忽略。若需要展示样例图，应整理到 `docs/assets/`。
- `*.db`、`*.sqlite`、`*.sqlite3`、`stock_prices.xlsx`：运行数据库和脚本生成的数据文件已被 `.gitignore` 排除。当前清理前的 `stock_prices.db`、`schema_vector.db` 含会话、登录日志、查询缓存、用户哈希等运行数据，不建议直接公开。
- `.trae/`、`workspace/`：个人工作区/工具目录，已移至 `.cleanup_backup_20260505/`，应忽略。
- `.cleanup_backup_20260505/`：本次清理备份目录，仅用于临时恢复，不应提交到 GitHub。

## GitHub 上传前待办

- 复核 `README.md`：确认描述、启动步骤、默认账号和部署注意事项是否符合你的实际发布口径。
- 复核 `LICENSE`：当前采用 MIT License，如需闭源或其他许可证，应在发布前替换。
- 复核 `.env.example`：确认变量名、默认端口和 CORS 来源是否符合部署环境。
- 生成干净样例数据：如果希望仓库开箱可运行，应提供无用户、无日志、无缓存、无密码哈希的样例数据或初始化脚本。
- 复核 Python 依赖：当前已补充根级 `requirements.txt`，建议在目标机器上执行一次全量安装和启动验证。
