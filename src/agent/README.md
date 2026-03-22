# agent 模块详细说明

`src/agent` 是系统的智能体编排核心，负责把“用户问题”转成“可执行任务”，再聚合多源结果生成投资建议。当前模块同时支持两条业务链路：

1. Phase 2 主分析链路：多 Agent 协同分析，输出结构化工作流结果。
2. 聊天问答链路：复用主分析编排能力生成回答。

## 目录结构与文件职责

### 1. 核心协议与主控

1. `agent_protocol.py`
定义统一协议与数据结构，是 Phase 2 链路的“契约层”。
包含内容：
- `TASK_PLAN_SCHEMA`：任务计划 JSON Schema 语义定义。
- `AGENT_RESULT_SCHEMA`：单 Agent 结果结构定义。
- `WORKFLOW_RESULT_SCHEMA`：整体工作流返回结构定义。
- `AgentResult`：单 Agent 标准输出 dataclass，字段有 `agent/status/data/error/latency_ms`。
- `WorkflowResult`：工作流标准输出 dataclass，字段有 `query/symbol/degraded/task_plan/agent_results/recommendation/created_at`。

2. `master_agent.py`
Phase 2 主控编排器，负责任务计划、编排选择、执行顺序、降级和结果组装。
核心逻辑：
- 解析股票标的：优先 `SymbolResolver`，失败后基于名称候选 + `DataAgent.fetch_spot_em()` 二次识别。
- 构建任务计划：`data_agent -> news_agent -> knowledge_agent -> analysis_agent`。
- 编排器路由：根据 `AGENT_ORCHESTRATOR` 在 `langchain` 与 `custom` 之间切换。
- 自研执行链路（custom）：顺序执行 `DataAgent/NewsAgent/KnowledgeAgent/AnalysisAgent`。
- 统一输出：返回 `WorkflowResult.to_dict()`。
- 回调支持：`on_agent_complete(agent_name, agent_result)` 用于实时进度上报（供 API 执行器使用）。

3. `langchain_orchestrator.py`
可选编排器实现，基于 LangChain `AgentExecutor` 和工具调用。
核心逻辑：
- `is_available()` 检查 `langchain` 依赖是否可用。
- `_build_executor()` 注册 3 个工具：`data_agent_tool`、`news_agent_tool`、`knowledge_agent_tool`。
- `execute()` 执行 AgentExecutor 后读取 `intermediate_steps`，回填为标准 `AgentResult`。
- 若某工具未被 LLM 调用，会做“补偿调用”，保证数据覆盖。
- 最后统一调用 `AnalysisAgent.analyze()` 产出 `recommendation`。

### 2. 子 Agent 实现（Phase 2 标准四子 Agent）

4. `data_agent.py`
数据 Agent 主实现（`DataAgent`），负责行情抓取、指标计算和市场概览。
主要能力：
- 历史行情：`fetch_daily_hist()`，内部走 `_fetch_hist_with_fallback()`。
- 回退策略：东方财富 -> 腾讯 -> 新浪。
- 技术分析：`analyze_daily_hist()` 与 `analyze_technical_indicators()`。
- 实时快照：`fetch_spot_em()`，支持代码/名称过滤。
- 交易所统计：`fetch_sse_summary()`、`fetch_szse_summary()`、`fetch_sse_deal_daily()`。
- 汇总接口：`summarize()` 返回 `analysis + technical`。
- 兼容处理：`_normalize_symbol()` 统一股票代码格式，`_without_proxy()` 可按环境变量临时禁用代理。
5. `news_agent.py`
新闻 Agent，当前以联网搜索为主，不走 RSS 聚合。
主要能力：
- `search_web_by_keywords()`：关键词拼接后执行联网检索。
- `get_relevant_titles()`：返回标准新闻负载，包含 `timestamp/relevant_titles/web_results`。
- `fetch_titles_with_web()`：按查询词返回联网结果（兼容接口）。

6. `analysis_agent.py`
综合分析 Agent，负责把数据、新闻、知识库结果整合为最终用户可读建议。
主要能力：
- `analyze()`：输入 `data_payload/news_payload/knowledge_payload/preferences`，输出文本结论。
- 支持 `debug_mode` 调试模式与默认使用模式两套提示词策略。
- `_sanitize_payload()` 会移除 `error/traceback/latency_ms/fallback_reason` 等内部字段，防止在使用模式泄露调试信息。

7. `knowledge_agent.py`
知识库 Agent，负责对 RAG 能力做子 Agent 封装，提供统一调用入口。
主要能力：
- `query(query, top_k=5)`：内部调用 `query_investment_knowledge()`，返回知识片段、引用与降级信息。

### 3. 公共能力与包结构

8. `llm_common.py`
LLM 公共工具模块。
主要能力：
- `get_env()`：统一读取环境变量。
- `load_env_file()`：加载项目根目录 `.env` 配置。
- `build_client()`：统一创建 OpenAI 兼容客户端。

9. `symbol_resolver.py`
离线证券代码解析器，优先使用本地主数据 `src/stock/data/stock_zh_a_spot_em.txt`。
主要能力：
- 显式代码识别：文本里出现 `600519` / `SH600519` / `600519.SH` 时直接命中。
- 名称匹配：公司名、别名、拼音与候选词打分匹配。
- 歧义处理：同分候选返回 `ambiguous_pick` 并附候选列表。
- 缓存：查询级 TTL 缓存，减少重复匹配开销。

10. `__init__.py`
包初始化文件，当前为空，用于标记 `agent` 为 Python 包。

11. `test/`
模块相关测试：
- `test_master_agent.py`：主控编排与输出结构。
- `test_data_agent_fallback.py`：股票数据源回退逻辑。
- `test_symbol_resolver.py`：代码解析与匹配结果。

## 端到端调用流程

### A. Phase 2 主分析链路（`/api/agent/analyze`、`/api/agent/query`）

1. API 层创建会话并启动异步执行器 `AgentWorkflowExecutor`。
2. 执行器调用 `MasterAgent.execute_phase2()`。
3. `MasterAgent` 根据 `AGENT_ORCHESTRATOR` 选择编排方式：
- `auto` 或 `langchain`：优先 `LangChainOrchestrator.execute()`。
- 不可用或异常：自动回退 `custom` 并记录 `fallback_reason`。
- `custom`：直接走自研顺序编排。
4. 子 Agent 执行与聚合（四子 Agent）：
- `DataAgent`：股票摘要与技术指标。
- `NewsAgent`：关键词联网新闻。
- `KnowledgeAgent`：RAG 检索。
- `AnalysisAgent`：综合生成 `recommendation`。
5. 执行器通过 `on_agent_complete` 回调写入实时日志、进度和中间结果。
6. 返回标准工作流结果并持久化到会话记录。

### B. 聊天简答链路（`/api/chat/ask`）

1. `MasterAgent.execute_phase2(content, preferences)` 统一完成任务规划与工具调用。
2. 返回 `workflow_result.recommendation` 作为聊天回复。
3. 用户消息与助手回复都写入 `ChatHistory`。

## 协议规范（Phase 2）

### 1. task_plan（任务计划）

语义来源：`TASK_PLAN_SCHEMA`。
关键字段：
- `query: str` 用户原始问题。
- `symbol: str | null` 识别出的股票代码。
- `tasks: list[object]` 计划任务列表。
- 扩展字段：实际运行中会附加 `orchestrator`，回退时可能有 `fallback_reason`。

任务项格式：

```json
{
  "agent": "data_agent",
  "task": "get_stock_summary",
  "params": {"symbol": "600519"}
}
```

### 2. agent_results（单 Agent 结果列表）

语义来源：`AGENT_RESULT_SCHEMA`。
每项字段：
- `agent: str`，如 `DataAgent`。
- `status: completed | failed | skipped`。
- `data: object` 成功或部分结果。
- `error: str | null` 失败或跳过原因。
- `latency_ms: int` 耗时毫秒。

### 3. workflow_result（工作流结果）

语义来源：`WORKFLOW_RESULT_SCHEMA`。
字段：
- `query` 用户问题。
- `symbol` 股票代码或空。
- `degraded` 是否降级（任一 Agent `failed` 即为 `true`）。
- `task_plan` 任务计划。
- `agent_results` 子 Agent 结果集合。
- `recommendation` 最终建议文本。
- `created_at` ISO 时间戳。

## 降级与容错机制

1. 编排层降级
- LangChain 不可用或运行异常时，自动回退到 custom 编排。

2. 数据源降级
- `DataAgent` 历史行情按“东方财富 -> 腾讯 -> 新浪”逐级回退。

3. 结果层降级
- 任一子 Agent 失败时仍返回完整协议结构，`degraded=true`，并在结果中保留失败原因。

## 关键配置项

1. `AGENT_ORCHESTRATOR`
- 取值：`auto | langchain | custom`。
- 默认：`auto`。

2. 行情代理参数（`DataAgent`）
- `AKSHARE_DISABLE_PROXY=1` 时请求前临时移除代理环境变量。

## 开发注意事项

1. 新增子 Agent 时，优先接入 `agent_protocol.py` 定义的统一结构，避免返回格式漂移。
2. 修改 `MasterAgent` 或 `LangChainOrchestrator` 后，需确保 `task_plan` 和 `agent_results` 字段兼容现有 API 持久化逻辑。
3. `AnalysisAgent` 使用模式默认屏蔽内部错误细节，若需排障请通过 `preferences.debug_mode=true` 启用调试提示词。
