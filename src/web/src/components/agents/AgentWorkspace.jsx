import React from 'react'
import { AlertTriangle, Scale, Users } from 'lucide-react'
import AgentCard from './AgentCard'
import OrchestratorCard from './OrchestratorCard'
import SummaryCard from './SummaryCard'
import EvidencePanel from './EvidencePanel'
import DebateTimeline from './DebateTimeline'
import PhaseProgress from './PhaseProgress'
import VerdictPanel from './VerdictPanel'

const SectionHead = ({ icon, title, meta }) => (
  <div className="section-head">
    {icon}
    <span className="section-title">{title}</span>
    {meta && <span className="section-meta">{meta}</span>}
  </div>
)

/**
 * 投研工作区
 * 进度 → 分工 → 取证 → 证据台账 → 多空辩论 → 裁决 → 研报
 * 只渲染实际启动的分析师卡片。
 */
const AgentWorkspace = ({
  phase,
  orchestrator,
  agents,
  agentOrder,
  finalAnswer,
  evidence = [],
  debateTurns = [],
  verdict = null,
  verification = null,
  theses = {},
  phases = {},
  debateInfo = null,
  error,
  recoveredByPolling,
}) => {
  const showConclusion = Boolean(
    finalAnswer || verdict || phase === 'summarizing' || agents.SummaryAgent
    || phases?.L4 || phases?.L5
  )
  const evidenceActive = Boolean(phases?.L1) || evidence.length > 0
  const l3Skipped = Boolean(phases?.L3?.detail?.skipped)
  const l3Reason = phases?.L3?.detail?.reason
  const debateActive = Boolean(phases?.L3) || Boolean(debateInfo) || debateTurns.length > 0
  const debateSkippedLabel = l3Skipped
    ? (l3Reason === 'debate_disabled'
      ? '本次为宏观/无明确标的研究，未启用多空辩论。'
      : '一方论点不足，已跳过辩论。')
    : ''
  const verdictActive = Boolean(phases?.L4) || Boolean(verdict)

  return (
    <div>
      {recoveredByPolling && (
        <div className="polling-recovery-hint">
          实时事件流已中断，最终结果来自任务状态查询，中间过程可能不完整。
        </div>
      )}

      <PhaseProgress phases={phases} />

      {(phase === 'orchestrating' || orchestrator.thoughts.length > 0 || orchestrator.plan) && (
        <OrchestratorCard
          thoughts={orchestrator.thoughts}
          plan={orchestrator.plan}
          status={phase === 'orchestrating' ? 'orchestrating' : phase === 'researching' ? 'researching' : 'done'}
        />
      )}

      {agentOrder.length > 0 && (
        <>
          <SectionHead icon={<Users size={14} />} title="取证记录" meta={`${agentOrder.length} 位分析师`} />
          <div className="agent-grid">
            {agentOrder.map((name, index) => (
              <AgentCard key={name} name={name} state={agents[name]} index={index} />
            ))}
          </div>
        </>
      )}

      <EvidencePanel evidence={evidence} active={evidenceActive} />

      <DebateTimeline
        turns={debateTurns}
        theses={theses}
        active={debateActive}
        skippedLabel={debateSkippedLabel}
        reason={debateInfo?.stopped_reason || ''}
        controversy={debateInfo?.controversy || phases?.L3?.detail?.controversy || null}
      />

      {showConclusion && (
        <>
          <SectionHead
            icon={<Scale size={14} />}
            title="裁决与研报"
            meta={verdict ? '已形成结论' : '正在收束'}
          />
          <VerdictPanel verdict={verdict} verification={verification} active={verdictActive} />
          {finalAnswer ? (
            <SummaryCard answer={finalAnswer} />
          ) : agents.SummaryAgent ? (
            <AgentCard name="SummaryAgent" state={agents.SummaryAgent} />
          ) : null}
        </>
      )}

      {error && (
        <div className="card" style={{ borderColor: 'rgba(229,72,77,.35)' }}>
          <div className="card-body" style={{ color: 'var(--red)', fontSize: 13, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
            <span>{error}</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default AgentWorkspace
