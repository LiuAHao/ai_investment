# agent 模块简介

agent 模块负责多智能体编排与决策执行，聚合股票与新闻能力，并通过工具调用完成分析与回答。

## 目录与职责

- master_agent.py：主控 Agent，负责协调子 Agent 与决策流程
- stock_agent.py：股票 Agent，提供收盘后历史行情与技术指标分析
- news_agent.py：新闻 Agent，仅进行联网搜索（已移除 RSS）
- decision_agent.py：决策 Agent，基于工具调用生成结论
- investment_expert_agent.py：投资专家 Agent，基于工具结果与偏好生成建议

## 工作流概览

- 用户输入 -> 主控 Agent 选择工具 -> 子 Agent 获取数据 -> 决策 Agent 汇总输出
- 仅使用收盘后历史数据，不使用实时行情

## 主要能力

- 股票历史行情摘要、技术指标
- 联网搜索新闻与资料检索
- 工具调用结果缓存与统一汇总

## 使用说明

模块由 API 层调用，无需直接执行。若需自定义工具或策略，可在 `decision_agent.py` 中扩展工具列表与调用逻辑。

## Agent 调用关系

1. `MasterAgent.run_query()` 作为入口，接收用户问题与偏好。
2. `DecisionAgent.run_tools()` 根据问题选择工具并调用：
	- `StockAgent.analyze_daily_hist()`：历史行情摘要
	- `StockAgent.analyze_technical_indicators()`：技术指标
	- `StockAgent.fetch_daily_hist()`：历史行情原始摘要
	- `NewsAgent.get_relevant_titles()` / `NewsAgent.search_web_by_keywords()`：联网搜索
3. `InvestmentExpertAgent.summarize()` 汇总工具结果并生成最终建议。

说明：当前流程不再调用实时行情工具，新闻 RSS 拉取已移除，仅保留联网搜索。
