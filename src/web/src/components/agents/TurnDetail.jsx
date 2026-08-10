import React from 'react'
import OrchestratorCard from './OrchestratorCard'
import AgentCard from './AgentCard'
import SummaryCard from './SummaryCard'

/**
 * 历史会话中单轮研究的完整流程展示
 * 与主页（ResearchView / AgentWorkspace）一比一还原：
 * PHASE 01 编排卡 → PHASE 02 调研工位（AgentCard 网格）→ PHASE 03 总结报告（SummaryCard）
 */

// 历史 agent_results -> AgentCard 需要的 state 形态
const buildAgentState = (r) => ({
  status: r.error ? 'failed' : 'done',
  thoughts: r.thinking_log || [],
  tools: (r.tool_calls || []).map((tc) => ({
    tool: tc.tool_name,
    status: tc.status === 'failed' ? 'failed' : 'completed',
    latency: tc.latency_ms,
    summary: tc.summary,
    error: tc.error,
  })),
  summary: r.conclusion || '',
})

const TurnDetail = ({ turn }) => {
  const agentResults = turn.agent_results || []
  // 工位顺序：优先使用保存的 plan（编排派发顺序），缺失时按结果顺序兜底
  const plan = turn.plan
    || (turn.orchestrator && turn.orchestrator.plan)
    || agentResults.map((r) => r.agent_name)
  const thoughts = (turn.orchestrator && turn.orchestrator.thoughts) || []

  const agents = {}
  agentResults.forEach((r) => {
    agents[r.agent_name] = buildAgentState(r)
  })

  return (
    <div>
      {/* 问题头 */}
      <div className="card">
        <div className="card-head">
          <span style={{ fontSize: 14, fontWeight: 700, flex: 1 }}>Q: {turn.query}</span>
          <span style={{ fontSize: 12, color: 'var(--text3)' }}>{turn.timestamp}</span>
        </div>
      </div>

      {/* PHASE 01 编排指挥台 */}
      <OrchestratorCard thoughts={thoughts} plan={plan} status="done" />

      {/* PHASE 02 调研工位（与主页一致的网格布局） */}
      {plan.length > 0 && (
        <>
          <div className="phase-tag">
            <span className="phase-label">PHASE 02 · RESEARCH</span>
          </div>
          <div className="agent-grid">
            {plan.map((name, idx) => (
              <AgentCard key={name} name={name} state={agents[name]} index={idx} />
            ))}
          </div>
        </>
      )}

      {/* PHASE 03 总结报告（完整研报版式） */}
      {turn.answer && (
        <>
          <div className="phase-tag">
            <span className="phase-label">PHASE 03 · CONCLUSION</span>
          </div>
          <SummaryCard answer={turn.answer} />
        </>
      )}
    </div>
  )
}

export default TurnDetail
