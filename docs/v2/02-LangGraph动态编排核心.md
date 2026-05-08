# 02 - LangGraph 动态编排核心

## 目标

本阶段目标是把 V1 的固定执行链路升级为 V2 的动态图编排。系统不再默认执行所有 Agent，而是根据用户问题动态决定：

- 是否需要资产识别。
- 是否需要行情数据。
- 是否需要新闻。
- 是否需要 RAG。
- 是否需要宏观分析。
- 是否需要补查。
- 是否需要修改答案。

## 当前 V1 问题

V1 的主链路大致为：

```text
识别股票
  ↓
DataAgent
  ↓
NewsAgent
  ↓
KnowledgeAgent
  ↓
AnalysisAgent
```

即使用户只是问“什么是市盈率”，系统仍容易走完整投资分析链路。V2 需要让编排逻辑根据问题类型动态变化。

## V2 图结构

推荐主图：

```text
load_context
  ↓
route_intent
  ↓
resolve_assets
  ↓
plan_tasks
  ↓
execute_tools
  ↓
collect_evidence
  ↓
should_replan?
  ├── yes → plan_tasks
  └── no
       ↓
draft_answer
  ↓
critic_check
  ↓
should_revise?
  ├── yes → revise_answer
  └── no
       ↓
compliance_check
  ↓
should_block?
  ├── yes → safe_response
  └── no → finalize_answer
       ↓
save_memory
```

## 节点说明

### load_context

职责：

- 加载用户信息。
- 加载当前 session 的聊天历史。
- 加载用户风险偏好。
- 加载上一轮研究上下文。

输入：

- `user_id`
- `session_id`
- `query`

输出：

- `chat_history`
- `user_profile`

### route_intent

职责：

- 判断问题意图。
- 判断是否为追问。
- 判断需要哪些能力。

输出示例：

```json
{
  "primary_intent": "asset_analysis",
  "secondary_intents": ["risk_check"],
  "user_horizon": "medium",
  "requires_realtime_data": true,
  "requires_news": true,
  "requires_macro": false,
  "confidence": 0.86
}
```

### resolve_assets

职责：

- 识别资产。
- 对追问继承上一轮资产。
- 对歧义资产给出候选。

可以跳过的场景：

- 纯知识问答。
- 用户没有提到具体资产，且上下文也没有资产。

### plan_tasks

职责：

- 根据意图和资产生成执行计划。
- 从工具注册中心选择工具。
- 设置停止条件和超时。

### execute_tools

职责：

- 按 plan 调用工具。
- 支持并行执行无依赖工具。
- 收集 ToolResult。
- 捕获异常并降级。

### collect_evidence

职责：

- 将 ToolResult 转换为 EvidenceItem。
- 对证据排序。
- 判断证据是否足够。

### draft_answer

职责：

- 基于证据生成初稿。
- 不直接作为最终答案返回。

### critic_check

职责：

- 检查证据支撑度。
- 检查遗漏风险。
- 检查逻辑跳跃。

### compliance_check

职责：

- 检查合规表达。
- 检查高风险建议。
- 检查 Prompt 注入痕迹。

### finalize_answer

职责：

- 生成用户可读答案。
- 保存结构化答案。
- 更新任务状态。

## 条件边设计

### should_replan

返回：

- `replan`
- `draft`

触发重新规划的条件：

- 资产识别置信度过低。
- 关键工具失败。
- 证据数量不足。
- 用户问题要求对比，但只识别出一个资产。
- Planner 要求的必需工具没有成功。

### should_revise

返回：

- `revise`
- `compliance`

触发修改答案的条件：

- Critic 分数低于阈值。
- 存在未被证据支持的结论。
- 缺少关键风险。
- 回答不符合用户风险偏好。

### should_block

返回：

- `block`
- `final`

触发安全回答的条件：

- 出现确定性收益承诺。
- 出现诱导交易。
- 用户要求内幕消息。
- 用户要求绕过风险提示。

## ReAct 循环控制

V2 可以保留 ReAct 思想，但不要让模型无限循环。

建议限制：

- 最大迭代次数：6。
- 单工具超时：20 秒。
- 总任务超时：120 秒。
- 相同工具同参数最多调用 1 次。
- 重新规划最多 2 次。
- Critic 修改最多 1 次。

## 状态 Trace

每个节点应写入 trace：

```json
{
  "node": "plan_tasks",
  "status": "completed",
  "input_summary": "intent=asset_analysis, asset=cn_stock:300750",
  "output_summary": "planned 3 steps",
  "latency_ms": 210,
  "created_at": "2026-05-08T10:00:00"
}
```

trace 用途：

- 前端调试模式展示。
- 失败排查。
- 自动评测工具选择。
- 面试展示 Agent 过程。

## 最小实现路线

第一版不需要把所有节点都做复杂。

优先实现：

1. `load_context`
2. `route_intent`
3. `resolve_assets`
4. `plan_tasks`
5. `execute_tools`
6. `draft_answer`
7. `finalize_answer`

第二版再加入：

1. `collect_evidence`
2. `critic_check`
3. `compliance_check`
4. `revise_answer`
5. `save_memory`

## 验收标准

- 问“分析宁德时代”时，系统调用资产识别、行情、新闻、RAG、答案生成。
- 问“什么是市盈率”时，系统不调用行情工具，只走知识问答。
- 问“那未来三个月呢”时，系统能继承上一轮资产。
- 工具失败时，任务不会整体崩溃，而是降级回答。
- 调试模式能看到节点执行轨迹。
