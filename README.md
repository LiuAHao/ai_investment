# AI 投资分析系统

基于 **Flask + React + 多 Agent 协作** 的投资研究平台（demo 形态，无登录）。系统通过"编排 Agent 按需调度 → 调研 Agent 并行研究 → 总结 Agent 综合输出"的流程回答投资问题。

## 核心架构

```
用户问题
   │
   ▼
OrchestratorAgent（总编排）
   │  识别意图 → 资产解析 → 按需调度
   ▼
┌──────────────── 并行执行（线程池）────────────┐
│  MarketAgent     NewsAgent     KnowledgeAgent │
│  (行情/技术面)   (新闻/舆情)    (知识/基本面)    │
│  每个都是独立 ReAct Agent：                   │
│  LLM 思考 → 自主调工具 → 观察 → 再思考 → 收敛  │
└───────────────────┬───────────────────────────┘
                    ▼
         SummaryAgent（总结分析，可再调工具核实）
                    │
                    ▼
                 最终投资结论
```

### 特点

- **真多 Agent**：每个调研 Agent 由 LLM 驱动，自主决定工具调用序列（function calling 优先，JSON 兜底），循环边界由 Agent 自己判断
- **按需调度**：编排 Agent 只启动必要的调研 Agent（如"市场环境"只需 Market + News），前端只渲染实际启动的卡片
- **并行执行**：三个调研 Agent 通过 `ThreadPoolExecutor` 并行运行
- **前端聚焦执行过程**：实时展示编排思考、各 Agent 思考流与工具调用、最终报告
- **SSE 实时推送**：任务全程事件流，支持断线重连补发快照

## 技术栈

- 后端：`Python`、`Flask`、`pydantic`
- Agent：自研 ReAct 循环（OpenAI 兼容 function calling）
- 前端：`React`、`Vite`
- 数据：`AKShare`、`Tushare`、`ChromaDB`、`sentence-transformers`
- 检索：混合检索（向量 + 关键词 + RRF + Rerank）

## 项目结构

```text
ai_investment/
├── run.py                      # 启动脚本（前后端快捷启动，自动选择 Node 版本）
├── requirements.txt            # Python 依赖
├── docs/                       # 设计文档与历史记录
└── src/
    ├── api/                    # Flask API 层
    │   ├── main.py             # 应用工厂
    │   ├── events.py           # SSE 事件流
    │   └── routes/             # 路由（agent / history）
    ├── agents/                 # ★ 多 Agent 核心
    │   ├── orchestrator.py     # 总编排 Agent
    │   ├── base.py             # BaseReActAgent 基类
    │   ├── loop.py             # ReAct 循环执行器
    │   ├── research/           # 三个调研 Agent
    │   ├── summary_agent.py    # 总结分析 Agent
    │   ├── state.py            # 状态模型
    │   ├── events.py           # Agent 事件发射
    │   └── memory.py           # 内存会话
    ├── asset/                  # 资产主数据与解析
    ├── tools/                  # 工具层（注册中心 + 11 个工具）
    ├── data/                   # 数据源（行情 / 新闻）
    ├── rag/                    # RAG 知识库（检索）
    ├── services/               # 事件总线等
    ├── utils/                  # LLM 客户端、联网搜索等
    └── web/                    # React 前端
```

## 环境要求

- Python `3.10+`（建议 `3.11`）
- Node.js `20.19+` 或 `22.12+`（Vite 7 要求）

## 快速开始

### 1) 创建并激活虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) 安装依赖

```bash
# Python 依赖
pip install -r requirements.txt

# 前端依赖
cd src/web && npm install && cd ../..
```

### 3) 配置环境变量

编辑 `.env` 文件，填入有效的 API Key：

```bash
# DeepSeek（推荐）或 OpenAI 二选一
DEEPSEEK_API_KEY=sk-xxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
# 或
OPENAI_API_KEY=sk-xxxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Tushare 数据源（更稳定的行情数据，可选，填了优先于 akshare）
# 注册: https://tushare.pro ，首页个人主页获取 token
TUSHARE_TOKEN=你的tushare-token
```

### 4) 启动服务

前后端需分别在两个终端中启动（均需先激活虚拟环境）：

```bash
# 终端 1 — 后端（默认端口 5001）
python run.py --backend

# 终端 2 — 前端（默认端口 5173）
python run.py --frontend
```

其他启动方式：

| 命令 | 说明 |
|------|------|
| `python run.py` | 默认启动前端 |
| `python run.py --backend --port 5003` | 指定后端端口 |
| `python run.py --frontend --api-url http://localhost:5003` | 指定后端地址 |

## API 概览

后端服务入口：`src/api/main.py`

| 路由 | 方法 | 说明 |
|------|------|------|
| `/` | GET | API 信息（name / version / status） |
| `/api/health` | GET | 健康检查 |
| `/api/agent/query` | POST | 提交研究任务，返回 `{task_id, session_id}` |
| `/api/agent/events/<task_id>` | GET | SSE 事件流（Agent 实时进度，30s 心跳） |
| `/api/agent/tasks/<task_id>` | GET | 查询任务状态 |
| `/api/history` | GET | 会话列表（内存态） |
| `/api/history/<session_id>` | GET | 会话详情 |

### SSE 事件类型

| 事件 | 说明 |
|------|------|
| `connected` / `heartbeat` | 连接建立 / 30s 心跳保活 |
| `orchestrator_thinking` / `orchestrator_decided` | 编排 Agent 思考与派发计划 |
| `agent_started` / `agent_thinking` / `agent_completed` | 调研 Agent 生命周期 |
| `tool_started` / `tool_completed` / `tool_failed` | 工具调用进度 |
| `agent_failed` | Agent 失败 |
| `final_answer` | 最终投资结论 |
| `task_started` / `task_completed` / `task_failed` | 任务生命周期 |

## 前端

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
npm run test     # 测试（vitest）
```

前端核心文件：

- `App.jsx` — 应用入口（视图切换 + 底部常驻输入终端）
- `components/agents/AgentWorkspace.jsx` — 三段式研究流程（编排 → 工位 → 研报）
- `components/agents/AgentCard.jsx` — 单 Agent 执行卡片（思考流 + 工具调用流）
- `components/agents/OrchestratorCard.jsx` — 编排 Agent 卡片
- `components/agents/SummaryCard.jsx` — 总结分析与最终报告
- `components/views/HistoryView.jsx` + `components/agents/TurnDetail.jsx` — 历史会话与详情
- `hooks/useAgentStream.js` — SSE 事件流状态管理
- `services/apiClient.js` — API 封装

## RAG 知识库

RAG 在 `src/rag/`，采用**差异化内容策略**（只装网络给不了的增量）：

- 合规风控规则库、A股交易与监管规则（可溯源）
- 指标口径说明（A股 vs 美股确定性事实）
- 分析框架与工具手册（Agent 工具书）

知识检索统一入口为 `src/rag/knowledge_tool.py` 的 `query_investment_knowledge()`（向量 + 关键词混合检索），查询数据源为 `src/rag/data/chunks/chunks.jsonl` 与 `src/rag/index/chroma/`。

## 免责声明

本项目仅用于学习与研究，不构成任何投资建议。投资有风险，决策需谨慎。
