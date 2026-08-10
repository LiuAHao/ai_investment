import React from 'react'
import AgentCard from './AgentCard'
import OrchestratorCard from './OrchestratorCard'
import SummaryCard from './SummaryCard'

/**
 * Agent 工作区（三段式流程布局）
 * PHASE 01 编排 → PHASE 02 调研工位 → PHASE 03 汇总结论
 * 只渲染实际启动的 Agent 卡片（按需调度）。
 */
const AgentWorkspace = ({ phase, orchestrator, agents, agentOrder, finalAnswer, error }) => {
  return (
    <div>
      {/* PHASE 01 编排指挥台 */}
      {(phase === 'orchestrating' || orchestrator.thoughts.length > 0 || orchestrator.plan) && (
        <OrchestratorCard
          thoughts={orchestrator.thoughts}
          plan={orchestrator.plan}
          status={phase === 'orchestrating' ? 'orchestrating' : phase === 'researching' ? 'researching' : 'done'}
        />
      )}

      {/* PHASE 02 调研工位 */}
      {agentOrder.length > 0 && (
        <>
          <div className="phase-tag">
            <span className="phase-label">PHASE 02 · RESEARCH</span>
          </div>
          <div className="agent-grid">
            {agentOrder.map((name, idx) => (
              <AgentCard key={name} name={name} state={agents[name]} index={idx} />
            ))}
          </div>
        </>
      )}

      {/* PHASE 03 汇总结论：分析中展示 SummaryAgent 进度卡（思考流+工具流），完成后展示完整研报 */}
      {(finalAnswer || phase === 'summarizing' || agents['SummaryAgent']) && (
        <>
          <div className="phase-tag">
            <span className="phase-label">PHASE 03 · CONCLUSION</span>
          </div>
          {finalAnswer ? (
            <SummaryCard answer={finalAnswer} />
          ) : (
            <AgentCard name="SummaryAgent" state={agents['SummaryAgent']} />
          )}
        </>
      )}

      {error && (
        <div className="card" style={{ borderColor: 'var(--red)' }}>
          <div className="card-body" style={{ color: 'var(--red)', fontSize: 13 }}>
            ⚠ {error}
          </div>
        </div>
      )}
    </div>
  )
}

export default AgentWorkspace
