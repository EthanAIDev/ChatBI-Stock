# ChatBI 股票查询助手

ChatBI 助手是一个基于自然语言的 ChatBI（对话式商业智能）股票分析系统，包含 FastAPI 后端、React 管理/聊天前端、SQLite 数据查询、LLM 语义解析、SQL 生成、图表生成和 ARIMA 趋势预测能力。

## 功能概览

- 自然语言查询股票行情数据
- LLM 辅助意图识别、SQL 生成、纠错和结果解释
- 聊天会话、历史消息和流式输出
- 管理后台：用户、登录日志、操作日志、查询审计、AI 设置
- 股票图表生成与 ARIMA 趋势分析
- 语义层元数据、SQL 示例和 Chroma 向量检索

## 技术栈

- 后端：Python、FastAPI、Pydantic Settings、SQLite、JWT、bcrypt
- AI/LLM：OpenAI SDK 兼容接口、DashScope、LangChain、Chroma
- 前端：React、TypeScript、Vite、Ant Design、Zustand、Axios、React Router
- 可视化：ECharts、matplotlib
- 数据处理：pandas、Tushare、statsmodels

## 项目结构

详细结构见 [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)。

```text
ChatBI助手/
├─ backend/              # FastAPI 后端
├─ frontend/             # React + Vite 前端
├─ semantic_layer.py     # 语义层、元数据、缓存和向量辅助
├─ prepare_stock_data.py # 股票数据生成脚本
├─ stock_prices.sql      # 股票价格表结构
├─ requirements.txt      # Python 依赖
├─ .env.example          # 环境变量示例
└─ PROJECT_STRUCTURE.md  # 项目结构说明
```

## 快速开始

### 1. 准备后端环境

建议使用 Python 3.12。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

复制环境变量示例并填写真实配置：

```powershell
Copy-Item .env.example .env
```

至少需要配置：

- `DASHSCOPE_API_KEY`：DashScope / OpenAI 兼容接口密钥
- `TUSHARE_TOKEN`：用于运行 `prepare_stock_data.py` 拉取股票数据

### 2. 生成本地数据

仓库默认不提交运行数据库。首次运行前需要生成或提供本地数据库：

```powershell
python prepare_stock_data.py
```

该脚本会生成：

- `stock_prices.db`
- `stock_prices.xlsx`
- `stock_prices.sql`

其中 `stock_prices.db` 和 `stock_prices.xlsx` 已被 `.gitignore` 忽略；`stock_prices.sql` 保留在仓库中作为表结构参考。

### 3. 启动后端

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

健康检查：

```text
GET http://localhost:8000/api/health
```

### 4. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

默认访问：

```text
http://localhost:5173
```

Vite 会将 `/api` 代理到 `http://localhost:8000`。

## 默认账号

开发环境初始化时会创建默认账号：

- 管理员：`admin / admin123`
- 普通用户：`user / user123`

这些账号仅用于本地开发和演示。公开部署或生产使用前，必须修改默认密码，并避免将包含真实用户、登录日志、查询缓存或密码哈希的 SQLite 数据库提交到仓库。

## 环境变量

参考 [.env.example](./.env.example)。

重要变量：

- `DASHSCOPE_API_KEY`：模型调用密钥；当前代码也会将其作为 JWT 密钥来源之一。
- `DASHSCOPE_BASE_URL`：DashScope OpenAI 兼容接口地址。
- `TUSHARE_TOKEN`：生成股票行情数据所需的 Tushare Token。
- `MODEL_NAME`：默认模型名称。

## GitHub 上传说明

以下内容已加入 `.gitignore`，不应提交：

- `.env`、私钥、凭证文件
- `node_modules/`、`frontend/dist/`
- `*.db`、`*.sqlite`、`*.sqlite3`
- `stock_prices.xlsx`
- `logs/`、`__pycache__/`
- `chroma_db/`、`image_show/`
- `.cleanup_backup_*/`

本地清理备份目录 `.cleanup_backup_20260505/` 仅用于恢复清理前文件，不应上传。

## License

This project is licensed under the MIT License. See [LICENSE](./LICENSE).
