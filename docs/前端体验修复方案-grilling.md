# 前端体验修复 · Grilling 决策记录

> 状态：已定案（按推荐执行）
> 日期：2026-10-22
> 输入：实际使用反馈 5 条 + 后端日志 + sessions.json + decisions.sqlite 实测
> 关联：`docs/投研智能体框架重构方案-v4.md`

---

## 0. 实测证据（先摆事实）

| 现象 | 实测数据 |
|---|---|
| MacroAnalyst 显示原始 JSON | `conclusion` 长度 3776，是截断 JSON；`_readable_conclusion` 解析失败后原样返回 |
| MarketAnalyst 正常 | `conclusion` 长度 327，可读摘要 |
| 报告时间框架显示英文 | `verdict.time_frame = "medium"`，`answer.time_frame` 直接透传 |
| 免责声明并未丢失 | `answer.compliance_disclaimer` 有值（"以上内容仅为投资研究辅助…"） |
| L3 跳过 | 本次 query 为"市场环境怎么样"，`intent=macro` → `debate=False`，L3 本就没执行 |
| L6 显示 0.0s | `_save_decision` 耗时 1-2ms，`toFixed(1)` 变成 `0.0s` |
| 证据 22 条但可读性差 | macro 类为 `CPI 202609：nt_val=100.9`、`nt_yoy=0.9` |
| Supervisor 浪费调用 | 22:19:58 LLM 输出了无关的"学术研究计划"模板，失败后才走规则计划 |

---

## 1. Grilling：17 个决策点

### A. 分析师输出

**A1. 分析师还要不要输出 `evidence` 数组？**

- 选项：① 保留全量 evidence ② 完全删除 ③ 改为少量 `highlights`
- **定案：③。`highlights` 最多 3 条纯事实，`gaps` / `coverage` 保留。**
- 理由：台账已经由工具结果自动登记，模型复述一遍纯属浪费输出预算，正是 3776 字符截断的直接原因。但模型有时能提炼工具没直说的事实（如"毛利率下滑是结构性的"），完全删除会丢信息，所以留 3 条。
- 影响：`AnalystOutput` 增加 `highlights`；`parse_analyst_payload` 兼容 `evidence`（旧）与 `highlights`（新）。

**A2. 截断后怎么兜底？**

- 选项：① 回退原文 ② 回退空 ③ 三层降级
- **定案：③。JSON 解析 → 正则提取 `conclusion/summary` 字段 → "采集 N 条证据，M 个问题未覆盖"。绝不回退原始 JSON。**
- 理由：回退原文就是这次 MacroAnalyst 显示 3776 字符 JSON 的原因。回退空会让用户不知道发生了什么。
- 影响：`_readable_conclusion` 重写；增加单测覆盖截断场景。

**A3. `thinking_log` 里的对话式内容（"需要我进一步…吗"）怎么处理？**

- 选项：① 全部展示 ② 全部隐藏 ③ 展示但默认折叠，并过滤对话式句子
- **定案：③。思考流默认折叠；过滤以"需要我/是否要我/如需"开头的句子。**
- 理由：思考流是过程证据，不该消失；但反问用户的内容会污染结论区。
- 影响：`AgentCard` 增加折叠开关与过滤函数。

**A4. 分析师的 `max_tokens` 要不要降？**

- 选项：① 保持 8192 ② 降到 3000 ③ 降到 4096
- **定案：③。4096。**
- 理由：输出瘦身后 4096 足够；reasoning 模型会占用预算，降太低会截断思考过程。
- 影响：`BaseAnalyst` 覆盖 `max_tokens`。

### B. 证据可读性

**B1. 中文语句在哪一层生成？**

- 选项：① 数据层 ② Ledger ③ 前端
- **定案：② 为主，① 补充。Ledger 提供 `STATEMENT_BUILDERS` 按工具生成语句；数据层只补 `metric/value/unit` 元数据。**
- 理由：前端拼中文会导致历史数据无法复用；数据层各自拼会导致口径分散。Ledger 是唯一事实入口，模板放这里最稳。
- 影响：`ledger.py` 增加模板函数；`macro_client.py` 补 `metric` 字段。

**B2. 前端展示到什么粒度？**

- 选项：① 全文 ② 截断 + 展开 ③ 只显示摘要
- **定案：②。正文 120 字截断、数值做成徽标、时间/来源小字、类别默认只展开第一组。**
- 理由：22 条全展开会把页面拉得很长；只显示摘要又丢失可核验性。
- 影响：`EvidencePanel` 重写展示层。

**B3. 要不要做证据搜索/过滤？**

- **定案：不做。P2 再说。**
- 理由：当前样本量 20-70 条，分组折叠足够，加搜索属于过度设计。

### C. 实时性

**C1. `evidence_added` 在哪儿发？**

- 选项：① 分析师结束后（现状） ② 工具执行后 ③ 两处都发
- **定案：② 工具执行后；`highlights` 另发一条带 `source=analyst` 的事件。前端按 `evidence_id` 去重。**
- 理由：现状是 L1 结束才一次性出现，用户感觉"最后一起弹"。
- 影响：`BaseReActAgent._on_tool_result` 发事件；`pipeline._ingest` 只发 highlights 增量。

**C2. 事件缓冲 200 条够不够？**

- 选项：① 保持 200 ② 提到 500 ③ 提到 2000
- **定案：② 500。**
- 理由：一个任务 22-65 条证据 + 30 条工具事件 + 20 条思考，200 在长任务上会丢早期事件；2000 没必要。
- 影响：`event_bus.MAX_BUFFER = 500`。

**C3. 面板什么时候出现？**

- **定案：按阶段占位。L1 开始显示证据空态；L2 结束显示辩论空态；L4 开始显示裁决骨架；L5 结束显示报告。**
- 理由：用户要的是"提前显示状态"，不是"提前显示内容"。
- 影响：三个面板去掉 `return null`，改为接收 `stage` 状态。

**C4. `plan_ready` 要不要处理？**

- **定案：要。前端保存 `planMeta`（debate / focus_questions / analysts），用于 L3 文案与排班。**
- 理由：现在只处理 `orchestrator_decided`，拿不到 `debate=false` 的信息，才出现"跳过"误判。

### D. 报告收尾

**D1. 时间框架在哪层中文化？**

- **定案：后端 `_to_answer` 统一映射，前端做旧数据兜底。**
- 理由：历史数据也要正确显示；双层兜底防止旧 turn 显示英文。
- 映射：`short→短期 1-4 周`、`medium→中期 1-6 个月`、`long→长期 6 个月以上`。

**D2. "截断"到底是什么？**

- 选项：① CSS 高度截断 ② 免责声明被忽略 ③ 推理内容太短造成"突然结束"
- **定案：② + ③。不改 CSS，改为显式"报告结束"区域 + 强化免责声明；同时把 `reasoning` 从 3 行扩为"裁决逻辑"。**
- 理由：CSS 里 `.card` 只有 `overflow: hidden`，没有 `max-height`；`.compliance-banner` 正常渲染但样式很轻。真正让用户觉得"截断"的是时间框架后突然没有内容。
- 影响：`SummaryCard` 末尾结构与 `_to_answer.reasoning`。

**D3. `reasoning` 写什么？**

- **定案：`revision_reason` + `confidence_calibration` + 可解决分歧的结论。不重复分歧矩阵。**
- 理由：VerdictPanel 已经展示矩阵，SummaryCard 再贴一遍会冗余。

### E. 阶段状态

**E1. L3 未启用怎么表达？**

- **定案：后端显式发 `phase_started/phase_completed`，`detail.skipped=true`、`reason=debate_disabled`；前端显示"未启用"。删掉前端"L4 完成推断跳过"的逻辑。**
- 理由：推断逻辑会把"事件丢失"误判成"跳过"。

**E2. 0.0s 怎么显示？**

- **定案：`<100ms → "<0.1s"`；无数据 → `"—"`。**

**E3. 阶段失败要不要单独状态？**

- **定案：要。`degraded` 显示 ⚠，`failed` 显示红色；当前只有 ⚠。**

### F. Supervisor 计划

**F1. 什么时候调用 LLM 计划？**

- 选项：① 总是 ② 从不 ③ 只对多资产对比
- **定案：③。`auto` 模式只对 `intent=compare` 或 `len(assets)>1` 开启；宏观/单票走规则。**
- 理由：实测宏观问题调用后输出无关的学术模板，白花 15-30 秒。

**F2. 失败要不要重试？**

- **定案：不重试。Supervisor 只调用一次，失败立刻规则兜底。**
- 理由：计划不是关键路径，规则保底已经够；重试只会放大延迟。

### G. 裁决生成

**G1. 现在做两段式吗？**

- 选项：① P0 就做 ② P1 ③ P2
- **定案：③ P2。P0 先把裁决输出瘦身（summary≤200 字、drivers≤5、disagreement≤4），抑制截断。**
- 理由：实测第二次重试能成功，说明不是不可用；两段式会改变 L4 结构，优先级低于体验问题。

**G2. 提高 `max_tokens` 还是瘦身？**

- **定案：先瘦身，不提高。**
- 理由：reasoning 模型会吃掉预算，单纯加 token 只是把成本转嫁给延迟。

### H. 范围控制

**H1. 要不要顺带重构 AgentCard？**

- **定案：只做必要改动（折叠、过滤、摘要标题），不重写。**
- 理由：AgentCard 结构稳定，重写收益低、回归风险高。

---

## 2. 最终实施清单

### P0（先改，直接解决截图里的问题）

| # | 改动 | 文件 |
|---|---|---|
| 1 | 分析师契约：`evidence` → `highlights(≤3)`，`max_tokens=4096` | `analysts/base.py`、四个分析师 prompt |
| 2 | `_readable_conclusion` 三层降级 + 截断单测 | `agents/pipeline.py`、`tests/test_readable_conclusion.py` |
| 3 | `evidence_added` 移到工具执行后；highlights 增量单独发 | `agents/base.py`、`agents/pipeline.py`、`agents/events.py` |
| 4 | 事件缓冲 200 → 500 | `services/event_bus.py` |
| 5 | horizon 中文化（后端 + 前端兜底） | `pipeline._to_answer`、`SummaryCard.jsx` |
| 6 | 报告收尾：结束分隔 + 免责声明强化 + `reasoning` 扩为裁决逻辑 | `SummaryCard.jsx`、`pipeline._to_answer` |
| 7 | L3 `skipped` 显式事件；时长 `<0.1s` | `pipeline.py`、`events.py`、`PhaseProgress.jsx` |
| 8 | 前端处理 `plan_ready`，删掉 L3 推断逻辑 | `useAgentStream.js`、`PhaseProgress.jsx` |

### P1（可读性与占位）

| # | 改动 | 文件 |
|---|---|---|
| 9 | Ledger `STATEMENT_BUILDERS`（market/valuation/fundamental/news/announcement/macro） | `agents/ledger.py` |
| 10 | macro 指标中文字典（`nt_val→当月值`、`nt_yoy→同比`） | `data/macro_client.py` |
| 11 | EvidencePanel：截断展开、数值徽标、分组折叠、空态 | `EvidencePanel.jsx` |
| 12 | Debate/Verdict 占位骨架 | `DebateTimeline.jsx`、`VerdictPanel.jsx`、`AgentWorkspace.jsx` |
| 13 | AgentCard：思考流默认折叠、过滤反问句、标题"取证摘要" | `AgentCard.jsx` |
| 14 | Supervisor：`auto` 只对 compare，失败不重试 | `pipeline._should_use_llm_plan`、`_supervise` |

### P2

| # | 改动 |
|---|---|
| 15 | 裁决两段式（短裁决 + 报告正文分开生成） |
| 16 | 证据搜索/过滤 |
| 17 | AgentCard 结构重写 |

---

## 3. 验收标准

**后端**

- `_readable_conclusion`：截断 JSON、纯文本、正常 JSON 三种输入都不返回原始 JSON。
- 分析师产出 JSON 长度中位数下降 50% 以上（对比 3776 字符）。
- `evidence_added` 事件时间戳落在工具完成后的 100ms 内。
- 宏观问题 L3 事件包含 `skipped=true`；单票问题 L3 有 turns。
- `answer.time_frame` 为"中期 1-6 个月"，不再是 `medium`。

**前端**

- 证据面板在 L1 开始后立即出现空态，工具完成后逐条增长。
- 辩论面板在 L3 开始显示（未启用时显示"未启用"）。
- 裁决面板在 L4 开始显示骨架。
- 时长 `<0.1s` 不再显示 `0.0s`。
- 报告末尾能看到"报告结束"和完整免责声明。

**回归**

- 宏观问题（`市场环境怎么样`）与单票问题（`分析贵州茅台`）各跑一次真实链路。
- 既有 46 个后端测试 + 10 个前端测试全过。
