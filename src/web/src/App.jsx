import React, { useEffect, useRef, useState } from 'react'
import { ArrowUp, History, Plus, Sparkles } from 'lucide-react'
import { useAgentStream } from './hooks/useAgentStream'
import AgentWorkspace from './components/agents/AgentWorkspace'
import HistoryView from './components/views/HistoryView'

const RISK_OPTIONS = [
  { value: '稳健型', hint: '优先控制回撤' },
  { value: '平衡型', hint: '收益与风险兼顾' },
  { value: '进取型', hint: '接受更大波动' },
]

const SUGGESTIONS = [
  '市场环境怎么样',
  '分析一下贵州茅台',
  '沪深300ETF 近期走势如何',
  '中概互联板块现在怎么看',
]

const ORBIT_NODES = [
  { key: 'market', label: '市', name: '行情', className: 'n1' },
  { key: 'news', label: '闻', name: '事件', className: 'n2' },
  { key: 'fund', label: '财', name: '财务', className: 'n3' },
  { key: 'macro', label: '宏', name: '宏观', className: 'n4' },
]

/** 空态：一句话说清价值，右侧用四路分析师关系图代替装饰。 */
const Hero = ({ onPick }) => (
  <section className="hero fade-in">
    <div className="hero-copy">
      <div className="hero-kicker">AI 投研工作台</div>
      <h1 className="hero-title">
        让每个判断<br />
        <em>都有据可循</em>
      </h1>
      <p className="hero-desc">
        四路分析师并行取证，多空双方当面辩论，裁判先盲判再裁决。
        每个结论都能追溯到原始数据，而不是一句凭感觉的涨跌。
      </p>
      <div className="hero-suggests">
        {SUGGESTIONS.map((suggestion) => (
          <button key={suggestion} className="suggest-chip" onClick={() => onPick(suggestion)}>
            {suggestion}
          </button>
        ))}
      </div>
    </div>

    <div className="hero-orbit" aria-hidden="true">
      <div className="orbit-ring r1" />
      <div className="orbit-ring r2" />
      <div className="orbit-ring r3" />
      <div className="orbit-core">研</div>
      {ORBIT_NODES.map((node) => (
        <div key={node.key} className={`orbit-node ${node.className}`}>
          <span>{node.label}</span>
          <small>{node.name}</small>
        </div>
      ))}
    </div>
  </section>
)

function App() {
  const [view, setView] = useState('research') // research | history
  const [query, setQuery] = useState(() => {
    try {
      return localStorage.getItem('aii.draft') || ''
    } catch {
      return ''
    }
  })
  const [riskPreference, setRiskPreference] = useState(() => {
    try {
      return localStorage.getItem('aii.risk') || '稳健型'
    } catch {
      return '稳健型'
    }
  })
  const [submitting, setSubmitting] = useState(false)
  const [autoFollow, setAutoFollow] = useState(true)
  const autoFollowRef = useRef(true)
  const inputRef = useRef(null)
  const stream = useAgentStream()

  useEffect(() => {
    const element = inputRef.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 132)}px`
  }, [query, view])

  useEffect(() => {
    try {
      if (query) localStorage.setItem('aii.draft', query)
      else localStorage.removeItem('aii.draft')
    } catch {
      /* 隐私模式下忽略 */
    }
  }, [query])

  useEffect(() => {
    try {
      localStorage.setItem('aii.risk', riskPreference)
    } catch {
      /* 隐私模式下忽略 */
    }
  }, [riskPreference])

  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        if (view !== 'research') setView('research')
        window.setTimeout(() => inputRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [view])

  const {
    phase, orchestrator, agents, agentOrder, finalAnswer, evidence, debateTurns,
    verdict, verification, theses, phases, error, recoveredByPolling,
  } = stream

  const streaming = phase === 'researching' || phase === 'orchestrating' || phase === 'summarizing'
  const disabled = submitting || streaming

  useEffect(() => {
    if (!streaming || !autoFollowRef.current) return
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' })
  }, [streaming, phase, finalAnswer, agents, orchestrator.thoughts.length])

  // 研究完成时把视线带到研报开头，而不是停在报告末尾。
  useEffect(() => {
    if (phase !== 'done' || !autoFollowRef.current) return undefined
    const timer = window.setTimeout(() => {
      document.getElementById('research-report')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 160)
    return () => window.clearTimeout(timer)
  }, [phase])

  useEffect(() => {
    if (!streaming) return undefined
    const handleScroll = () => {
      const distanceToBottom = document.documentElement.scrollHeight - window.innerHeight - window.scrollY
      const follow = distanceToBottom < 240
      autoFollowRef.current = follow
      setAutoFollow(follow)
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [streaming])

  const handleSubmit = async (event) => {
    event?.preventDefault()
    const text = query.trim()
    if (!text || submitting || streaming) return
    setSubmitting(true)
    autoFollowRef.current = true
    setAutoFollow(true)
    try {
      const started = await stream.start(text, { riskPreference })
      if (started) setQuery('')
    } finally {
      setSubmitting(false)
    }
  }

  const handleNewChat = () => {
    setQuery('')
    setView('research')
    autoFollowRef.current = true
    setAutoFollow(true)
    stream.reset()
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }

  const pickSuggestion = (suggestion) => {
    setView('research')
    setQuery(suggestion)
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }

  const runningAgents = agentOrder.filter((name) => (
    ['waiting', 'thinking', 'tooling'].includes(agents[name]?.status)
  )).length

  const liveHint = phase === 'orchestrating'
    ? '研究主管正在拆解问题…'
    : phase === 'researching'
      ? (runningAgents > 0 ? `${runningAgents} 位分析师正在取证…` : '分析师正在汇总证据…')
      : phase === 'summarizing'
        ? '正在撰写研报…'
        : ''

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-seal">研</div>
          <div className="brand-text">
            <div className="brand-name">AI 投资研究</div>
            <div className="brand-sub">MULTI-AGENT RESEARCH</div>
          </div>
        </div>
        <nav className="topnav" aria-label="主导航">
          <button
            className={`nav-btn ${view === 'research' ? 'active' : ''}`}
            onClick={() => { setView('research'); stream.reset() }}
          >
            <Sparkles size={14} /> 新对话
          </button>
          <button
            className={`nav-btn ${view === 'history' ? 'active' : ''}`}
            onClick={() => setView('history')}
          >
            <History size={14} /> 历史记录
          </button>
        </nav>
      </header>

      <main className="main-area">
        {view === 'history' ? (
          <HistoryView onBack={() => setView('research')} />
        ) : (
          <>
            {phase === 'idle' && <Hero onPick={pickSuggestion} />}

            {phase !== 'idle' && (
              <AgentWorkspace
                phase={phase}
                orchestrator={orchestrator}
                agents={agents}
                agentOrder={agentOrder}
                finalAnswer={finalAnswer}
                evidence={evidence}
                debateTurns={debateTurns}
                verdict={verdict}
                verification={verification}
                theses={theses}
                phases={phases}
                error={error}
                recoveredByPolling={recoveredByPolling}
              />
            )}

            {streaming && !autoFollow && (
              <button
                type="button"
                className="follow-progress-button"
                onClick={() => {
                  autoFollowRef.current = true
                  setAutoFollow(true)
                  window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' })
                }}
              >
                <ArrowUp size={13} />
                回到当前进度
              </button>
            )}

            {(phase === 'done' || phase === 'failed') && (
              <div className="new-chat-bar">
                <button onClick={handleNewChat} className="back-btn">
                  <Plus size={14} /> 开始新对话
                </button>
              </div>
            )}
          </>
        )}
      </main>

      {view === 'research' && (
        <footer className="console-dock">
          <section className="console">
            <form className="console-form" onSubmit={handleSubmit}>
              <div className="console-input-wrap">
                <span className="console-prompt">▍</span>
                <textarea
                  ref={inputRef}
                  className="console-input"
                  value={query}
                  rows={1}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                      event.preventDefault()
                      handleSubmit()
                    }
                  }}
                  placeholder={streaming ? '研究进行中，可先输入下一个问题…' : '输入你想研究的问题，如：分析一下贵州茅台'}
                  aria-label="研究问题"
                />
              </div>
              <div className="risk-group" role="group" aria-label="风险偏好">
                {RISK_OPTIONS.map((option) => (
                  <button
                    type="button"
                    key={option.value}
                    className={`risk-pill ${riskPreference === option.value ? 'active' : ''}`}
                    onClick={() => setRiskPreference(option.value)}
                    title={option.hint}
                  >
                    {option.value}
                  </button>
                ))}
              </div>
              <button type="submit" className="run-btn" disabled={!query.trim() || disabled}>
                <Sparkles size={15} />
                {submitting ? '提交中…' : '开始研究'}
              </button>
            </form>
            <div className={`console-hint ${liveHint ? 'is-live' : ''}`} aria-live="polite">
              {liveHint || (phase === 'done'
                ? '研究已完成，可以继续追问或换个角度'
                : '四路分析师并行取证 · 多空辩论 · 盲判裁决 · 质检归档')}
              {!liveHint && <span className="hint-shortcut">⌘K 聚焦</span>}
            </div>
          </section>
        </footer>
      )}
    </div>
  )
}

export default App
