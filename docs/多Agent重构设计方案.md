# AI 投资分析系统 · 多 Agent 重构设计方案

> 版本: v3.1 (已纳入设计评审修正)
> 日期: 2026-08-04
> 状态: 方向已确认，评审修正已纳入，进入实施

## 0. 已确认的决策

| # | 决策项 | 结论 |
|---|--------|------|
| 1 | 三个调研 Agent 执行方式 | **并行执行** |
| 2 | SummaryAgent 工具权限 | **给**（可再调工具核实） |
| 3 | 旧代码/灰度回退 | **不保留**。本产品是 demo，不用的功能与代码直接删除 |
| 4 | 模型 function calling 兼容 | **需要兜底**（JSON 输出解析 fallback） |
| 5 | 旧对话/历史数据 | **不保留**，前端完全重构 |
| 6 | 目录框架 | **完全重新设计**，去掉版本号命名（v1/v2），统一职责化模块命名 |
| 7 | 编排 Agent 展示 | 编排 Agent 也展示思考过程（`orchestrator_thinking`） |
| 8 | 调研 Agent 调度 | **按需调度**，前端只渲染实际启动的 Agent 卡片 |
| 9 | 执行并发模型 | **线程池并行**（复用现有 `ThreadPoolExecutor`，不用 asyncio） |
| 10 | 编排 Agent 资产识别 | 封装现有规则逻辑为 `AssetResolveTool`，编排 Agent 以工具调用方式完成资产识别 |
| 11 | 工具命名 | **保留现有工具名**（如 `StockDataTool`），不做无收益改名 |
| 12 | 会话存储 | **内存会话**（进程内），重启清空，不落库 |
| 13 | 知识库内容策略 | **差异化内容**（私有/可信/确定性/沉淀），按半衰期分层更新，详见 §6.3 |
| 14 | 登录/用户系统 | **删除**（demo 无登录，去除 auth/JWT/user 模型/登录页） |
| 15 | 数据源目录 | `src/data/` **合并**旧 `src/stock/` + `src/news/`；`src/asset/`（资产主数据）保留；旧目录删除 |

### 0.1 设计评审修正记录（v3.1 新增）

| # | 问题 | 修正 |
|---|------|------|
| P1 | 同步 OpenAI 客户端与 `asyncio.gather` 冲突，并行会退化成串行 | 统一用**线程池并行**（决策 #9），Agent 方法用同步 `run()` 而非 `async def` |
| P2 | 删除旧 `agent/` 目录会让 `tools/` 的 `agent.v2.state` 导入断裂 | 阶段 1 前置：先迁移 state 模型到 `agents/state.py` 并改 tools 导入，再删旧目录 |
| P3 | 编排 Agent 资产识别依赖规则函数，非工具形态 | 封装现有 `asset_resolver` 规则逻辑为 `AssetResolveTool`，编排 Agent 通过工具调用完成资产识别（决策 #10） |
| P9 | 目录结构遗漏 `src/asset/` 资产主数据模块（`AssetMasterData`，资产识别依赖） | 保留 `src/asset/`（决策 #15） |
| P10 | 登录/用户系统与 demo 定位不符，冗余复杂度 | 删除 auth/JWT/user 模型/登录页（决策 #14） |
| P4 | `orchestrator_decided` 与 `agent_started` 并发，前端渲染时序不稳定 | 前端**只以 `orchestrator_decided.plan` 为准创建卡片**，后续事件仅更新状态 |
| P5 | "历史记录"导航与会话不落库矛盾 | 历史记录页显示进程内会话（决策 #12），重启清空 |
| P6 | 事件协议缺失败事件 | 补充 `tool_failed` / `agent_failed`，并设任务级总超时 |
| P7 | 工具改名（`cn_stock_history`→`stock_history`）无收益且牵动前端 | 保留现有工具名（决策 #11），仅目录职责化 |
| P8 | 三个 Agent 事件在 SSE 流上交错，前端难以归集 | 事件统一携带 `agent` 字段，前端按 agent 分组归集 |

---

## 1. 背景与目标

### 1.1 背景

当前系统本质上是 **LangGraph 静态工作流编排**：固定节点串行（context → route → resolve → plan → execute → evidence → draft → critic → compose → compliance → finalize），其中大多数"Agent"（Router、Planner、Evidence、Critic、Compliance）实际是**规则函数**，只有 `draft_answer` / `analysis` 真正调用了 LLM。

**核心问题**：系统不是"真正的多 Agent"，而是"流水线上的函数调用"。Agent 没有自主思考、没有自我循环、工具使用受静态规划规则约束。

### 1.2 目标

重构为一个**真正的多 Agent 系统**，纯 demo 形态，无历史包袱：

```
用户问题
   │
   ▼
OrchestratorAgent（总编排）
   │  识别意图 → 拆解子任务 → 按需并行调度
   │
   │  （按需：只启动必要的调研 Agent）
   ▼
┌──────────────── 并行执行 ────────────────┐
│  MarketAgent   NewsAgent   KnowledgeAgent │
│  (行情/技术面)  (新闻/舆情)   (知识/基本面)   │
└───────────────────┬───────────────────────┘
                    │ 各调研 Agent 独立 ReAct 循环：
                    │   LLM 思考 → 自主调工具 → 观察 → 再思考 → 收敛
                    ▼
         SummaryAgent（总结分析，可再调工具核实）
                    │
                    ▼
                 最终结论
```

### 1.3 关键原则

1. **Agent 是自主的**：每个 Agent 由 LLM 驱动，自己决定思考方向、工具调用序列，允许"思考 → 行动 → 观察 → 再思考"的循环。
2. **编排是灵活的**：Orchestrator 动态决定派哪些子 Agent（**按需启动**），并行执行，不写死节点序列。
3. **工具是 Agent 的手脚**：所有数据获取都通过工具，工具注册中心保留并扩展。
4. **前端聚焦关键过程**：编排 Agent 思考、各调研 Agent 执行进度（工具调用、思考内容）、最终汇总。

## 2. 现状诊断（旧架构问题清单）

### 2.1 架构层面的问题

| 问题 | 现状 | 后果 |
|------|------|------|
| 伪 Agent | 14 个图节点中约 9 个是规则函数（router/planner/evidence/critic/compliance 等） | 展示给用户的"Agent 流程"实际是 if-else，效果像"假流程" |
| 无自主循环 | 唯一循环是工具失败时 replan（最多 2 次），无"思考-行动-观察"循环 | Agent 无法根据中间结果调整研究策略 |
| 静态规划 | planner 用规则硬编码"股票→历史数据、新闻、知识、分析" | 无法应对复杂、组合型问题（多资产、跨类型） |
| 写死的限制 | 固定迭代次数、replan 上限、evidence 截断等 | 灵活性问题被硬编码 |
| 结构化模板答案 | 情景分析（30/40/30）、操作选项、风险提示均为硬编码模板 | 结论"看着专业，实际是模板" |

### 2.2 复用资产（保留并改造）

- **工具注册中心** `src/tools/registry.py`：资产类型 × 意图 的元数据匹配，结构良好。
- **统一资产模型**：Asset / ToolResult / EvidenceItem 等 pydantic 模型。
- **LLM 客户端封装**：`build_client()` 支持 OpenAI/DeepSeek 兼容协议。
- **SSE 事件总线**：事件流机制，前端可复用。
- **合规与安全能力**：合规正则库、风险词表（改为由 SummaryAgent 调用）。

### 2.3 删除项（demo，不保留）

- 旧 LangGraph 静态图及规则型节点。
- 旧编排层（`master_agent.py`、`langchain_orchestrator.py` 等）。
- 前端旧流程画布、内部节点展示、旧会话历史兼容逻辑。
- 版本号命名（`agent_v2`、`agent_v3`、`apiV2Service` 等）全部废弃。
- **登录/用户系统**：auth、JWT、`models/user.py`、`AuthView`、登录路由（决策 #14）。
- **旧数据源目录**：`src/stock/`、`src/news/` 合并进 `src/data/`（决策 #15）。

## 3. 目标架构

### 3.1 总览（Supervisor 模式）

```
┌─────────────────────────────────────────────┐
│         OrchestratorAgent（Supervisor）       │
│   LLM 驱动：意图/资产识别 → 任务拆解 → 按需调度  │
└──────┬──────────────┬──────────────┬─────────┘
       │    按需并行    │              │
       ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ MarketAgent │ │ NewsAgent   │ │ KnowledgeAgent│
│ (行情/技术面)│ │ (新闻/舆情)  │ │ (知识/基本面) │
└─────────────┘ └─────────────┘ └─────────────┘
       │              │              │
       └──────────────┴──────────────┘
                     │  调研结果汇总
                     ▼
        ┌───────────────────────┐
        │   SummaryAgent        │
        │   综合分析 → 可再调工具确认 │
        │   → 最终投资结论        │
        └───────────────────────┘
```

**按需调度示例**：问题「市场环境怎么样」→ 编排 Agent 判断只需 Market + News 两路，KnowledgeAgent 不启动，前端不渲染其卡片。

### 3.2 后端目录结构（重构后，全新设计）

```
src/
├── api/                        # HTTP API 层（Flask）
│   ├── __init__.py
│   ├── main.py                 # 应用工厂 / 蓝图注册
│   ├── routes/                 # 路由模块（按资源拆分）
│   │   ├── __init__.py
│   │   ├── agent.py            # Agent 研究接口（提交/SSE 事件流）
│   │   └── history.py          # 会话历史接口
│   └── wsgi.py                 # 启动入口
│
├── agents/                     # ★ 多 Agent 核心（全新）
│   ├── __init__.py
│   ├── orchestrator.py         # 总编排 Agent（Supervisor，LLM 调度 + AssetResolveTool）
│   ├── base.py                 # BaseReActAgent 抽象基类（思考/工具/收敛）
│   ├── loop.py                 # ReAct 循环执行器（思考→行动→观察 + JSON 兜底）
│   ├── research/               # 调研 Agent（并行）
│   │   ├── __init__.py
│   │   ├── market_agent.py     # 市场/行情调研 Agent
│   │   ├── news_agent.py       # 新闻/舆情调研 Agent
│   │   └── knowledge_agent.py  # 知识/基本面调研 Agent
│   ├── summary_agent.py        # 总结分析 Agent（综合 + 可再调工具）
│   ├── state.py                # ★ 状态模型（Asset/ToolResult/AgentTask/AgentResult）
│   │                           #   从旧 agent/v2/state.py 迁移而来，tools 层也依赖此
│   ├── events.py               # Agent 事件发射（agent_thinking / tool_* / agent_*）
│   └── memory.py               # 会话记忆与追问上下文（进程内内存）
│
├── asset/                      # 资产主数据（决策 #15，保留）
│   ├── __init__.py             # AssetMasterData / get_asset_master()（名称→代码搜索）
│   ├── resolver.py             # 资产解析规则（正则提取 + 主数据搜索，供 AssetResolveTool 封装）
│   └── data/                   # 资产静态数据表
│
├── tools/                      # 工具层（保留现有工具名，仅目录归置）
│   ├── __init__.py
│   ├── registry.py             # 工具注册中心（资产类型 × 意图）
│   ├── base.py                 # ToolSpec 工具规格（import 改为 agents.state）
│   ├── asset_tools.py          # 资产解析工具（AssetResolveTool，编排 Agent 专用）
│   ├── stock_tools.py          # 行情/财务工具（StockDataTool/StockSpotTool）
│   ├── news_tools.py           # 新闻检索工具（NewsSearchTool）
│   ├── knowledge_tools.py      # 知识库/RAG 工具（KnowledgeQueryTool）
│   ├── fund_tools.py           # 基金工具（FundNavTool/FundProfileTool）
│   ├── etf_tools.py            # ETF 工具（EtfProfileTool/EtfTrackingTool）
│   ├── us_stock_tools.py       # 美股工具（UsStockQuoteTool/UsStockHistoryTool）
│   ├── analysis_tools.py       # 分析工具（AnalysisTool）
│   └── executor.py             # 工具执行器（并行/超时/错误处理）
│
├── services/                   # 通用服务
│   ├── __init__.py
│   ├── task_service.py         # 异步任务队列（后台线程）
│   └── event_bus.py            # SSE 事件总线（队列 → 推送）
│
├── models/                     # 数据模型（进程内，决策 #12）
│   ├── __init__.py
│   ├── session.py              # 会话记录（内存）
│   └── history.py              # 历史记录（内存）
│
├── data/                       # 数据源层（合并旧 stock/ + news/，决策 #15）
│   ├── __init__.py
│   ├── akshare_client.py       # A股数据（自旧 src/stock/）
│   ├── us_client.py            # 美股数据
│   ├── fund_client.py          # 基金数据
│   └── news_client.py          # 新闻源（自旧 src/news/）
│
├── rag/                        # 知识库检索
│   ├── __init__.py
│   ├── indexer.py              # 索引构建（含 add_knowledge() 写入接口，§6.3）
│   ├── retriever.py            # 检索器
│   └── loader.py               # 文档加载
│
├── utils/                      # 通用工具
│   ├── __init__.py
│   ├── logger.py               # 日志
│   ├── config.py               # 配置读取（.env）
│   └── security.py             # 敏感信息处理
│
└── web/                        # React 前端（见 7.4）
```

### 3.3 命名规范

- **Agent 类**：`XxxAgent`（如 `MarketAgent`），职责化命名。
- **模块**：按职责分层（`agents` / `tools` / `data` / `services`），**不使用版本号**。
- **API 路由**：`/api/agent/query`、`/api/agent/events`（去掉版本路径）。
- **前端**：统一 `apiClient.js` + `useAgentStream`，废弃 `apiV2Service` 等旧命名。

## 4. 核心机制：BaseReActAgent（重构的灵魂）

### 4.1 统一的 ReAct 循环

每个调研 Agent 与 SummaryAgent 都基于同一个基类，跑同一个循环：

```
for turn in range(max_iterations):        # 安全上限可配（默认 8）
    thought = llm(reasoning, history, tool_descriptions)
    if thought.decision == "final_answer":
        break                             # Agent 自己决定完成
    tool_call = thought.tool_call          # Agent 自主选择工具与参数
    observation = execute(tool_call)       # 执行真实工具
    history.append(observation)            # 观察结果回到上下文
return final_answer
```

关键点：
- **循环边界不写死**：由 Agent 的 LLM 判断是否还需要更多信息，仅设安全上限（默认 8 轮，可配置）。
- **工具由 Agent 自己选**：通过 LLM function-calling 协议，把工具 schema 交给模型。
- **每个 Agent 可见的工具子集不同**：工具权限矩阵绑定，避免新闻 Agent 乱调行情工具。
- **并行执行（P1 修正）**：复用现有同步 OpenAI 客户端，三个调研 Agent 通过 `concurrent.futures.ThreadPoolExecutor` 并行运行（每个 Agent 一个工作线程），Agent 方法为**同步 `run()`**，不使用 asyncio。并行上限 3，超时由工具层与任务层双重控制。

> ⚠ 执行模型说明：当前 `build_client()` 返回同步 `OpenAI` 客户端，若用 `asyncio` 并行会导致 LLM 阻塞事件循环、并行失效。故统一采用**线程池并行**。

### 4.2 工具调用协议

复用 OpenAI 兼容的 function calling（`build_client()` 已支持）：

```python
response = client.chat.completions.create(
    model=model,
    messages=messages,               # system + history + thought
    tools=[schema for schema in agent_tool_schemas],  # 本 Agent 可见的工具
    tool_choice="auto",
)
```

**兜底机制（决策 #4）**：当模型未返回标准 `tool_calls`（个别模型/配置不支持）时，`loop.py` 解析 LLM 输出的 JSON 字段（`{"decision": "call_tool", "tool": ..., "params": ...}`）作为降级方案。

### 4.3 BaseReActAgent 接口

```python
class BaseReActAgent:
    name: str                  # 例如 "MarketAgent"
    description: str           # 给 Orchestrator 看的职责说明
    tool_names: List[str]      # 本 Agent 可用的工具白名单
    system_prompt: str         # 角色与目标
    max_iterations: int = 8    # 安全上限

    def run(self, task: AgentTask, shared_state) -> AgentResult:
        # 1. 加载上下文（继承会话/追问历史）
        # 2. 执行 ReAct 循环（loop.py）
        # 3. 产出：结论文本 + 证据引用 + 工具调用记录
        # 4. 全程通过 events.py 发射 agent_thinking / tool_started / tool_completed
        ...
```

### 4.4 事件协议（前端展示的基石）

| 事件 | 载荷要点 | 前端展示 |
|------|---------|---------|
| `orchestrator_thinking` | `{thought}` | 编排 Agent 思考过程 |
| `orchestrator_decided` | `{plan: [agent名单], reason}` | 研究计划 + 编排结论（前端据此创建卡片） |
| `agent_started` | `{agent, task, goal}` | Agent 卡片开始 |
| `agent_thinking` | `{agent, thought}` | 思考内容日志 |
| `tool_started` | `{agent, tool, params}` | 工具调用中 |
| `tool_completed` | `{agent, tool, status, latency, summary}` | 工具结果摘要 |
| `tool_failed` | `{agent, tool, error}` | 工具失败（标红） |
| `agent_failed` | `{agent, error}` | Agent 失败（卡片标红） |
| `agent_completed` | `{agent, result_summary, evidence_refs}` | Agent 卡片完成 |
| `final_answer` | `{answer, key_points, risks, evidence_refs}` | 最终结论 |

**关键设计：按需调度**。编排 Agent 只启动必要的调研 Agent（前端只渲染实际启动的卡片），不固定三个全开。

**前端渲染时序（P4 修正）**：前端**只以 `orchestrator_decided.plan` 为准创建 Agent 卡片**，其后的 `agent_started / agent_thinking / tool_*` 事件仅更新已有卡片状态，不新增/删除卡片，避免并发渲染抖动。

**事件归集（P8 修正）**：所有 Agent 级事件统一携带 `agent` 字段，前端 `useAgentStream` 按 `agent` 分组归集到对应卡片（SSE 流上三个 Agent 事件是交错的）。

## 5. 各 Agent 设计

### 5.1 OrchestratorAgent（总编排）

**职责**（LLM 驱动 + AssetResolveTool）：
1. **识别资产与意图**：通过 `AssetResolveTool` 完成（该工具封装现有 `asset_resolver` 规则逻辑 + `AssetMasterData` 主数据，如"茅台"→`600519`）。复用成熟规则，不重复造轮子，同时保持编排 Agent 的"LLM + 工具"形态。
2. **按需调度**：根据问题类型决定派发哪些调研 Agent（如"市场环境"只需 Market + News，不启动 Knowledge）。
3. 资产歧义时向用户提问澄清。
4. 汇总各 Agent 结果交给 SummaryAgent。

**可见工具**：`AssetResolveTool`（唯一工具，保持编排层轻量）。资产解析是确定性任务，规则实现更快更稳，不作为调研工具暴露给其他 Agent。

**展示**（前端）：
- 编排 Agent 的思考过程通过 `orchestrator_thinking` 实时展示。
- 最终派发计划通过 `orchestrator_decided` 展示：实际启动的 Agent 名单 + 理由。
- **前端只渲染实际启动的 Agent 卡片**，未启动的 Agent 不出现。

**示例**（问题：市场环境怎么样）：
```
[Orchestrator] 💭 识别到宏观市场问题，涉及整体行情与新闻舆情，
                无需深度知识库，派发 Market + News 两个调研 Agent
[Orchestrator] 📋 已启动：MarketAgent + NewsAgent（理由：宏观环境，两路足够）
```

### 5.2 三个调研 Agent（并行，按需启动）

| Agent | 职责 | 可见工具（示例，保留现有注册名，P7） |
|-------|------|-------------------------------------|
| `MarketAgent` | 行情/财务/技术面研究 | `StockDataTool`、`StockSpotTool`、`UsStockQuoteTool`、`FundNavTool`、`EtfProfileTool` |
| `NewsAgent` | 新闻/舆情研究 | `NewsSearchTool`、`AssetNewsSearchTool`（如存在） |
| `KnowledgeAgent` | **查档案 + 沉淀经验**（知识库/基本面/框架，见 §6.3） | `KnowledgeQueryTool`（RAG 检索） |

每个 Agent 内：
- `system_prompt` 定义角色、研究目标、输出要求。
- ReAct 循环自主决定调用哪些工具、调用几次、何时收敛。
- 产出 `AgentResult`：结论文本 + 引用证据 + 工具调用记录 + 思考轨迹。

### 5.3 SummaryAgent（总结分析 Agent）

**职责**（决策 #2：给工具权限）：
1. 读取所有调研 Agent 的 `AgentResult`。
2. 自主综合分析：投资逻辑、关键判断、主要风险。
3. **可再调用工具确认**：发现数据矛盾或需核实时，再调用行情/新闻/知识工具。
4. 输出最终结构化结论：`summary / key_points / risks` 全部由 LLM 生成。

## 6. 状态与会话

### 6.1 状态模型（P2 修正：先迁移再删旧代码）

状态模型统一收敛到 `agents/state.py`（由旧 `agent/v2/state.py` 迁移）：
- `AssetType` / `Asset` / `ToolResult` / `EvidenceItem` 等**保持原定义不变**（tools 层 import 同步改指向 `agents.state`）。
- 新增：

```python
class AgentTask(BaseModel):
    agent_name: str
    goal: str                 # 编排器派发的任务目标
    assets: List[Asset]
    context: str              # 相关上下文/追问历史

class AgentResult(BaseModel):
    agent_name: str
    conclusion: str           # Agent 自己的研究结论
    evidence_refs: List[str]
    tool_calls: List[ToolResult]
    thinking_log: List[str]   # 思考轨迹（前端展示用）
```

**迁移顺序（硬性要求）**：阶段 1 必须先 (a) 建 `agents/state.py` → (b) 改 `tools/base.py`、`tools/registry.py` 的 import → (c) 验证工具可运行 → (d) 才能删旧 `agent/` 目录。

> **schemas 归属（R4）**：旧 `agent/v2/schemas.py` 中的 `AssetResolveResponse` 等 schema 一并归入 `agents/state.py`（或拆 `agents/schemas.py`），随迁移一并处理。

### 6.2 会话与追问（决策 #5 + #12）

- **内存会话**：会话仅存进程内（`agents/memory.py`），不落库，重启清空。
- 历史记录页显示进程内会话；新会话从新格式开始，旧历史不迁移。
- 追问时：Orchestrator 将上一轮结论作为上下文注入新任务，各 Agent 继承资产与偏好。

### 6.3 知识库（RAG）内容策略（决策 #13）

#### 6.3.1 现状诊断

现有知识库 `src/rag/data/raw/` 仅含 6 个**静态教材文档**（财务指标/估值框架/技术分析/行业模板/A股规则/合规话术）。问题：这些内容网络可免费获取且质量更好，**未提供任何"网络搜不到"的增量**，故 KnowledgeAgent 实际价值趋近于零。

#### 6.3.2 差异化定位：RAG 只装"网络给不了的 4 类增量"

| 类别 | 内容示例 | 价值点 |
|------|---------|--------|
| **私有/可信** | 公司投资策略、风控红线、内部研报、历史分析笔记、Agent 决策记录 | 网络永远搜不到 |
| **确定性事实** | 指标计算口径（PE/ROE 在 A 股 vs 美股 GAAP 差异）、财报科目定义、退市/ST 规则、监管条例原文 | 可精确引用、可溯源 |
| **结构化深度知识** | 券商研报精华（定期导入）、行业专题报告、宏观分析框架 | 网络碎片化、噪音多 |
| **Agent 工具书** | 各 Agent 领域知识卡片、工具使用手册、常见问题标准分析方法 | 提升 Agent 决策质量 |

#### 6.3.3 内容挑选标准（候选文档打分决策）

```
1. 网络能搜到高质量同款吗？ → 能 → 淘汰（交给 NewsAgent）
2. 时效性要求高吗？         → 高 → 淘汰（动态源，不走静态 RAG）
3. 需要精确引用/可溯源吗？  → 是 → 进 RAG（如监管规则原文）
4. 是私有/内部/沉淀内容吗？ → 是 → 进 RAG（如决策记录）
```

#### 6.3.4 分层更新机制（解决"静态"问题）

按内容**半衰期**分三层：

| 层 | 内容 | 更新频率 | 机制 |
|----|------|---------|------|
| **L1 静态知识** | 指标口径、交易规则、分析框架 | 数月 | 手动导入 |
| **L2 定期知识** | 券商研报、行业专题、财报摘要 | 周/月 | 定时任务批量摄入（LLM 清洗 + 人审） |
| **L3 沉淀知识** | 每次研究的结论/案例/决策 | 实时 | **研究完成后自动写回 RAG**（Agent 自学习） |

**L3 是让 RAG 真正"活起来"的关键**：每个研究任务结束后，SummaryAgent 的结论按模板沉淀进知识库，下次同类问题直接命中——这是网络搜索永远做不到的增量。

#### 6.3.5 落地到本项目（demo 范围）

1. **替换内容**：删除 6 个通用教材文档，换成 3 类差异化内容——
   - 合规/风控规则库（可溯源，配合 SummaryAgent 校验）
   - 个股/行业结构化档案（基本面字段说明、指标口径）
   - 分析框架沉淀（每轮研究写回，L3）
2. **改造 KnowledgeAgent**：从"查教材"改为"查档案 + 沉淀经验"。
3. **保留检索管线**：现有 Chroma + embedding + 混合检索 + rerank 已是标准方案，质量没问题，**只需替换喂进去的内容**。
4. **新增写入接口**：`rag/indexer.py` 增加 `add_knowledge()`（供 L3 沉淀），任务完成后由 SummaryAgent 或编排器调用。

## 7. 前端展示设计（聚焦 Agent 执行）

### 7.1 页面结构（按需调度示例：只启动 Market + News）

```
┌──────────────────────────────────────────────────────┐
│  顶部导航：Logo · 新对话 · 历史记录                    │
├──────────────────────────────────────────────────────┤
│  输入区：问题输入框 + 风险偏好选择 + [开始研究]         │
├──────────────────────────────────────────────────────┤
│  OrchestratorAgent（编排 Agent 卡片，展示思考过程）     │
│  ┌────────────────────────────────────────────────┐ │
│  │ 💭 识别到宏观市场问题，涉及行情与新闻舆情，        │ │
│  │    无需深度知识库 → 派发 Market + News 两个 Agent │ │
│  │ 📋 已启动：MarketAgent + NewsAgent              │ │
│  │ ↳ 理由：宏观环境调研，两路并行足够                │ │
│  └────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────┤
│  调研 Agent 卡片（动态列，只渲染实际启动的 Agent）     │
│  ┌─ MarketAgent ──────┐ ┌─ NewsAgent ─────┐         │
│  │ 思考中              │ │ 已完成          │         │
│  │ 💭 先看大盘趋势...   │ │ 💭 检索相关新闻..│         │
│  │ 🔧 stock_spot(500)  │ │ 🔧 news_search()│         │
│  │    ↓ 获取 3824 只   │ │    ↓ 返回 8 条  │         │
│  │ 💭 行情偏弱，再看.. │ │ 💭 舆情偏中性..  │         │
│  └────────────────────┘ └────────────────┘         │
│  （KnowledgeAgent 未启动 → 不渲染）                 │
├──────────────────────────────────────────────────────┤
│  SummaryAgent（总结分析）                            │
│  ┌────────────────────────────────────────────────┐ │
│  │ 💭 综合两路调研...再核实一下最新数据              │ │
│  │ 🔧 news_search(...) → ✅ 复核完成               │ │
│  │                                                │ │
│  │ 📄 最终结论：                                   │ │
│  │   【总体判断】...                               │ │
│  │   【关键判断】...                               │ │
│  │   【主要风险】...                               │ │
│  │                                                │ │
│  │ 证据引用：[行情1] [新闻2]                      │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### 7.2 组件拆分

| 组件 | 职责 | 数据来源 |
|------|------|---------|
| `OrchestratorCard` | 编排 Agent 卡片：思考流 + 派发计划（谁被启动、为什么） | `orchestrator_thinking / orchestrator_decided` |
| `AgentCard` | 单调研 Agent 执行卡片：状态徽标 + 思考流 + 工具调用流 | `agent_started / agent_thinking / tool_* / agent_completed` |
| `FinalReport` | 最终结论（summary / key_points / risks + 证据引用） | `final_answer` |
| `AgentWorkspace` | 动态列布局 + Summary 区 | 状态机聚合 |

### 7.3 交互细节

- **AgentCard 状态徽标**：`思考中 / 工具调用中 / 已完成`（无"等待调度"——未启动的 Agent 根本不渲染）。
- **动态列**：实际启动 N 个 Agent，就渲染 N 列（1-3 列自适应）；窄屏纵向堆叠。
- **思考内容**：`agent_thinking` 实时追加，可折叠。
- **工具调用**：`tool_started` 显示工具名+参数摘要（敏感参数截断），`tool_completed` 显示耗时+结果摘要，失败标红。
- **Summary 完成后**：AgentCard 区可折叠，突出最终报告。

### 7.4 前端目录（重构后）

```
src/web/src/
├── App.jsx
├── views/
│   ├── ResearchView.jsx        # 研究页（核心页面，无登录直接进入）
│   └── HistoryView.jsx         # 历史记录（进程内会话）
├── components/
│   ├── agents/
│   │   ├── OrchestratorCard.jsx
│   │   ├── AgentCard.jsx
│   │   ├── FinalReport.jsx
│   │   └── AgentWorkspace.jsx
│   ├── common/                 # 通用组件（按钮/输入/标签等）
│   └── layout/                 # 布局组件（导航/页头等）
├── services/
│   └── apiClient.js            # 统一 API 客户端（含 SSE）
├── hooks/
│   └── useAgentStream.js       # SSE 订阅 Hook
├── styles/
│   └── global.css
└── utils/
    └── format.js               # 格式化工具
```

> **无登录（决策 #14）**：demo 无登录页/鉴权，`App.jsx` 直接进入研究页。

## 8. 实施路径

### 阶段 1：核心循环与基类（1-2 天）
1. **前置（P2）**：建 `agents/state.py`（迁移状态模型）→ 改 `tools/base.py`、`tools/registry.py` 的 import → 验证工具可运行。
2. 实现 `agents/loop.py`：ReAct 循环执行器（LLM 思考 + function calling + JSON 兜底，同步实现）。
3. 实现 `agents/base.py`：`BaseReActAgent`（同步 `run()`）。
4. 接入现有 `build_client()` 与 `ToolRegistry`，跑通最小 MarketAgent。

### 阶段 2：三个调研 Agent + 并行编排（2-3 天）
1. 实现 MarketAgent / NewsAgent / KnowledgeAgent。
2. **知识库内容替换（决策 #13）**：删除 6 个通用教材文档，导入 3 类差异化内容（合规规则库、个股/行业档案、分析框架）；实现 `rag/indexer.py` 的 `add_knowledge()` 写入接口（供 L3 沉淀）。
3. 实现 `agents/orchestrator.py`（LLM 调度 + 规则兜底 + 按需启动）；封装 `tools/asset_tools.py` 的 `AssetResolveTool`（复用 `asset/resolver.py` 规则）。
4. **线程池并行（P1）**：`ThreadPoolExecutor(max_workers=3)` 并行执行；会话状态（内存）、追问继承。

### 阶段 3：SummaryAgent + 事件流（1-2 天）
1. 实现 `agents/summary_agent.py`（综合分析 + 可再调工具）。
2. **L3 沉淀（决策 #13）**：任务完成后由编排器将结论写入 RAG（`add_knowledge()`），实现 Agent 自学习闭环。
3. 定义并发射全部 `agent_* / tool_* / orchestrator_*` 事件。
4. 新建 API 路由 `/api/agent/query` + `/api/agent/events`，复用事件总线 + SSE。

### 阶段 4：前端重构（2-3 天）
1. 新建 `OrchestratorCard / AgentCard / FinalReport / AgentWorkspace`。
2. 实现 `useAgentStream` SSE Hook + `apiClient.js`。
3. 删除旧流程画布、旧组件、旧历史兼容。

### 阶段 5：清理与收尾（1 天）
1. 删除旧代码：静态图、旧编排层、旧 API、旧前端组件、**登录/用户系统（决策 #14）**、旧数据源目录 `src/stock/`、`src/news/`（决策 #15）。
2. 合规兜底、超时/并发/降级处理。
3. 端到端验证。

> 总工期约 8-11 个工作日。

## 9. 风险与对策

| 风险 | 对策 |
|------|------|
| LLM 工具调用不稳定（幻觉参数） | 工具 schema 严格校验 + 失败重试一次 + 错误注入回 LLM |
| 循环不收敛 | 安全上限（可配置）+ 单调性检测（无新增信息即收敛） |
| 并行调用资源/成本增加 | 并行度有限、每 Agent 迭代上限、token 预算 |
| 工具权限过大（乱调） | 工具白名单矩阵按 Agent 绑定 |
| 结果不一致/矛盾 | SummaryAgent 识别矛盾并驱动复核 |
| 模型不支持 function calling | JSON 输出解析兜底（决策 #4） |

## 10. 验收标准

1. 一个问题可看到：编排 Agent 思考 → 按需启动调研 Agent → 并行思考/调工具 → 汇总 Agent 综合 → 最终结论。
2. 前端展示 Agent 卡片（思考 + 工具调用 + 结果），只渲染实际启动的 Agent（以 `orchestrator_decided.plan` 为准创建，P4）。
3. 三个调研 Agent 真并行（线程池），工具失败有 `tool_failed` 事件且不影响其他 Agent（P1/P6）。
4. 追问可继承上下文；多资产/组合问题可动态调度多个 Agent。
5. 旧代码与版本号命名已删除；工具层 import 已切换到 `agents.state`（P2）。
6. 会话为内存态，重启清空（P5）。
7. 无登录/用户系统，应用直接进入研究页（决策 #14）。
8. 资产识别通过 `AssetResolveTool` 完成（"茅台"→代码），资产主数据 `src/asset/` 保留（决策 #15）。
