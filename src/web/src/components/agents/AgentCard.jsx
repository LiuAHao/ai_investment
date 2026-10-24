import React, { useState } from 'react'
import {
  Brain, Check, ChevronDown, ChevronUp, FileText, Loader2, Minus, Wrench, X,
} from 'lucide-react'
import Markdown from '../common/Markdown'
import { agentMeta, toolLabel } from '../../utils/format'

const STATUS_LABEL = {
  waiting: '等待调度',
  thinking: '思考中',
  tooling: '取证中',
  done: '已完成',
  failed: '失败',
  skipped: '不适用',
}

const STATUS_CLASS = {
  waiting: 'st-waiting',
  thinking: 'st-thinking',
  tooling: 'st-tooling',
  done: 'st-done',
  failed: 'st-failed',
  skipped: 'st-waiting',
}

const ToolStatusIcon = ({ status }) => {
  if (status === 'running') return <Loader2 size={11} className="spin" />
  if (status === 'failed') return <X size={11} />
  if (status === 'skipped') return <Minus size={11} />
  return <Check size={11} />
}

const AgentCard = ({ name, state }) => {
  const [collapsed, setCollapsed] = useState(false)
  const [toolsExpanded, setToolsExpanded] = useState(false)
  const [thoughtsExpanded, setThoughtsExpanded] = useState(false)

  const meta = agentMeta(name)
  const status = state?.status || 'waiting'
  const rawThoughts = state?.thoughts || []
  const tools = state?.tools || []
  const summary = state?.summary || ''
  const isSummaryAgent = name === 'SummaryAgent'

  const isFinished = status === 'done' || status === 'skipped'
  const toolsCollapsed = isFinished && !toolsExpanded
  const completedTools = tools.filter((tool) => tool.status !== 'running').length

  const thoughts = rawThoughts
    .filter((thought) => {
      const core = (thought || '').replace(/^收敛\s*[:：]?\s*/, '').trim()
      return core && core !== summary
    })
    .map((thought) => (thought || '')
      .split('\n')
      .filter((line) => !/^\s*(需要我|是否要我|如需|要不要|我可以)/.test(line))
      .join('\n')
      .trim())
    .filter(Boolean)

  return (
    <article className={`agent-panel fade-in ${isFinished ? 'is-done' : ''}`}>
      <header className="agent-panel-head">
        <div className={`card-avatar av-${meta.tone}`}>{meta.short}</div>
        <div className="agent-title-row">
          <div className="agent-title">{meta.title}</div>
          <div className="agent-role">{meta.role}</div>
        </div>
        <span className={`agent-status ${STATUS_CLASS[status] || 'st-waiting'}`}>
          {status === 'thinking' || status === 'tooling' ? (
            <Loader2 size={11} className="spin" />
          ) : null}
          {STATUS_LABEL[status] || status}
        </span>
        <button
          type="button"
          className="icon-btn"
          onClick={() => setCollapsed((value) => !value)}
          aria-label={collapsed ? '展开分析师卡片' : '收起分析师卡片'}
          aria-expanded={!collapsed}
        >
          {collapsed ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
        </button>
      </header>

      {!collapsed && (
        <div className="agent-panel-body">
          {summary && (
            <div className="agent-conclusion">
              <div className="conclusion-label">
                <FileText size={11} />
                {isSummaryAgent ? '综合结论' : isFinished ? '取证结论' : '阶段性结论'}
              </div>
              <Markdown text={summary} />
            </div>
          )}

          {thoughts.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <button
                type="button"
                className={`disclosure ${thoughtsExpanded ? 'is-open' : ''}`}
                onClick={() => setThoughtsExpanded((value) => !value)}
              >
                <Brain size={13} />
                {thoughtsExpanded ? '收起思考过程' : `思考过程 · ${thoughts.length} 条`}
                <ChevronDown size={12} />
              </button>
              {thoughtsExpanded && (
                <div style={{ marginTop: 6 }}>
                  {thoughts.map((thought, thoughtIndex) => (
                    <div key={`thought-${thoughtIndex}`} className="item fade-in">
                      <span className="item-icon"><Brain size={12} /></span>
                      <div className="item-body"><Markdown text={thought} /></div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tools.length > 0 && (
            <div>
              <button
                type="button"
                className={`disclosure ${!toolsCollapsed ? 'is-open' : ''}`}
                onClick={() => setToolsExpanded((value) => !value)}
              >
                <Wrench size={13} />
                {toolsCollapsed
                  ? `已调用 ${completedTools} 个数据工具`
                  : `收起工具明细 · ${completedTools} 个`}
                <ChevronDown size={12} />
              </button>
              {!toolsCollapsed && (
                <div className="tool-list">
                  {tools.map((tool, toolIndex) => (
                    <div
                      key={`tool-${toolIndex}`}
                      className={`tool-row is-${tool.status || 'completed'}`}
                      title={tool.summary || tool.error || ''}
                    >
                      <span className="tool-dot" />
                      <span className="tool-name">{toolLabel(tool.tool)}</span>
                      <span className="tool-meta">
                        <ToolStatusIcon status={tool.status} />
                        {' '}
                        {tool.status === 'running' ? '执行中'
                          : tool.status === 'failed' ? '失败'
                            : tool.status === 'skipped' ? '不适用'
                              : tool.latency != null ? `${(tool.latency / 1000).toFixed(1)}s`
                                : '完成'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {!thoughts.length && !tools.length && !summary && (
            <div className="agent-empty">
              <Loader2 size={13} className={status === 'waiting' ? '' : 'spin'} />
              {status === 'waiting' ? '等待研究主管分配任务' : '正在准备取证…'}
            </div>
          )}
        </div>
      )}
    </article>
  )
}

export default AgentCard
