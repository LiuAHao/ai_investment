import React from 'react'

const OrchestratorCard = ({ thoughts, plan, status }) => {
  const active = status === 'orchestrating'
  return (
    <div className="orchestrator-bar">
      <div className="orch-head">
        <div className={`orch-node ${active ? 'working' : ''}`}>编</div>
        <div className="orch-name">
          OrchestratorAgent · 编排指挥
          <small>ASSET RESOLVE &amp; PLAN</small>
        </div>
        {active ? (
          <span className="agent-status st-thinking pulse">思考中</span>
        ) : plan ? (
          <span className="agent-status st-done">已完成</span>
        ) : null}
      </div>
      <div className="card-body" style={{ padding: '12px 0 0' }}>
        {thoughts.map((thought, i) => (
          <div key={i} className="item fade-in">
            <span className="item-icon">💭</span>
            <div className="item-body item-think">{thought}</div>
          </div>
        ))}
        {plan && (
          <div className="orch-plan">
            <span style={{ fontSize: 14 }}>📋</span>
            <span className="orch-plan-text">
              已启动：<b>{(plan || []).join(' + ')}</b>
            </span>
            {plan.length < 3 && (
              <span className="orch-plan-reason">
                ↳ 未启动的 Agent 不展示
              </span>
            )}
          </div>
        )}
        {!thoughts.length && !plan && (
          <div className="item" style={{ color: 'var(--text3)' }}>
            <span className="item-icon">⏳</span>
            <div className="item-body">正在分析问题意图...</div>
          </div>
        )}
      </div>
    </div>
  )
}

export default OrchestratorCard
