import React, { useState } from 'react'
import Markdown from '../common/Markdown'

const AVATARS = {
  MarketAgent: ['市', 'av-mkt'],
  NewsAgent: ['闻', 'av-news'],
  KnowledgeAgent: ['知', 'av-kno'],
}

const STATUS_LABEL = {
  waiting: '等待调度',
  thinking: '思考中',
  tooling: '工具调用中',
  done: '已完成',
  failed: '失败',
}

const STATUS_CLASS = {
  waiting: 'st-thinking',
  thinking: 'st-thinking pulse',
  tooling: 'st-tooling',
  done: 'st-done',
  failed: 'st-failed',
}

const AGENT_CODENAME = {
  MarketAgent: '市场行情',
  NewsAgent: '新闻舆情',
  KnowledgeAgent: '知识库',
}

const AgentCard = ({ name, state, index = 0 }) => {
  const [collapsed, setCollapsed] = useState(false)
  const [avatar, avatarClass] = AVATARS[name] || ['A', 'av-mkt']
  const status = state?.status || 'waiting'
  const thoughts = state?.thoughts || []
  const tools = state?.tools || []
  const summary = state?.summary || ''

  return (
    <div className="agent-panel">
      <div className="agent-panel-head">
        <div className={`card-avatar ${avatarClass}`}>{avatar}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="card-name">{name}</div>
          <div className="agent-index">
            {AGENT_CODENAME[name] || '调研'} · 工位 {String(index + 1).padStart(2, '0')}
          </div>
        </div>
        <span className={`agent-status ${STATUS_CLASS[status] || 'st-thinking'}`}>
          {STATUS_LABEL[status] || status}
          {status === 'tooling' && <span className="loading-dots" />}
        </span>
        <button
          onClick={() => setCollapsed((v) => !v)}
          style={{ background: 'transparent', border: 'none', color: 'var(--text3)', fontSize: 12 }}
        >
          {collapsed ? '展开 ▾' : '收起 ▴'}
        </button>
      </div>
      {!collapsed && (
        <div className="agent-panel-body">
          {/* 1. 思考流（从上到下） */}
          {thoughts.map((thought, i) => (
            <div key={`t${i}`} className="item fade-in">
              <span className="item-icon">💭</span>
              <div className="item-body item-think"><Markdown text={thought} /></div>
            </div>
          ))}

          {/* 2. 工具调用流 */}
          {tools.map((tool, i) => (
            <div key={`x${i}`}>
              <div className="item">
                <span className="item-icon">
                  {tool.status === 'running' ? '🔧' : tool.status === 'failed' ? '❌' : '✅'}
                </span>
                <div className="item-body">
                  <span className="tool-name">
                    {tool.tool}({formatParams(tool.params)})
                  </span>
                  <div className="tool-meta">
                    {tool.status === 'running' && <span className="loading-dots">执行中</span>}
                    {tool.status === 'completed' && `完成 · ${tool.latency ?? ''}ms${tool.summary ? ` · ${tool.summary}` : ''}`}
                    {tool.status === 'failed' && <span style={{ color: 'var(--red)' }}>失败 · {tool.error}</span>}
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* 3. 结论（固定在面板底部） */}
          {summary && (
            <div
              className="item fade-in"
              style={{
                marginTop: 10, padding: '10px 12px', borderTop: '1px solid var(--border)',
                background: 'rgba(224,49,49,.05)', borderRadius: 8,
              }}
            >
              <span className="item-icon">📝</span>
              <div className="item-body">
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--gold)', letterSpacing: '.12em', marginBottom: 4 }}>
                  研究结论
                </div>
                <Markdown text={summary} />
              </div>
            </div>
          )}

          {!thoughts.length && !tools.length && !summary && (
            <div className="item" style={{ color: 'var(--text3)' }}>
              <span className="item-icon">⏳</span>
              <div className="item-body">等待编排器调度...</div>
            </div>
          )}
        </div>
      )}
      <div className="agent-panel-foot">
        已调用 {tools.filter((t) => t.status !== 'running').length} 个工具 · {thoughts.length} 次思考
      </div>
    </div>
  )
}

function formatParams(params) {
  if (!params) return ''
  try {
    const str = JSON.stringify(params)
    return str.length > 40 ? `${str.slice(0, 40)}…` : str
  } catch {
    return ''
  }
}

export default AgentCard
