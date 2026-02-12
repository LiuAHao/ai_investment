# AI 投资分析系统

一个基于 **Flask + React + 多 Agent 协作** 的投资分析项目，支持用户认证、股票与新闻信息聚合、对话分析与 RAG 知识检索。

## 主要能力

- 用户注册/登录与 JWT 鉴权
- 股票数据查询与分析（AKShare）
- 新闻联网检索与分析
- 多 Agent 协同分析流程（主控、数据、新闻、知识、分析）
- 可切换编排器（LangChain `AgentExecutor` / 自研编排自动回退）
- 聊天记录与分析会话持久化（SQLite/可切换数据库）
- RAG 本地知识库检索（Chroma）
- React 前端可视化界面

## 技术栈

- 后端：`Python`、`Flask`、`SQLAlchemy`
- 编排：`LangChain AgentExecutor`（可选）+ 自研编排（fallback）
- 前端：`React`、`Vite`、`TailwindCSS`、`Recharts`
- 数据与检索：`SQLite`（默认）、`ChromaDB`、`sentence-transformers`
- 数据源：`AKShare`、网页联网搜索（已移除 RSS 拉取）

## 项目结构

```text
ai_investment/
├── run.py                      # 启动脚本（前后端快捷启动）
├── requirements.txt            # Python 依赖
├── src/
│   ├── api/                    # Flask API 路由
│   ├── agent/                  # 多 Agent 核心逻辑
│   ├── models/                 # 数据库模型与初始化
│   ├── stock/                  # 股票数据模块
│   ├── news/                   # 新闻数据模块
│   ├── rag/                    # RAG 检索与索引构建
│   ├── utils/                  # 工具模块
│   └── web/                    # React 前端
└── ...
```

## 环境要求

- Python `3.10+`（建议 `3.11`）
- Node.js `18+`
- npm `9+`

## 快速开始

### 1) 安装 Python 依赖

在项目根目录执行：

```bash
pip install -r requirements.txt
```

### 2) 安装前端依赖

```bash
cd src/web
npm install
cd ../..
```

### 3) 启动项目

#### 方式 A：默认启动前端

```bash
python run.py
```

#### 方式 B：仅启动后端

```bash
python run.py --backend
```

后端默认地址：`http://127.0.0.1:5000`

#### 方式 C：仅启动前端

```bash
python run.py --frontend
```

前端默认地址：`http://127.0.0.1:5173`

#### 方式 D：前后端同时启动（两个终端）

```bash
python run.py --backend
python run.py --frontend
```

## 配置说明

### 数据库配置

默认使用 SQLite，本地文件数据库地址为：

- `sqlite:///ai_investment.db`

可通过环境变量覆盖：

```bash
set DATABASE_URL=mysql+pymysql://user:password@host:3306/dbname
```

> Windows PowerShell 可使用：`$env:DATABASE_URL="..."`

### 密钥与安全

- JWT 密钥目前在代码中为默认值，仅适用于开发环境
- 生产环境请务必改为环境变量并关闭 debug

### Agent 编排器切换

可通过环境变量控制主分析链路编排方式：

```bash
set AGENT_ORCHESTRATOR=auto
```

可选值：

- `auto`：优先使用 LangChain 编排，不可用时自动回退自研编排
- `langchain`：优先 LangChain（异常时仍回退并记录原因）
- `custom`：仅使用自研编排

## API 概览

后端服务入口：`src/api/main.py`

常用路由：

- `GET /`：服务状态
- `GET /api/health`：健康检查
- `POST /api/auth/register`：注册
- `POST /api/auth/login`：登录
- `GET /api/user/profile`：获取用户信息
- `PUT /api/user/profile`：更新用户信息
- `PUT /api/user/phone`：更新手机号
- `PUT /api/user/password`：更新密码

其余业务路由见：

- `src/api/agent.py`
- `src/api/stock.py`
- `src/api/news.py`
- `src/api/chat.py`

### Agent 链路说明

- 主分析链路：`POST /api/agent/analyze`、`POST /api/agent/query`
	- 由 `AgentWorkflowExecutor` 异步启动
	- 调用 `MasterAgent.execute_phase2()` 进行多 Agent 编排
	- 输出包含 `task_plan`、`agent_results`、`degraded`、`recommendation`
- 聊天简答链路：`POST /api/chat/ask`
	- 由 `DecisionAgent.run_tools(max_rounds=1)` + `InvestmentExpertAgent.summarize_brief()` 组成

## 前端开发

进入前端目录：

```bash
cd src/web
```

常用命令：

```bash
npm run dev      # 开发
npm run build    # 构建
npm run preview  # 预览
npm run lint     # 代码检查
```

## RAG 知识库

RAG 相关目录在 `src/rag/`，包含：

- 原始知识文件与清洗分块
- 索引构建脚本
- Chroma 持久化索引

可按需执行：

- `src/rag/scripts/build_index.py`
- `src/rag/scripts/build_chroma_index.py`
- `src/rag/scripts/query_index.py`

## 测试

项目中已包含测试目录，可按需执行：

```bash
python -m pytest src/agent/test/test_master_agent.py -v
python -m pytest src/news/test/test_news_api.py -v
python -m pytest src/stock/test/test_akshare_api.py -v
python -m pytest src/utils/test/test_web_search.py -v
```

## 常见问题

- 启动后端报模块导入错误：请确认在项目根目录运行命令。
- 前端无法启动：请确认 Node.js 与 npm 已安装，且已执行 `npm install`。
- 股票或新闻数据异常：可能与网络状态、数据源可用性有关。
- RAG 检索效果不佳：请先重新构建索引并检查 `src/rag/data/` 内容。

## 免责声明

本项目仅用于学习与研究，不构成任何投资建议。投资有风险，决策需谨慎。
