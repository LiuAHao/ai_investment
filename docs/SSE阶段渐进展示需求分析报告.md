# SSE 阶段渐进展示需求分析报告

## 1. 需求概述

你希望研究页里的流程展示从现在的“阶段骨架一次性全显示”，改成：

- 后端真正执行到某个阶段时，该阶段才浮现
- 阶段里的条目也跟随后端执行进度逐步出现
- 工具执行过程尽量通过 SSE 日志实时展示
- 页面看到的是“真实执行轨迹”，而不是预铺好的静态流程图

这个需求**合理，而且很有价值**。

它解决的是当前前端一个明显问题：  
页面虽然接了 SSE，但流程区的主体结构仍然是“预渲染 + 改状态”，导致用户感知上像是假流程，不利于测试和排障。

---

## 2. 当前实现现状

从前端代码看，当前研究页主要逻辑在：

- `src/web/src/components/research/ResearchChatView.jsx:23`
- `src/web/src/components/research/ResearchChatView.jsx:61`
- `src/web/src/components/research/ResearchChatView.jsx:198`
- `src/web/src/components/research/ResearchChatView.jsx:447`

### 当前行为可以概括为两层

#### 2.1 流程结构是预定义死的
在 `src/web/src/components/research/ResearchChatView.jsx:23` 开始定义了固定的 `PHASES`。  
在 `src/web/src/components/research/ResearchChatView.jsx:10` 开始定义了固定的 `AGENTS`。

也就是说：

- 阶段顺序是前端写死的
- 每个阶段有哪些节点也是前端写死的
- 页面渲染时直接按这份静态配置整段输出

#### 2.2 SSE 只是拿来改“状态”
在 `src/web/src/components/research/ResearchChatView.jsx:198` 的 `handleEvent` 中，已经接收这些事件：

- `node_started`
- `node_completed`
- `tool_started`
- `tool_completed`
- `evidence_added`
- `critic_completed`
- `compliance_completed`
- `draft_created`
- `task_completed`
- `task_failed`

但这些事件目前主要用于：

- 设置 `activePhase`
- 设置 agent 的 `pending/running/completed`
- 追加 tool 卡片
- 追加 evidence
- 最终落 answer

### 直接导致的问题

在 `src/web/src/components/research/ResearchChatView.jsx:447` 这里，前端会对 `PHASES.map(...)` 全量渲染。  
所以用户一开始就能看到：

- 问题理解
- 动态规划
- 并行工具执行
- 证据汇总
- 生成与校验
- 最终结论

只是状态有些是“等待”，有些是“运行中”。

这和你想要的“执行到哪儿才出现哪儿”不是一个交互模型。

---

## 3. 你的需求是否合理

## 结论：合理，且建议做

原因有三点。

### 3.1 更符合真实运行过程
如果流程是事件驱动渐进出现，用户看到的是：

- 系统先理解问题
- 再进入规划
- 再开始工具执行
- 再汇总证据
- 再生成和校验答案

这比“整张流程图先铺满”更真实。

### 3.2 更利于测试
你现在正在测前后端联动。  
如果某个阶段其实没执行，但 UI 结构先展示出来，就很容易误判：

- 是前端写死了
- 还是后端真发过事件
- 某阶段到底有没有跑到

渐进展示后，测试判断会清晰很多。

### 3.3 更利于排障
如果加上 SSE 日志流，出现问题时会更容易定位：

- 卡在 Router 还是 Planner
- 是工具没启动，还是启动了但没返回
- 是没有 evidence，还是 evidence 追加失败

---

## 4. 这个需求好不好做

## 结论：中等难度，可做，不算特别难

### 好做的部分
前端已经有这些基础：

- SSE 已接入  
  `src/web/src/components/research/ResearchChatView.jsx:198`
- 节点到阶段的映射已存在  
  `src/web/src/components/research/ResearchChatView.jsx:131`
- 工具执行状态结构已存在  
  `src/web/src/components/research/ResearchChatView.jsx:222`
- 轮询补偿机制已存在  
  `src/web/src/components/research/ResearchChatView.jsx:274`

所以不是从零做。

### 难点主要在两处

#### 4.1 前端状态模型要从“静态骨架”变成“动态可见集”
现在前端的思路是：

- 全阶段存在
- 只更新状态

你要的思路是：

- 阶段默认不可见
- 某阶段第一次收到相关事件时，才加入可见列表
- 某节点第一次收到相关事件时，才加入该阶段的已展示条目

这是状态模型升级，不是纯样式改动。

#### 4.2 SSE 事件粒度可能不够细
如果后端现在只会发：

- `node_started`
- `node_completed`
- `tool_started`
- `tool_completed`

那前端已经能做“阶段渐进浮现”。  
但如果你还想要“日志感”更强，比如：

- 正在解析问题
- 正在抽取资产代码
- 正在生成任务
- 正在调用新闻接口
- 正在整理论据

那最好后端再发更细的事件，例如：

- `node_log`
- `tool_log`
- `phase_started`
- `phase_completed`

否则前端只能根据有限事件模拟过程，真实感会差一点。

---

## 5. 推荐的目标交互

我建议把目标拆成两层，不要一步做到过重。

## 第一层：阶段/节点渐进浮现
用户看到的规则：

- 初始只显示“正在分析”容器，不显示完整流程图
- 收到某阶段第一个相关事件时，显示该阶段
- 收到某节点第一个相关事件时，显示该节点
- 节点完成后改状态
- 工具区只有收到 `tool_started` 后才出现
- 证据池只有收到 `evidence_added` 后才出现
- 校验区只有收到 `critic_completed` 或 `compliance_completed` 后才出现
- 报告区只有收到 `draft_created` 或最终结果后才出现

这是最核心、最值得先做的一层。

## 第二层：SSE 日志流增强
在第一层稳定后，再增强“过程感”：

- 每个 agent 节点下面展示实时日志
- 工具卡片下面展示实时日志
- 失败时保留最后几条日志
- 完成时保留摘要

这一步更偏“可观测性增强”。

---

## 6. 推荐的前端实现思路

## 方案方向：保留静态配置，但改成“按事件驱动显隐”

这是我最推荐的方案。

### 为什么不建议把 PHASES/AGENTS 全删掉
因为这些配置本身不是问题。  
问题不在“有静态配置”，而在“静态配置被一次性渲染出来”。

保留配置的好处：

- 顺序稳定
- UI 可控
- 不需要后端每次把完整元数据都传给前端
- 改动面比“完全由后端驱动布局”小很多

### 更合适的做法
保留：

- `PHASES`
- `AGENTS`
- `mapNodeToAgent`
- `mapNodeToPhase`

新增前端运行态数据：

- `visiblePhases`
- `visibleAgentsByPhase`
- `agentLogs`
- `toolLogs`

然后渲染逻辑从：

- `PHASES.map(...)`

改成：

- 只渲染 `visiblePhases` 中已激活的阶段
- 每个阶段内只渲染已激活节点
- 但顺序仍参考原来的 `PHASES/AGENTS` 配置

这样是“最小侵入改法”。

---

## 7. 对后端 SSE 事件的要求

## 最低要求：当前事件基本够用
如果后端稳定发送这些事件，其实已经能做第一层效果：

- `node_started`
- `node_completed`
- `tool_started`
- `tool_completed`
- `evidence_added`
- `critic_completed`
- `compliance_completed`
- `draft_created`
- `task_completed`
- `task_failed`

前端可用这些事件推断：

- 哪个阶段该出现
- 哪个节点该出现
- 哪个节点状态变了
- 哪个工具开始/结束了
- 哪些结果可以展示了

## 更理想的增强事件
如果你要“日志感更强”，建议后端新增：

- `node_log`
- `tool_log`
- `phase_started`
- `phase_completed`

建议 payload 大致包含：

- `task_id`
- `phase`
- `node`
- `tool_name`
- `message`
- `timestamp`
- `level`

这样前端就不需要猜。

---

## 8. 可能的前端状态重构点

核心改动会集中在：

- `src/web/src/components/research/ResearchChatView.jsx:61`
- `src/web/src/components/research/ResearchChatView.jsx:198`
- `src/web/src/components/research/ResearchChatView.jsx:447`
- `src/web/src/components/research/ResearchChatView.jsx:505`
- `src/web/src/components/research/ResearchChatView.jsx:556`

### 建议新增的状态
可考虑增加：

- `visiblePhaseIds`
- `visibleAgentIds`
- `agentEventLogs`
- `toolEventLogs`

### handleEvent 需要增强
在 `src/web/src/components/research/ResearchChatView.jsx:198` 附近：

- `node_started` 时
  - 激活对应 phase
  - 激活对应 agent
  - agent 状态改为 running
- `node_completed` 时
  - agent 状态改为 completed
- `tool_started` 时
  - 激活“并行工具执行”阶段
  - 加入工具卡片
- `evidence_added` 时
  - 激活“证据汇总”区
- `critic_completed` / `compliance_completed` 时
  - 激活“生成与校验”区
- `draft_created` / `task_completed` 时
  - 激活报告区

### 渲染逻辑需要改
在 `src/web/src/components/research/ResearchChatView.jsx:447` 附近：

当前是“全渲染”。  
应改为“按 visible 集合过滤后再渲染”。

---

## 9. 风险与注意点

### 9.1 不能过度依赖事件绝对有序
SSE 在真实环境里可能会出现：

- 事件稍微乱序
- 某类事件缺失
- 重连后丢部分中间消息

所以前端状态机要设计成：

- 幂等
- 收到 `completed` 时如果还没 `started`，也能补显示
- 不因为少一条日志就崩

### 9.2 轮询补偿仍然要保留
现在的轮询兜底在  
`src/web/src/components/research/ResearchChatView.jsx:274`  
这个机制不要删。

原因是：

- SSE 适合过程展示
- 轮询适合保底拿最终态

这两者是互补，不冲突。

### 9.3 “等待”一词要谨慎
如果你改成渐进浮现，其实很多未出现的节点就不该显示“等待”了。  
因为它们还没进入用户视野。

更好的规则是：

- 未激活：不显示
- 已激活未完成：运行中 / 等待后续事件
- 已完成：已完成
- 失败：失败

这样逻辑更自洽。

---

## 10. 推荐的分阶段落地顺序

## 第一阶段：只做“渐进浮现”
目标：

- 阶段按执行进度出现
- 节点按执行进度出现
- 不新增复杂日志协议
- 工具卡片继续沿用现有 `tool_started/tool_completed`

这个阶段投入相对可控，收益很高。

## 第二阶段：补日志流
目标：

- agent 节点下显示实时日志
- tool 卡片下显示实时日志
- 保留最后若干条

这需要后端事件更细，最好配合改。

## 第三阶段：补阶段级事件
目标：

- phase_started / phase_completed 明确化
- 减少前端通过 node->phase 推断的复杂度

这属于协议质量提升。

---

## 11. 我对需求的结论

## 结论
你的需求：

- 合理
- 值得做
- 对联调测试和后续可观测性都有明显帮助
- 不是小修小补，但也绝对不是重构过头的需求

### 最推荐的实施策略
先做这一版：

1. 保留现有 `PHASES` / `AGENTS` 配置
2. 改成基于 SSE 事件的渐进显示
3. 保留轮询兜底
4. 后端如果暂时不改协议，先利用现有 `node_started/tool_started/...` 做第一版
5. 后续再补 `node_log/tool_log`

---

## 12. 一句话建议

如果你的目标是“这个页面能真实反映后端到底跑到哪里”，那这次改造非常值得做；我建议先做**阶段/节点渐进浮现**，再做**SSE 日志流增强**，不要两件事一次打满。

如果你要，下一步可以继续补一版：  
**前后端分别要改什么、事件协议怎么定、前端状态结构怎么收敛**。