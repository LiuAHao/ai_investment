import React from 'react'
import { HelpCircle, Scale, Users } from 'lucide-react'
import OrchestratorCard from './OrchestratorCard'
import AgentCard from './AgentCard'
import SummaryCard from './SummaryCard'
import EvidencePanel from './EvidencePanel'
import DebateTimeline from './DebateTimeline'
import PhaseProgress from './PhaseProgress'
import VerdictPanel from './VerdictPanel'
import { phasesFromTrace } from '../../utils/phases'
import { formatDateTime } from '../../utils/format'

const SectionHead = ({ icon, title, meta }) => (
  <div className="section-head">
    {icon}
    <span className="section-title">{title}</span>
    {meta && <span className="section-meta">{meta}</span>}
  </div>
)

const buildAgentState = (result) => ({
  status: result.error ? 'failed' : 'done',
  thoughts: result.thinking_log || [],
  tools: (result.tool_calls || []).map((call) => ({
    tool: call.tool_name,
    status: call.status === 'failed' ? 'failed'
      : call.status === 'skipped' ? 'skipped' : 'completed',
    latency: call.latency_ms,
    summary: call.summary,
    error: call.error,
  })),
  summary: result.conclusion || '',
  degraded: Boolean(result.degraded),
})

/**
 * 历史会话中单轮研究的完整回放。
 */
const TurnDetail = ({ turn }) => {
  const agentResults = turn.agent_results || []
  const plan = turn.plan
    || (turn.orchestrator && turn.orchestrator.plan)
    || agentResults.map((result) => result.agent_name)
  const thoughts = (turn.orchestrator && turn.orchestrator.thoughts) || []
  const evidence = turn.evidence || []
  const debateTurns = (turn.debate && turn.debate.turns) || []
  const verdict = turn.verdict || null
  const verification = turn.verification || null
  const theses = turn.thesis || {}
  const phases = phasesFromTrace(turn.trace)
  const debateInfo = turn.debate || {}

  const agents = {}
  agentResults.forEach((result) => {
    agents[result.agent_name] = buildAgentState(result)
  })

  return (
    <div>
      <section className="card turn-question">
        <div className="card-body">
          <HelpCircle size={16} style={{ color: 'var(--gold)', flexShrink: 0 }} />
          <div className="turn-question-text">{turn.query}</div>
          <span className="turn-question-meta">{formatDateTime(turn.timestamp)}</span>
        </div>
      </section>

      <PhaseProgress phases={phases} />

      <OrchestratorCard thoughts={thoughts} plan={plan} status="done" />

      {plan.length > 0 && (
        <>
          <SectionHead icon={<Users size={14} />} title="取证记录" meta={`${plan.length} 位分析师`} />
          <div className="agent-grid">
            {plan.map((name, index) => (
              <AgentCard key={name} name={name} state={agents[name]} index={index} />
            ))}
          </div>
        </>
      )}

      <EvidencePanel evidence={evidence} />

      <DebateTimeline
        turns={debateTurns}
        theses={theses}
        active={debateTurns.length > 0 || Boolean(debateInfo?.executed)}
        reason={debateInfo?.stopped_reason || ''}
        skippedLabel={debateInfo?.executed ? '' : (debateInfo?.stopped_reason || '')}
        controversy={debateInfo?.controversy || phases?.L3?.detail?.controversy || null}
      />

      {turn.answer && (
        <>
          <SectionHead icon={<Scale size={14} />} title="裁决与研报" meta="历史归档" />
          <VerdictPanel verdict={verdict} verification={verification} />
          <SummaryCard answer={turn.answer} />
        </>
      )}
    </div>
  )
}

export default TurnDetail
