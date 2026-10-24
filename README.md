# AI 投资分析系统

基于 **Flask + React + 多 Agent 协作** 的投资研究平台（demo 形态，无登录）。系统按「研究主管 → 多路取证 → 多空辩论 → 裁决 → 质检 → 决策落库」的六层流水线产出可追溯的投资判断。

## 核心架构

```
用户问题
   │
   ▼
L0 ResearchSupervisor（规则保底 + LLM 加派）
   │  资产解析 / 研究计划 / focus_questions / 预算
   ▼
L1 四路分析师并行（只交证据，不下结论）
   MarketAnalyst   NewsAnalyst   FundamentalAnalyst   MacroAnalyst
   └──────────────┬──────────────────┬─────────────────┘
                  ▼
        EvidenceLedger（结构化证据台账，EV-xxxx 可追溯）
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
   BullThesis           BearThesis      （并行、互不可见）
        └─────────┬─────────┘
                  ▼
   L3 结构化辩论（攻击六类 → 防守/修正/让步，最多 2 轮）
                  ▼
   L4 裁决（先盲判，再读辩论出终判，必须写修订理由）
                  ▼
   L5 质检（引用/数字/口径/时效/合规 + LLM 逻辑检查，有界回退）
                  ▼
   L6 DecisionRecord → SQLite → 到期结算 → 反思回灌
```

### 特点

- **事实与判断分离**：分析师只交证据，结论只出现在论点和裁决里；任何数字必须挂 `evidence_id`
- **结构化对抗**：多空双方独立建论（claim + 证据 + 可证伪条件），辩论限定六类攻击且必须点名让步
- **先盲判后裁决**：裁判先只看证据出结论，再读辩论，`revision_reason` 留档用于校准
- **有界质检与降级**：机械校验 + LLM 校验，定向回退最多 2 次；失败显式标注，不伪造结论
- **闭环**：决策落 SQLite，到期结算收益/超额并生成反思，下次同类研究注入对应分析师
- **可回测**：PIT 数据源、T+1 成交、历史成分股、置信度校准（Brier/分桶命中率/辩论增量）

## 技术栈

- 后端：`Python`、`Flask`、`pydantic`
- Agent：自研 ReAct 循环（OpenAI 兼容 function calling）
- 前端：`React`、`Vite`
- 数据：`Tushare`（A股/基金/宏观，单一数据源）、`Alpaca`（美股日线）、`ddgs`（网页检索）
- 存储：`SQLite`（决策记录 / 回测结果 / LLM 缓存），无向量库依赖

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
    ├── agents/                 # ★ 编排与质量层
    │   ├── pipeline.py         # 六层流水线（预算/超时/并行/回退）
    │   ├── orchestrator.py     # 对外入口（Pipeline 薄封装）
    │   ├── ledger.py           # 证据台账
    │   ├── debate.py           # 结构化辩论
    │   ├── judge.py            # 盲判 + 裁决
    │   ├── verifier.py         # 机械 + LLM 质检
    │   ├── base.py / loop.py   # ReAct 基类与循环
    │   ├── state.py            # 状态模型
    │   └── events.py           # 事件发射
    ├── analysts/               # 四路分析师 + 注册表
    │   └── registry.py         # 扩展唯一入口（AnalystSpec）
    ├── memory/                 # 跨任务闭环
    │   ├── decision_store.py   # 决策落库（SQLite）
    │   ├── settlement.py       # 到期结算
    │   └── reflection.py       # 反思检索与回灌
    ├── backtest/               # 回测与校准
    │   ├── clock.py            # T+1 / 停牌涨跌停 / 持有期
    │   ├── datasource.py       # PIT 数据源
    │   ├── runner.py           # 决策点遍历 / 幂等 / 断点续跑
    │   └── metrics.py          # Brier / 校准 / 辩论增量
    ├── asset/                  # 资产主数据与解析
    ├── tools/                  # 工具层（19 个工具）
    ├── data/                   # 数据源（行情/财务/公告/宏观/新闻）
    ├── tests/                  # 纯逻辑单测 + 离线端到端冒烟
    ├── services/               # 事件总线等
    ├── utils/                  # LLM 客户端、PIT、联网搜索
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

# Tushare 数据源（必需，行情/财务/宏观/基金均走 tushare）
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
| `orchestrator_thinking` / `orchestrator_decided` | 研究主管思考与派发计划 |
| `plan_ready` | 结构化研究计划（含必选/加派分析师、focus_questions） |
| `phase_started` / `phase_completed` | L0-L6 阶段进度与耗时 |
| `agent_started` / `agent_thinking` / `agent_completed` | 分析师生命周期 |
| `tool_started` / `tool_completed` / `tool_failed` | 工具调用进度 |
| `evidence_added` | 新增证据（实时写入台账） |
| `thesis_submitted` / `debate_turn` | 多空论点与辩论动作 |
| `verdict_ready` / `verification_failed` | 裁决与质检结果 |
| `decision_recorded` | 决策落库（用于历史与结算） |
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
- `components/agents/PhaseProgress.jsx` — L0-L6 阶段进度
- `components/agents/EvidencePanel.jsx` — 证据台账（可按类别折叠）
- `components/agents/DebateTimeline.jsx` — 多空结构化辩论时间线
- `components/agents/VerdictPanel.jsx` — 裁决（盲判 vs 终判、分歧矩阵、观察项、质检）
- `components/agents/SummaryCard.jsx` — 研报正文（多空论据、风险矩阵、缺口）
- `components/views/HistoryView.jsx` + `components/agents/TurnDetail.jsx` — 历史会话与详情
- `hooks/useAgentStream.js` — SSE 事件流状态管理
- `services/apiClient.js` — API 封装

## 证据台账与决策闭环

系统不依赖向量检索。事实统一写入 `src/agents/ledger.py` 的 `EvidenceLedger`：

- 工具执行成功后由代码自动登记（不依赖模型输出 `[FINDINGS]`）
- 每条证据有全局 ID（`EV-0001`），带类别、数值、口径、来源工具、数据时间
- 同资产/同类别/同事实自动去重，保留最新观测
- 回测时按 `as_of` 校验：晚于决策时点的证据标记冲突并降权

结论侧对应 `src/memory/`：

1. `decision_store.py`：裁决、论点、证据 ID 落 SQLite（`src/data/decisions.sqlite`）
2. `settlement.py`：决策到期后拉取 T+1 开盘 → 持有期收盘的收益与基准 alpha
3. `reflection.py`：生成结构化反思，下次同类研究注入对应分析师 prompt

## 回测与校准

回测定位是**系统校准器**，不是收益证明：

- `src/backtest/clock.py`：T+1 成交、停牌/涨跌停顺延、按交易日计算持有期
- `src/backtest/datasource.py`：PIT 上下文；新闻/公告/网页工具在回测中直接禁用
- `src/backtest/runner.py`：决策点遍历、幂等落库、断点续跑、多次运行取多数方向
- `src/backtest/metrics.py`：Brier、置信度分桶命中率、有/无辩论增量、按 stance 分组
- `src/backtest/universe.py`：历史成分股，取不到时标记 `universe_bias`

```python
from backtest import iter_grid, run_backtest
from backtest.report import render

dates = iter_grid("2026-01-01", "2026-06-30", every_n_days=7)
result = run_backtest(["600519"], dates, repeats=1, horizon="medium")
print(render(result))
```

### 轻量量化回测

和上面的“投研决策回测”不同，这套不调用 LLM，直接对价格/策略做日线回测（秒级）：

```bash
# 双均线
PYTHONPATH=src .venv/bin/python -m quant --assets 600519 \
  --start 2020-01-01 --end 2026-06-30 --strategy ma_cross \
  --params '{"fast":20,"slow":60}'

# 动量 + 多资产等权
PYTHONPATH=src .venv/bin/python -m quant --assets 600519,000858 \
  --strategy momentum --params '{"lookback":20}' --json
```

- 内置策略：`buy_hold` / `ma_cross` / `momentum`；库 API 支持自定义 `df -> 0/1` 信号
- 规则：T 日收盘信号 → T+1 开盘成交；100 股一手；手续费万 2.5（最低 5 元）+ 滑点 0.1%
- 指标：总收益、年化、最大回撤、夏普、胜率、盈亏比、换手、基准超额
- v1 不做：分钟级、做空、杠杆、组合优化、PIT 成分、企业行动

### 命令行 pilot

```bash
# 链路验证（不调用 LLM，30 个决策点，秒级）
PYTHONPATH=src .venv/bin/python -m backtest.pilot

# 真实 pilot（每个决策点约 5 分钟）
PYTHONPATH=src .venv/bin/python -m backtest.pilot --real --assets 600519 \
  --start 2026-06-01 --end 2026-06-01 --limit 1

# 用历史成分股作为资产池
PYTHONPATH=src .venv/bin/python -m backtest.pilot --real --index 000300.SH \
  --universe-limit 3 --limit 2
```

结果写入 `src/data/backtest.sqlite`；同一 `run_id` 重跑会断点续跑。
真实模式下同一 (资产, 时点) 命中结果缓存，复跑约 2 秒且结论一致。

### 运行观测

每次提问都会落一份可查询的运行记录，排查问题不需要翻 stdout：

- 运行库：`src/data/observability.sqlite`（任务 / 事件 / LLM 调用 / 工具调用四张表）
- 结构化日志：`logs/app.jsonl`（50MB 轮转，保留 5 份，自动带 `task_id`）
- 查询接口：
  ```bash
  curl "http://localhost:5002/api/ops/tasks?limit=20&status=failed"
  curl "http://localhost:5002/api/ops/tasks/<task_id>"
  curl "http://localhost:5002/api/ops/stats?window=24h"
  curl "http://localhost:5002/api/ops/health"
  ```
- 开关：`OBS_ENABLED=0` 关闭；`OPS_TOKEN` 保护接口；
  `OBS_RUN_RETENTION_DAYS` / `OBS_EVENT_RETENTION_DAYS` 控制保留期

## 测试

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests -q
```

覆盖四个纯逻辑模块（ledger / verifier / settlement / backtest.clock）+ 指标函数 + 离线端到端冒烟（FakeLLM，不联网）。

## 免责声明

本项目仅用于学习与研究，不构成任何投资建议。投资有风险，决策需谨慎。
