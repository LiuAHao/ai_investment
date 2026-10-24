# 多 Agent 链路与逻辑问题审查（复核版）

> 审查对象：`src/agents`、`src/api`、`src/tools`、`src/rag`、`src/web/src`
> 审查日期：2026-10-22（第二轮复核）
> 说明：本文只记录问题与验证结论，不包含业务逻辑修改。"✅" 表示已用代码或脚本实测确认，"⚠️" 表示原判断需要修正，"❌" 表示原判断撤回。

## 一、改动边界

业务逻辑保持 origin/main 重构版原样。此前只改过管道层：`api/events.py`（快照字段结构）、`api/routes/agent.py`（任务表上限）、`services/event_bus.py`（缓冲释放）、`utils/llm_common.py`（删除未使用的 `AgentConfig`）。

本轮复核另外修复了一处**由前述管道改动引入的竞态**（见第七节），未触碰决策、提示词与解析逻辑。

## 二、当前执行链路

```
POST /api/agent/query
  └─ 线程池（max_workers=4）→ OrchestratorAgent.run_query
       ├─ 1. 资产解析：asset_resolve（纯规则，无网络）
       ├─ 2. 派发计划：LLM（无 JSON 模式）→ 失败走关键词规则
       ├─ 3. 第一轮：Market/News/Knowledge 并行 ReAct（每任务 3 线程）
       ├─ 4. 汇聚 shared_pool.get_all()
       ├─ 5. 第二轮：同一批 Agent 带 findings 再跑一遍（无条件）
       ├─ 6. SummaryAgent 综合 → JSON 解析 → confidence
       ├─ 7. L3 沉淀：sediment_research（同步，含 LLM 蒸馏）
       └─ 8. 写会话 → emit task_completed → 保存快照
```

## 三、复核结论总览

| # | 问题 | 复核结论 |
| --- | --- | --- |
| 1 | 无共享发现仍执行第二轮 | ✅ 属实（脚本实测） |
| 2 | 第二轮结果覆盖第一轮 | ✅ 属实（脚本实测） |
| 3 | LLM 异常后永久禁用工具 | ⚠️ 部分修正：降级到文本协议后**仍能**调用工具，但不再尝试原生 function calling，且用户无感知 |
| 4 | 置信度虚高 | ✅ 属实（实测零数据默认 0.8） |
| 5 | 强制收敛指令与 JSON 格式冲突 | ✅ 属实（静态） |
| 6 | 多轮上下文断裂 | ✅ 属实（静态） |
| 7 | 资产解析只作为提示词文本 | ✅ 属实（静态） |
| 8 | 派发规则首命中 | ✅ 属实（实测，前次已修正口径） |
| 9 | 共享发现依赖模型自觉输出 | ✅ 属实（静态） |
| 10 | 实时视图与最终报告不一致 | ⚠️ 部分修正：只在第二轮进行中短暂不一致，`round1Summary` 是未被渲染的死状态 |
| 11 | L3 沉淀同步 + 门槛偏松 | ✅ 属实（配置门槛实测） |
| 12 | 并发与超时无护栏 | ⚠️ 部分修正：OpenAI SDK 自带 600s 超时与 2 次重试；真正缺护栏的是**工具层 timeout 未生效** |
| 13 | 工具结果硬截断 | ✅ 属实（实测 3011 字符、尾部 JSON 非法） |
| 14 | 进展检测只看成功工具数 | ✅ 属实，并补充：文本协议路径完全没有进展检测 |
| 15 | 解析兜底脆弱 | ❌ 大部分撤回：尾随文字、字符串内括号、截断 JSON 都能解析；仅"正式答案前先出现另一个 JSON 对象"时会失败 |

## 四、确定性 bug（含复核依据）

### 1. 无共享发现仍执行第二轮

`src/agents/orchestrator.py:297-304`：日志写"跳过补充调研"，随后无条件 `_run_parallel(_second_round)`。

实测（注入 stub Agent）：第一轮 `run` 各调用 1 次后，`supplement` 被调用 2 次，`full_findings` 长度为 0。成本与第一轮相同。

### 2. 第二轮结果覆盖第一轮

实测：stub 第一轮返回 `R1-Conv`、第二轮返回 `R2-Conv`，`_run_research_agents` 返回值只含 `R2-Conv`。第一轮结论、工具数据、对话上下文全部丢弃，第二轮退化时无回退。

### 3. LLM 异常后永久降级（口径修正）

`src/agents/loop.py:276-282` 捕获任意异常后置 `_tools_supported = False`，此后循环不再尝试原生 function calling。

修正点：文本协议路径仍会解析 `TOOL: name {json}` 并执行工具。实测：首次调用抛异常后，第二轮输出 `TOOL: fake_tool {...}`，工具被正常执行，最终返回 `FINAL: 完成`。

真实风险：能力从"模型自主 function calling"退化为"依赖模型手写 TOOL: 格式"，成功率下降；同时文本协议路径**没有** `_check_progress` 调用，不会提前收敛，只能撞迭代上限；整个过程没有告警。

### 4. 置信度虚高

`src/agents/summary_agent.py:305-345`。实测：

| 场景 | 结果 |
| --- | --- |
| 无模型自评、无工具调用、无论据 | 0.80 |
| `degraded=True` | 0.40 |
| SummaryAgent 自己工具全失败、无论据 | 0.70 |

调研 Agent 的失败不参与计算（`degraded` 只在 SummaryAgent 自身异常时置位），报告完整性没有进入评分。

### 5. 强制收敛指令与输出格式冲突

`loop.py:210-216` 要求"以 FINAL: 开头"，SummaryAgent 以 `keep_full_json=True` 期望完整 JSON。收敛路径可能丢章节；触发原因统一写成"到达迭代上限"，实际可能是连续无进展。

## 五、设计隐患

### 6-9（与上一版一致，复核仍成立）

- **多轮上下文断裂**：`useAgentStream.js:331` 只传 `riskPreference`；`App.jsx` 无追问入口；`orchestrator._resolve_assets` 的 context 继承是 `pass`。
- **资产只做文本提示**：`base._build_user_message` 拼接名称，工具参数不携带资产，Agent 需重新猜代码。
- **规则首命中**：`orchestrator.py:46-66`，`估值` 同时在第 2/3 组，`分析` 跨组重叠；纯知识问题（"市盈率是什么"）走 Knowledge，含"分析"的知识问题会派三路。仅在 LLM 决策失败时生效。
- **共享发现靠自觉**：`loop._publish_findings` 正则匹配 `[FINDINGS]`，无结构化字段，无关联证据。

### 10. 展示一致性（口径修正）

第一轮结束时 `agent_completed` 写入 `summary`，UI 立刻展示；第二轮开始后 `summary` 保留、`round1Summary` 记录旧值；第二轮完成后 `summary` 被覆盖。因此不一致只在第二轮进行中存在。

`round1Summary` 在 `useAgentStream.js` 中写入但 `AgentCard` 从未读取，属于死状态。

### 11. L3 沉淀门槛偏松（复核补充数据）

`src/rag/config/rag_config.json` 的 `sediment` 配置：`min_summary_chars=50`、`min_key_points=1`、`distill_enabled=true`。

`_quality_gate` 只在"无证据且结论短于 100 字"时才拒绝；而 `has_evidence` 来自 `evidence_refs`，后者实际是工具名/`asset_id`（`loop._collect_evidence_refs`），只要调用过工具就为真。绝大多数报告都会通过门槛并进入知识库。

沉淀在返回结果前同步执行（`orchestrator.py:121`），包含一次 LLM 蒸馏与向量库写入，直接增加任务尾延迟。

### 12. 并发与超时（口径修正）

- 任务池 4 线程；每任务每轮 3 线程、共两轮。
- OpenAI SDK（2.36.0）默认 `timeout=600s`、`max_retries=2`，最坏情况单次调用可占住线程约 30 分钟，前端轮询 3 分钟就先放弃了。
- 工具层 `BaseTool.timeout` / `ToolSpec.timeout_seconds` 只写进 schema，`BaseTool.run()` 里没有任何超时控制，配置形同虚设。

### 13. 工具结果截断（复核确认形态）

`MAX_TOOL_RESULT_CHARS=3000`，实测超长结果被截成 3011 字符，尾部是 `……(结果过长已截断)`，整体已不是合法 JSON。模型读到的是破碎结构，可能导致误读，但不是客户端解析错误。

### 14. 进展检测

`_check_progress` 只在"成功工具数未增加"时累加，重复成功调用永远算进展。补充：该检测只在 function calling 路径调用，文本协议路径没有任何进展检测。

### 15. 解析兜底（撤回大部分结论）

实测 `_extract_answer_json`：

| 输入 | 结果 |
| --- | --- |
| `{...} 以上。`（尾随文字） | 正常解析 |
| summary 内含 `}` 与 `{` | 正常解析 |
| JSON 被截断（缺右括号） | 修复后正常解析 |
| 答案前先出现另一个 JSON 对象 | 解析失败，回退为整段文本 |

`_parse_decision` 的行为确认：JSON 可解析但缺 `decision` 字段时返回 `unknown`，内容被当思考继续循环，消耗迭代。

## 六、本轮新增发现

### 16. 会话文件并发写入失败（实测）

`SessionMemory._save` 在锁外执行，所有写入共用同一个 `.tmp` 文件名。8 线程 × 20 轮压测：内存 160 轮、文件 160 轮，数据未丢，但产生 **100+ 次** `FileNotFoundError` 日志（`os.replace` 时临时文件已被其他线程移走）。

后果：并发任务结束时最后一次落盘可能失败（内存有、磁盘少一轮），并刷大量告警日志；下一次成功写入会补齐，但服务重启会丢最后一轮。

### 17. 会话文件未被 gitignore

`SESSIONS_FILE = src/data/sessions.json`，`.gitignore` 未覆盖该路径（`git check-ignore` 无命中）。首次产生会话后，用户问题与完整研报会出现在 `git status` 里，存在误提交风险。

### 18. 工具超时配置未生效

`ToolSpec.timeout_seconds`、`BaseTool.timeout` 只参与 schema 输出；`run()` 直接同步执行 `execute()`。行情/新闻接口挂起时没有任何超时保护。

### 19. 计划未去重，可能产生重复工位

`orchestrator._decide_plan_by_llm` 只过滤合法名称，不去重。若模型输出 `["MarketAgent","MarketAgent"]`，`agentOrder` 会重复，前端 `agentOrder.map` 以 `name` 作为 key，出现重复 React key 与重复卡片。`_run_research_agents` 内部用 dict 构建 Agent，实际只跑一个，前后不一致。

### 20. 跨端死字段

- `InvestmentAnswer.scenarios` / `action_options` / `data_limitations`：后端从不填充，前端从不渲染。
- `evidence_refs`：值是工具名或 `asset_id`，前端未使用；同名工具多次调用会重复。
- `round1Summary`：前端写入、从未读取。

### 21. 前端轮询时长可能短于真实任务

`POLL_MAX_ATTEMPTS=150` × 1.2s ≈ 3 分钟。两轮 × 3 Agent × 8 次迭代 + 汇总 + 沉淀，真实耗时可能超过 3 分钟；SSE 若在早期断开，任务成功后前端仍会显示超时失败。

### 22. SummaryAgent 工具白名单为空

`SummaryAgent.tool_names = []`，`_execute_tool` 的白名单判断是 `if self.tool_names and ...`，空列表等于放开全部工具（含 `asset_resolve` 等与汇总无关的工具），提示词只能软约束。

### 23. 会话无保留策略

`list_sessions` 有 100 条上限，但单会话回合数、每回合内容（完整 answer + agent_results + tool_calls）无上限，`sessions.json` 会持续增长，且每次 `_save` 全量重写。

### 24. 派发 LLM 无结构化输出约束

`_decide_plan_by_llm` 用 `re.search(r"\{[\s\S]*?\}")` 取第一个对象，未使用 `response_format`；模型输出示例 JSON 或前后夹带多个对象时会静默回退到关键词规则（回退本身无日志区分）。

## 七、本次修复的管道问题

- **SSE 快照竞态（此前管道改动引入）**：`stream_events` 原先在请求处理阶段读取快照、再在生成器内订阅。若任务完成并清空事件缓冲恰好发生在两者之间，客户端既拿不到缓冲补发也拿不到快照，只能靠心跳一直等待。现已改为订阅后读取快照，保证"缓冲补发"与"快照补发"至少命中一路。
- `api/events.py` 的 `task_completed` 快照结构此前已统一为 `{result: ...}`，与实时事件一致。

## 八、优先级建议

1. 第二轮是否执行、失败是否回退第一轮（问题 1、2）——成本与结论稳定性。
2. 多轮上下文（问题 6、7）——决定"追问"是否是产品能力。
3. 置信度与降级信号（问题 4、3）——决定报告可信度与故障暴露。
4. 会话落盘竞态与 gitignore（问题 16、17）——数据完整性与隐私。
5. 超时与轮询窗口（问题 12、18、21）——长任务可用性。
6. 派发去重、死字段、沉淀门槛（问题 8、9、11、19、20）——体验与知识库质量。

## 九、复核方法与结果

| 验证项 | 方法 | 结果 |
| --- | --- | --- |
| 第二轮执行/覆盖 | 注入 stub Agent 类到 `_AGENT_MAP`，统计调用 | 两轮各执行，返回仅第二轮 |
| 置信度 | 直接调用 `SummaryAgent._compute_confidence` | 0.80 / 0.40 / 0.70（见表） |
| 降级行为 | 伪 OpenAI client，首次抛异常、后续返回 TOOL/FINAL | 工具仍被调用，`_tools_supported=False` |
| 截断 | `ReActLoop._serialize_result` 超长数据 | 3011 字符，尾部 JSON 非法 |
| 解析 | 直接调用 `_extract_answer_json` / `_parse_decision` | 仅"前置 JSON 对象"场景失败 |
| 规则派发 | `_decide_plan_by_rule` 多组输入 | 见第五节第 8 条 |
| 会话并发 | 8 线程 × 20 次 `add_turn`，独立临时文件 | 内存 160 / 文件 160，100+ 次落盘异常 |
| 会话文件忽略状态 | `git check-ignore -v src/data/sessions.json` | 未命中 |
| SDK 默认值 | `inspect.signature(openai.OpenAI.__init__)` | `max_retries=2`，`timeout` 默认 600s |

配合 `docs/多Agent重构设计方案.md` 阅读，可对照设计意图与当前实现。
