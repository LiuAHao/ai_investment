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
  round1_done: '第一轮完成·等待补充',
  done: '已完成',
  failed: '失败',
}

const STATUS_CLASS = {
  waiting: 'st-thinking',
  thinking: 'st-thinking pulse',
  tooling: 'st-tooling',
  round1_done: 'st-tooling',
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
  // 工具调用流折叠：Agent 产生结论后自动折叠（用户可手动展开）
  const [toolsExpanded, setToolsExpanded] = useState(false)
  const [avatar, avatarClass] = AVATARS[name] || ['A', 'av-mkt']
  const status = state?.status || 'waiting'
  const rawThoughts = state?.thoughts || []
  const tools = state?.tools || []
  const summary = state?.summary || ''

  // Agent 是否已产生结论（完成或第一轮完成）
  const isFinished = status === 'done' || status === 'round1_done'
  // 工具调用流折叠：Agent 完成时默认折叠（已产生结论，工具细节可收起）
  const toolsCollapsed = isFinished && !toolsExpanded
  const completedTools = tools.filter((t) => t.status !== 'running').length

  // 过滤与结论重复的收敛思考（避免"收敛: <完整结论>"在思考流与结论区展示两遍）
  const thoughts = rawThoughts.filter((t) => {
    const core = (t || '').replace(/^收敛\s*[:：]?\s*/, '').trim()
    return core && core !== summary
  })

  return (
    <div className="agent-panel">
      <div className="agent-panel-head">
        <div className={`card-avatar ${avatarClass}`}>{avatar}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="card-name">{name}</div>
          <div className="agent-index">
            {AGENT_CODENAME[name] || '调研'} · 工位 {String(index + 1).padStart(2, '0')}
            {status === 'round1_done' && <span style={{ color: 'var(--gold)', fontSize: 11 }}> · 第二轮待启动</span>}
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
          {/* 1. 思考流（从上到下，已过滤与结论重复的收敛记录） */}
          {thoughts.map((thought, i) => (
            <div key={`t${i}`} className="item fade-in">
              <span className="item-icon">💭</span>
              <div className="item-body item-think"><Markdown text={thought} /></div>
            </div>
          ))}

          {/* 2. 工具调用流（Agent 产生结论后自动折叠） */}
          {tools.length > 0 && (
            <>
              {toolsCollapsed ? (
                <div
                  className="item"
                  style={{ cursor: 'pointer', color: 'var(--text2)', userSelect: 'none' }}
                  onClick={() => setToolsExpanded(true)}
                >
                  <span className="item-icon">🔧</span>
                  <div className="item-body">
                    <span style={{ fontSize: 12 }}>
                      已调用 {completedTools} 个工具 · 点击展开工具细节
                    </span>
                  </div>
                </div>
              ) : (
                <>
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
                  {isFinished && (
                    <div
                      className="item"
                      style={{ cursor: 'pointer', color: 'var(--text3)', userSelect: 'none' }}
                      onClick={() => setToolsExpanded(false)}
                    >
                      <span className="item-icon">▴</span>
                      <div className="item-body">
                        <span style={{ fontSize: 11 }}>收起工具细节</span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </>
          )}

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
                  {status === 'round1_done' ? '第一轮结论' : '研究结论'}
                </div>
                <Markdown text={summary} />
                {status === 'round1_done' && (
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 6 }}>
                    等待第二轮补充调研后更新最终结论…
                  </div>
                )}
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
