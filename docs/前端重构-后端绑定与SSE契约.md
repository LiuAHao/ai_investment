# 前端重构交接文档：后端绑定与关键技术要点

> 用途：前端整体重做时只参考本文件，不参考旧前端实现。
> 旧前端目录 `src/web` 已删除；后端代码未做任何修改。
> 新前端可以使用任意框架，但必须满足本文的接口契约、事件处理与状态机要求。

---

## 1. 运行拓扑

- 后端：Flask，默认端口 `5001`（`FLASK_PORT` / `PORT` 可覆盖）。
- 前端：独立 SPA，开发期独立端口（旧实现用 Vite，默认 5173）。
- 跨域：后端已对所有来源开启 CORS（`flask_cors.CORS(app)`），前后端可不同源。
- 认证：无登录、无配额、无鉴权头。
- 后端入口：`src/api/main.py`，启动命令：

```bash
.venv/bin/python run.py --backend
# 或
PYTHONPATH=src .venv/bin/python src/api/main.py
```

- 后端健康检查：`GET /api/health` → `{"status":"ok","version":"2.0.0"}`。
- `.env` 从项目根目录加载（由后端读取），不通过前端注入。

### 1.1 前端位置与启动脚本的关系

`run.py --frontend` 硬编码了前端目录 `src/web`，并依赖 Vite 7 要求的 Node 版本
（`^20.19.0` 或 `>=22.12.0`）。旧 `src/web` 删除后：

- `python run.py --frontend` 会直接报“前端目录不存在”。
- `python run.py`（无参数）默认也是启动前端，同样会失败。
- 新前端如果仍放在 `src/web` 并使用 `npm run dev`，启动脚本无需改动；
  如果换目录或换构建工具，需要同步调整 `run.py` 的 `start_frontend()`。
- 旧前端通过 `VITE_API_BASE_URL` / `VITE_API_BASE` 指定后端地址，默认
  `http://localhost:5001`。新前端可以沿用，也可以自行定义，但必须支持“后端独立域名/端口”。

---

## 2. HTTP API 契约

### 2.1 提交研究任务

`POST /api/agent/query`

请求：

```json
{
  "query": "分析一下贵州茅台",
  "risk_preference": "稳健型",
  "session_id": "mem_xxxxxxxxxxxx",
  "context": ""
}
```

- `query`：必填，空字符串返回 `400 {"error":"query 不能为空"}`。
- `risk_preference`：可选，字符串（旧实现传“稳健型/平衡型/进取型”，后端不校验枚举）。
- `session_id`：可选；为空时后端生成 `mem_<12 hex>`。
- `context`：可选；为空时后端会自动从同一 `session_id` 的上一轮取结论摘要作为上下文。

响应：`202`

```json
{ "task_id": "task_xxxxxxxxxxxx", "session_id": "mem_xxxxxxxxxxxx" }
```

后续必须使用响应里的 `task_id` 订阅 SSE / 轮询；追问时复用响应里的 `session_id`。

### 2.2 查询任务状态（SSE 断流兜底）

`GET /api/agent/tasks/{task_id}`

响应：

```json
{
  "status": "processing | completed | failed",
  "result": { "...任务完整结果，仅 completed 时存在..." },
  "error": "错误文本，仅 failed 时存在"
}
```

- 任务不存在或已被淘汰：`404 {"error":"任务不存在"}`。
- 任务注册表是**进程内内存**，上限 200 个；后端重启后旧 `task_id` 会 404，
  但历史会话仍然存在（见第 6 节）。

### 2.3 历史会话

`GET /api/history`

```json
{
  "sessions": [
    {
      "session_id": "mem_xxx",
      "created_at": "ISO 时间",
      "updated_at": "ISO 时间",
      "title": "首轮问题前 30 字",
      "turn_count": 1
    }
  ]
}
```

- 按 `updated_at` 倒序，最多 100 条。

`GET /api/history/{session_id}`

```json
{
  "session_id": "mem_xxx",
  "turns": [ { "...见 6.3..." } ]
}
```

- 会话不存在：`404 {"error":"会话不存在"}`。
- 历史是持久化的，进程重启不丢（写入 `src/data/sessions.json`，原子替换）。

---

## 3. SSE 实时事件流

### 3.1 连接

`GET /api/agent/events/{task_id}`，`Content-Type: text/event-stream`。

- 必须按**具名事件**监听（`source.addEventListener(type, ...)`），不能只用 `onmessage`。
- 服务端每 30 秒发一次 `heartbeat` 保活。
- 任务结束（`task_completed` / `task_failed`）后服务端会主动结束流。

### 3.2 帧格式（两种包装，必须都兼容）

实时事件（来自事件总线）：

```
event: agent_thinking
data: {"type":"agent_thinking","task_id":"task_xxx","timestamp":1720000000.123,"data":{"agent":"MarketAgent","thought":"..."}}
```

`connected` / `heartbeat` / 快照补发（由 API 层直接构造）：

```
event: task_completed
data: {"type":"task_completed","data":{"result":{...}}}
```

统一解析方式：

```js
const evt = JSON.parse(message.data)   // { type, task_id?, timestamp?, data }
const payload = evt.data               // 业务字段永远在 data 里
```

差异：实时帧多 `task_id`、`timestamp`；快照帧没有。业务字段位置一致。

### 3.3 事件表

| 事件 | data 字段 | 说明 |
|---|---|---|
| `connected` | `{task_id}` | 连接建立 |
| `heartbeat` | `{timestamp}` | 30 秒心跳，忽略即可 |
| `task_started` | `{task_id, session_id}` | 后台任务开始 |
| `orchestrator_thinking` | `{thought: string}` | 编排 Agent 思考 |
| `orchestrator_decided` | `{plan: string[], reason: string}` | 派发计划；`plan` 为调研 Agent 名数组 |
| `agent_started` | `{agent, task, goal, round}` | Agent 开始；`round` 为 1 或 2 |
| `agent_thinking` | `{agent, thought: string}` | Agent 思考 |
| `tool_started` | `{agent, tool, params: object}` | 工具开始 |
| `tool_completed` | `{agent, tool, status, latency, summary}` | 工具完成；`latency` 单位 ms |
| `tool_failed` | `{agent, tool, error}` | 工具失败 |
| `agent_failed` | `{agent, error}` | Agent 失败 |
| `agent_degraded` | `{agent, reason, permanent}` | 原生 function calling 不可用，降级为文本工具协议 |
| `agent_completed` | `{agent, result_summary, evidence_refs, round}` | Agent 单轮完成，`result_summary` 为结论文本 |
| `final_answer` | `{answer: object}` | 最终结构化答案（见 6.2） |
| `task_completed` | `{result: object}` | 任务完整结果（见 6.1） |
| `task_failed` | `{error: string}` | 任务终止 |
| `task_marker` | `{label, ts}` | 内部时间标记，前端可忽略 |

关键点：

- **`agent_completed` 只带结论摘要，不带完整工具明细**；完整结果来自
  `final_answer`、`task_completed` 或轮询接口。
- `orchestrator_decided.plan` 与 `task_completed.result.plan` 的形态不同：
  - 事件里是 `string[]`。
  - 完整结果里是 `{agents: string[], reason: string}`。
  - `result.orchestrator.plan` 又是 `string[]`。
- `final_answer` 与 `task_completed` 可能都到达，终态处理必须幂等。

### 3.4 重连与快照

- 浏览器 `EventSource` 会自动重连；断线重连后，服务端会**回放事件缓冲**
  （每任务最近 200 条），因此会收到重复事件，必须去重。
- 如果任务在连接前已经完成，服务端先发 `connected`，再发一条
  `task_completed`（内含完整 `result`）或 `task_failed`，然后关闭。
- 任务运行中：先回放缓冲，再持续推送，直到终态。

### 3.5 去重建议

- `orchestrator_thinking` / `agent_thinking`：与同 Agent 最后一条相同则丢弃。
- `tool_started`：若已有同 `agent + tool + JSON.stringify(params)` 且状态为 running，则丢弃。
- `tool_completed` / `tool_failed`：优先匹配该 Agent 最后一条 running 工具。
- 终态：用 `finished` 标记，`final_answer` 与 `task_completed` 只处理一次。
- 若未来后端增加 `event_id`，优先按 `event_id` 去重。

---

## 4. 前端状态机

### 4.1 任务阶段

```
idle
  └─ POST /query 成功 → orchestrating
orchestrating
  └─ orchestrator_decided → researching
researching
  └─ agent_started(agent=SummaryAgent) → summarizing
summarizing
  └─ final_answer / task_completed → done
任意阶段
  └─ task_failed / 请求失败 / 轮询失败 → failed
```

- 进入 `researching` 的时机是收到派发计划，不是提交成功。
- `SummaryAgent` 不在调研 `plan` 里，它是独立的总结阶段。
- `done` 后仍可基于同一 `session_id` 继续追问；新会话必须清空 `session_id`。

### 4.2 Agent 视图状态（由事件推导，后端不下发）

| 状态 | 触发 |
|---|---|
| `waiting` | 收到 `orchestrator_decided`，按 `plan` 预创建卡片 |
| `thinking` | `agent_started` / `agent_thinking` / 工具完成或失败后 |
| `tooling` | `tool_started` |
| `round1_done` | 调研 Agent 的 `agent_completed(round=1)` |
| `done` | 调研 Agent 的 `agent_completed(round=2)`；SummaryAgent 完成；或进入终态 |
| `failed` | `agent_failed` |
| `degraded` | 独立布尔标记，可与上述状态并存 |

- 只渲染 `plan` 中实际启动的调研 Agent，不要虚构未启动的卡片。
- 如果第二轮没有发生，进入 `done` 时要把所有 `round1_done` 的 Agent 置为 `done`。
- 进入 `done` 时，仍在 running/thinking 的 Agent 也应统一收敛为终态，避免界面卡住。

### 4.3 页面切换与状态缓存（新前端需要重新实现）

- 任务状态、当前 `task_id`、`session_id`、当前问题、输入草稿建议提升到应用级存储，
  不要绑定在某个页面组件内。
- 切换首页/研究台/历史页时，不能重置 SSE 连接或任务状态；否则用户返回后只能去历史里找。
- 只有“开始新对话”才清空 `session_id` 与任务状态。
- 如果希望刷新浏览器后仍能恢复：需要持久化 `{task_id, session_id, query, phase}`，
  并在启动时调用任务状态接口补全；后端任务注册表是内存态，后端重启后只能回退到历史会话。

---

## 5. SSE 断流兜底（轮询）

收到 `EventSource.onerror` 后启动轮询，不要立即判定失败：

- `GET /api/agent/tasks/{task_id}`
- 建议退避：初始 1200ms，每次 ×1.4，上限 3000ms，总时长上限 15 分钟。
- `status=completed`：用 `result` 补全 UI，关闭 SSE，标记“结果来自轮询”。
- `status=failed`：进入 failed。
- `status=processing`：继续轮询。
- `completed` 但 `result.answer` 缺失：视为失败（后端异常数据）。
- 轮询与 SSE 可能同时到达终态：用 `finished` 标记保证只应用一次。
- 网络错误导致轮询请求本身失败时，应结束并提示“无法获取任务状态”，而不是无限重试。

---

## 6. 数据结构

### 6.1 任务完整结果（`task_completed.result` / 轮询 `result`）

```json
{
  "query": "分析一下贵州茅台",
  "assets": [ { "asset_id": "cn_stock:600519", "asset_type": "cn_stock", "symbol": "600519", "name": "贵州茅台" } ],
  "plan": {
    "agents": ["MarketAgent", "NewsAgent", "KnowledgeAgent"],
    "reason": "具体资产问题：行情 + 新闻 + 知识三路调研"
  },
  "agent_results": [
    {
      "agent_name": "MarketAgent",
      "conclusion": "研究结论文本（可能含 Markdown）",
      "round1_conclusion": null,
      "evidence_refs": ["ev_xxx"],
      "tool_calls": [
        {
          "tool_name": "stock_data",
          "status": "success",
          "asset_id": "cn_stock:600519",
          "data": {},
          "source": "akshare",
          "source_url": null,
          "data_timestamp": "ISO 或 null",
          "fetched_at": "ISO",
          "freshness_seconds": 120,
          "confidence": 1.0,
          "error": null,
          "latency_ms": 182,
          "step_id": null
        }
      ],
      "thinking_log": ["..."],
      "error": null,
      "degraded": false
    }
  ],
  "answer": { "...见 6.2..." },
  "orchestrator": {
    "thoughts": ["..."],
    "plan": ["MarketAgent", "NewsAgent", "KnowledgeAgent"],
    "reason": "..."
  }
}
```

### 6.2 最终答案 `answer`

```json
{
  "answer_id": "uuid",
  "session_id": "mem_xxx",
  "query": "分析一下贵州茅台",
  "assets": [ { "asset_id": "...", "asset_type": "cn_stock", "symbol": "600519", "name": "贵州茅台" } ],
  "summary": "总体判断（Markdown）",
  "key_points": ["关键判断 1", "关键判断 2"],
  "evidence_refs": ["ev_xxx"],
  "risks": ["字符串风险（旧格式）"],
  "structured_risks": [
    {
      "type": "政策 | 财务 | 行业 | 市场 | 技术 | 流动性",
      "desc": "风险描述",
      "probability": "high | medium | low",
      "impact": "high | medium | low",
      "priced_in": true
    }
  ],
  "confidence": 0.72,
  "reasoning": "推理过程（Markdown）",
  "bull_cases": [ { "point": "看多论据", "strength": "high | medium | low", "source": "来源" } ],
  "bear_cases": [ { "point": "看空论据", "strength": "high | medium | low", "source": "来源" } ],
  "information_gaps": ["信息缺口"],
  "time_frame": "时间框架（Markdown）",
  "compliance_disclaimer": "合规声明",
  "created_at": "ISO 时间"
}
```

注意：

- `confidence` 是 `0~1` 的小数，不是百分数。
- `bull_cases` / `bear_cases` 的字段名是 **`point`**（不是 `case` / `desc`）。
- `priced_in` 可能是 `true` / `false` / `null`。
- `summary`、`reasoning`、`time_frame`、各 Agent 的 `conclusion`、`thinking_log`
  都可能包含 Markdown（标题、列表、粗体、链接等）。
- `key_points`、`risks`、`information_gaps` 是纯文本字符串数组。
- `answer` 在异常情况下仍可能存在，但内容可能是错误文本（后端 SummaryAgent 兜底）；
  新前端应正常渲染，不要崩溃。

### 6.3 历史 turn

```json
{
  "query": "分析一下贵州茅台",
  "timestamp": "2026-10-22T11:30:45.756620",
  "answer": { "...同 6.2..." },
  "plan": ["MarketAgent", "NewsAgent", "KnowledgeAgent"],
  "orchestrator": {
    "thoughts": ["..."],
    "plan": ["MarketAgent", "NewsAgent", "KnowledgeAgent"],
    "reason": "..."
  },
  "agent_results": [
    {
      "agent_name": "MarketAgent",
      "conclusion": "...",
      "thinking_log": ["..."],
      "evidence_refs": [],
      "tool_calls": [
        {
          "tool_name": "stock_data",
          "status": "success",
          "latency_ms": 182,
          "error": null,
          "summary": "245 条日线"
        }
      ],
      "error": null,
      "degraded": false
    }
  ]
}
```

历史数据与实时结果的区别：

- 历史的 `tool_calls` **不含原始 `data`**，只有 `tool_name/status/latency_ms/error/summary`。
- 历史不保存 SSE 事件流，只保存最终结论与思考日志。
- `plan` 在历史 turn 里已经展开为数组；`orchestrator.plan` 也是数组。

---

## 7. Agent 与会话语义

### 7.1 Agent 名单

- 调研 Agent：`MarketAgent`、`NewsAgent`、`KnowledgeAgent`
- 总结 Agent：`SummaryAgent`

`plan` 只包含调研 Agent；`SummaryAgent` 始终在调研结束后单独执行。

### 7.2 轮次

- 第一轮：所有计划内调研 Agent 并行。
- 第二轮：条件触发（后端 `AGENT_SUPPLEMENT_MODE=conditional|always|off`）。
  第二轮只对第一轮已有共享发现的 Agent 做补充调研。
- `agent_completed.round` 标识轮次；第一轮结论可能被第二轮覆盖。
- 第二轮未发生时，任务结束时把第一轮的 `round1_done` 收敛为 `done`。

### 7.3 会话与追问

- 复用 `session_id` 提问时，后端会自动读取该会话上一轮的结论摘要与资产，
  作为本轮上下文；新前端不应自己拼接历史，只需传 `session_id`。
- 新会话：不要传 `session_id`，或传空字符串，后端会生成新 ID。
- 会话历史持久化在 `src/data/sessions.json`：
  - 最多 200 个会话；
  - 单会话最多 200 轮；
  - 文件最大 20MB，超限淘汰最旧会话；
  - 写入使用临时文件 + 原子替换。
- `context` 字段一般留空；只有需要手工注入额外上下文时才传。

---

## 8. 失败与降级

| 情况 | 表现 | 新前端处理 |
|---|---|---|
| 原生 function calling 不可用 | `agent_degraded` | 标记“已降级”，Agent 仍会继续运行 |
| 单个调研 Agent 异常 | `agent_failed` + 该 Agent `error` | 卡片显示失败，其他 Agent 继续 |
| 工具失败 | `tool_failed` | 标记该工具失败，不终止整个任务 |
| 总结阶段异常 | 仍可能返回 `answer.summary = "综合分析过程中发生错误: ..."` | 正常渲染，并标注异常 |
| 任务异常 | `task_failed {error}` | 进入 failed，展示错误；可重新提交 |
| 提交接口非 2xx | `{"error": "..."}` | 展示后端错误文本 |
| 任务状态 404 | 后端重启或任务被淘汰 | 提示任务已失效，引导去历史 |

不要假设“所有 Agent 都成功”才会出结果；后端会在部分失败时继续总结。

---

## 9. 限制与生命周期

| 资源 | 上限/行为 |
|---|---|
| 任务注册表 `_tasks` | 进程内，最多 200，优先淘汰已结束任务 |
| SSE 快照 `_task_snapshots` | 进程内，最多 200 |
| 事件缓冲 | 每任务最近 200 条，任务落地快照后清理 |
| 会话 | 最多 200 个 |
| 单会话轮次 | 最多 200 |
| 会话文件 | 最大 20MB，超限淘汰最旧 |
| SSE 心跳 | 30 秒 |
| 任务执行 | 后台线程池，最大 4 并发 |
| 任务状态 | 后端重启丢失；历史会话保留 |

---

## 10. 已知坑（实现前必读）

1. **SSE 有两种帧包装**：业务字段永远在 `evt.data`，但实时帧额外有 `task_id/timestamp`。
2. **必须监听具名事件**：`EventSource.onmessage` 收不到这些事件。
3. **重连会重放缓冲**：思考、工具开始事件会重复，必须去重。
4. **`agent_completed` 不是完整结果**：完整工具明细只在 `final_answer` / `task_completed` / 轮询里。
5. **`plan` 形态不一致**：事件里是数组，`result.plan` 是 `{agents, reason}`，`result.orchestrator.plan` 是数组。
6. **终态可能重复**：`final_answer` 与 `task_completed` 都可能到达，处理要幂等。
7. **不要等所有 Agent 成功**：部分失败仍会出总结；失败态也要能渲染。
8. **置信度是 0~1**，不是 0~100。
9. **多空论据字段是 `point`**，不是 `title` / `desc`。
10. **Markdown 与纯文本混用**：结论类字段可能含 Markdown，列表类字段是纯文本。
11. **历史没有原始工具数据**：只有摘要，不能从历史重建完整工具流。
12. **后端重启会丢 task_id**：任务状态查询 404，但历史会话仍可读。
13. **CORS 全开**：前后端可不同源，但新前端需要正确配置 API base。
14. **`run.py --frontend` 依赖 `src/web`**：换目录/换框架要同步改启动脚本。
15. **SSE 连接与组件生命周期解耦**：页面切换不要关闭连接；只有新任务/终态/卸载才关闭。
16. **长任务**：研究可能持续数分钟，浏览器标签页休眠会断流；必须保留轮询兜底。

---

## 11. 新前端最小验收清单

- [ ] 提交问题 → 202 → 立即建立 SSE，进入编排态。
- [ ] 收到 `orchestrator_decided` 后只渲染 plan 内 Agent。
- [ ] 思考流、工具流、轮次状态随事件更新。
- [ ] `SummaryAgent` 开始 → 进入总结态。
- [ ] `final_answer` / `task_completed` → 渲染完整研报，终态处理幂等。
- [ ] 部分 Agent 失败 / 降级 / 工具失败时界面可读、不崩。
- [ ] SSE 断流后轮询兜底，能恢复最终结果。
- [ ] 同一 session 追问可用；新会话会清空 session。
- [ ] 历史列表与历史详情可读，字段缺失时容错。
- [ ] 页面切换（首页/研究台/历史）不丢当前任务状态与输入草稿。
- [ ] 刷新浏览器后的行为明确（可选持久化 task_id 恢复）。
- [ ] 移动端与桌面端均可完成完整流程。

---

## 12. 后端边界（重构时不要改）

本次只删除前端。以下后端契约视为稳定输入：

- 路由路径与方法。
- SSE 事件名与 `data` 字段。
- `InvestmentAnswer` / `AgentResult` / 任务结果结构。
- 会话复用与历史持久化行为。
- Agent 名单与轮次语义。
- 环境变量与启动方式。

如果新前端需要新增字段或接口，应作为后端增量变更单独讨论，不要在前端侧猜测字段。
