# agent 模块简介

agent 模块负责后端智能体编排、数据聚合与分析生成。当前同时维护两条链路：

- 主分析链路（Phase 2）：多 Agent 协同，支持可切换编排器
- 简答链路（聊天）：工具调用 + 简短总结

## 目录与职责

- `master_agent.py`：主控 Agent，执行任务分解、编排、降级与汇总
- `langchain_orchestrator.py`：LangChain `AgentExecutor` 编排实现（可选）
- `agent_protocol.py`：统一任务计划/结果的协议结构（JSON Schema 语义）
- `analysis_agent.py`：分析 Agent，负责综合推理并生成最终建议
- `stock_agent.py`：数据 Agent，提供历史行情与技术指标标准化输出
- `news_agent.py`：新闻 Agent，负责联网搜索与相关新闻聚合
- `decision_agent.py`：工具决策 Agent（主要用于聊天简答链路）
- `investment_expert_agent.py`：投资专家 Agent（主要用于聊天简答链路）

## 后端调用链路

### 1) 主分析链路（`/api/agent/analyze` 与 `/api/agent/query`）

1. API 路由创建会话并异步启动 `AgentWorkflowExecutor`
2. `AgentWorkflowExecutor` 调用 `MasterAgent.execute_phase2()`
3. `MasterAgent` 按配置选择编排器：
	- `AGENT_ORCHESTRATOR=langchain|auto`：优先走 `LangChainOrchestrator`
	- 不可用或异常时自动回退到 `custom` 自研编排
4. 子 Agent 执行：
	- `StockAgent`：行情与技术指标
	- `NewsAgent`：联网新闻
	- `KnowledgeAgent`：`query_investment_knowledge()`
	- `AnalysisAgent`：综合生成建议
5. 返回统一结构：`task_plan`、`agent_results`、`degraded`、`recommendation`

### 2) 聊天简答链路（`/api/chat/ask`）

1. `DecisionAgent.run_tools(max_rounds=1)` 选择并调用工具
2. `InvestmentExpertAgent.summarize_brief()` 基于工具结果输出 3-5 句话简答

## 编排器切换

- 环境变量：`AGENT_ORCHESTRATOR=auto|langchain|custom`
- `auto`（默认）：优先 LangChain，失败自动回退
- `langchain`：强制优先 LangChain（异常时仍会回退并记录原因）
- `custom`：仅使用自研编排

## 统一输出约定（Phase 2）

- `task_plan`：本次任务计划（含编排器信息）
- `agent_results`：每个 Agent 的状态、数据、错误、耗时
- `degraded`：是否触发降级
- `recommendation`：最终建议文本

## 说明

- 当前数据侧以收盘后历史数据与技术指标为主。
- 新闻侧仅保留联网搜索，不再使用 RSS 拉取。
- 任一子 Agent 失败时，主链路会降级输出并明确缺失项，不编造内容。
