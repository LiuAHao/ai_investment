import React from 'react'
import Markdown from '../common/Markdown'

/**
 * 历史会话中单轮研究的完整流程展示
 * 包含：编排计划 → 各调研 Agent（思考流 + 工具调用 + 结论）→ 最终报告
 */

const AVATARS = {
  MarketAgent: ['市', 'av-mkt'],
  NewsAgent: ['闻', 'av-news'],
  KnowledgeAgent: ['知', 'av-kno'],
  OrchestratorAgent: ['编', 'av-orch'],
}

const STATUS_CLASS = {
  success: 'st-done',
  failed: 'st-failed',
  skipped: 'st-thinking',
  partial: 'st-tooling',
}

const ToolCallItem = ({ tc }) => (
  <div className="item">
    <span className="item-icon">{tc.status === 'failed' ? '❌' : '✅'}</span>
    <div className="item-body">
      <span className="tool-name">{tc.tool_name}</span>
      <div className="tool-meta">
        {tc.status === 'failed'
          ? <span style={{ color: 'var(--red)' }}>失败 · {tc.error || '未知错误'}</span>
          : `完成 · ${tc.latency_ms ?? 0}ms${tc.summary ? ` · ${tc.summary}` : ''}`}
      </div>
    </div>
  </div>
)

const AgentSection = ({ agent }) => {
  const [avatar, avatarClass] = AVATARS[agent.agent_name] || ['A', 'av-mkt']
  const conclusion = (agent.conclusion || '').trim()
  // 过滤与 Agent 结论重复的收敛思考记录（如 "收敛: <完整结论>"），避免研究结论重复展示
  const thoughts = (agent.thinking_log || []).filter((t) => {
    const core = t.replace(/^收敛\s*[:：]?\s*/, '').trim()
    return core !== conclusion
  })
  const tools = agent.tool_calls || []
  const hasContent = thoughts.length > 0 || tools.length > 0

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div className="card-head">
        <div className={`card-avatar ${avatarClass}`}>{avatar}</div>
        <span className="card-name">{agent.agent_name}</span>
        {agent.error && <span className="agent-status st-failed">失败</span>}
        {agent.degraded && <span className="agent-status st-thinking">降级</span>}
      </div>
      <div className="card-body">
        {!hasContent && (
          <div className="item" style={{ color: 'var(--text3)' }}>
            <span className="item-icon">—</span>
            <div className="item-body">无详细过程记录</div>
          </div>
        )}
        {thoughts.map((thought, i) => (
          <div key={`t${i}`} className="item">
            <span className="item-icon">💭</span>
            <div className="item-body item-think"><Markdown text={thought} /></div>
          </div>
        ))}
        {tools.map((tc, i) => (
          <ToolCallItem key={`x${i}`} tc={tc} />
        ))}
        {agent.conclusion && (
          <div className="item" style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
            <span className="item-icon">📝</span>
            <div className="item-body" style={{ color: 'var(--text2)' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', letterSpacing: '.06em', marginBottom: 4 }}>Agent 结论</div>
              <Markdown text={agent.conclusion} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const FinalReport = ({ answer }) => {
  if (!answer) return null
  return (
    <div className="card">
      <div className="card-head">
        <div className="card-avatar av-sum">汇</div>
        <span className="card-name">SummaryAgent · 最终结论</span>
        <span className="agent-status st-done">已完成</span>
      </div>
      <div className="card-body">
        <div className="final-report">
          {answer.summary && (
            <div className="report-section">
              <div className="report-label">总体判断</div>
              <Markdown text={answer.summary} />
            </div>
          )}
          {answer.key_points?.length > 0 && (
            <div className="report-section">
              <div className="report-label">关键判断</div>
              {answer.key_points.map((p, i) => (
                <div key={i} style={{ marginBottom: 8 }}><Markdown text={`- ${p}`} /></div>
              ))}
            </div>
          )}
          {answer.reasoning && (
            <div className="report-section">
              <div className="report-label">推理过程</div>
              <Markdown text={answer.reasoning} />
            </div>
          )}
          {answer.risks?.length > 0 && (
            <div className="report-section">
              <div className="report-label">主要风险</div>
              {answer.risks.map((r, i) => (
                <div key={i} style={{ marginBottom: 8 }}><Markdown text={`- ${r}`} /></div>
              ))}
            </div>
          )}
          {answer.information_gaps?.length > 0 && (
            <div className="report-section">
              <div className="report-label">信息缺口</div>
              {answer.information_gaps.map((g, i) => (
                <div key={i} style={{ marginBottom: 8 }}><Markdown text={`- ${g}`} /></div>
              ))}
            </div>
          )}
          {answer.time_frame && (
            <div className="report-section">
              <div className="report-label">时间框架</div>
              <Markdown text={answer.time_frame} />
            </div>
          )}
          {answer.data_limitations?.length > 0 && (
            <div className="report-section">
              <div className="report-label">数据限制</div>
              <ul className="report-list">
                {answer.data_limitations.map((d, i) => <li key={i} style={{ color: 'var(--text3)' }}>{d}</li>)}
              </ul>
            </div>
          )}
          {answer.compliance_disclaimer && (
            <div className="compliance-banner">
              <span style={{ color: 'var(--yellow)', fontSize: 16, flexShrink: 0 }}>⚠</span>
              <span>{answer.compliance_disclaimer}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const TurnDetail = ({ turn }) => {
  const agents = turn.agent_results || []
  return (
    <div>
      {/* 问题头 */}
      <div className="card">
        <div className="card-head">
          <span style={{ fontSize: 14, fontWeight: 700, flex: 1 }}>Q: {turn.query}</span>
          <span style={{ fontSize: 12, color: 'var(--text3)' }}>{turn.timestamp}</span>
        </div>
      </div>

      {/* 各 Agent 过程（思考流 + 工具调用 + 结论） */}
      {agents.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text3)', letterSpacing: '.06em', margin: '0 0 8px' }}>
            调研过程
          </div>
          {agents.map((agent, i) => (
            <AgentSection key={i} agent={agent} />
          ))}
        </div>
      )}

      {/* 最终报告 */}
      {turn.answer && <FinalReport answer={turn.answer} />}
    </div>
  )
}

export default TurnDetail
