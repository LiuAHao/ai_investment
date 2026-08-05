import React, { useState } from 'react'
import { Sparkles, History } from 'lucide-react'
import { useAgentStream } from './hooks/useAgentStream'
import AgentWorkspace from './components/agents/AgentWorkspace'
import HistoryView from './components/views/HistoryView'

const RISK_OPTIONS = ['稳健型', '平衡型', '进取型']
const SUGGESTIONS = [
  '市场环境怎么样',
  '分析一下贵州茅台',
  '沪深300ETF 近期走势如何',
  '中概互联板块现在怎么看',
]

/** 空闲态品牌展示（内容区上方） */
const Hero = ({ onPick }) => (
  <section className="hero fade-in">
    <div className="hero-kicker">AI MULTI-AGENT INVESTMENT RESEARCH</div>
    <h1 className="hero-title">
      多智能体 <em>投研</em> 工作台
    </h1>
    <p className="hero-desc">
      输入一个投资问题，编排 Agent 会理解意图并按需调度
      市场行情、新闻舆情、知识库三路调研智能体并行研究，
      最后由总结 Agent 交叉验证、综合判断，输出结构化投研结论。
    </p>
    <div className="hero-suggests">
      {SUGGESTIONS.map((s) => (
        <button key={s} className="suggest-chip" onClick={() => onPick(s)}>
          {s}
        </button>
      ))}
    </div>
  </section>
)

function App() {
  const [view, setView] = useState('research') // research | history
  const [query, setQuery] = useState('')
  const [riskPreference, setRiskPreference] = useState('稳健型')
  const [submitting, setSubmitting] = useState(false)
  const stream = useAgentStream()

  const { phase, orchestrator, agents, agentOrder, finalAnswer, error } = stream

  const handleSubmit = async (e) => {
    e?.preventDefault()
    const text = query.trim()
    if (!text || submitting) return
    setSubmitting(true)
    try {
      await stream.start(text, { riskPreference })
    } finally {
      setSubmitting(false)
    }
  }

  const handleNewChat = () => {
    setQuery('')
    stream.reset()
  }

  const disabled = submitting || phase === 'researching' || phase === 'orchestrating' || phase === 'summarizing'

  return (
    <div className="app-shell">
      {/* 顶部标头 */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-seal">研</div>
          <div>
            <div className="brand-name">AI<b>投资研究</b></div>
            <div className="brand-sub">MULTI-AGENT INVESTMENT RESEARCH</div>
          </div>
        </div>
        <nav className="topnav">
          <button
            className={`nav-btn ${view === 'research' ? 'active' : ''}`}
            onClick={() => { setView('research'); stream.reset() }}
          >
            <Sparkles size={15} /> 新对话
          </button>
          <button
            className={`nav-btn ${view === 'history' ? 'active' : ''}`}
            onClick={() => setView('history')}
          >
            <History size={15} /> 历史记录
          </button>
        </nav>
      </header>

      {/* 主内容区 */}
      <main className="main-area">
        {view === 'history' ? (
          <HistoryView onBack={() => setView('research')} />
        ) : (
          <>
            {/* 空闲态品牌展示（上方） */}
            {phase === 'idle' && <Hero onPick={(s) => { setQuery(s); setView('research') }} />}

            {/* 研究流程 */}
            {phase !== 'idle' && (
              <AgentWorkspace
                phase={phase}
                orchestrator={orchestrator}
                agents={agents}
                agentOrder={agentOrder}
                finalAnswer={finalAnswer}
                error={error}
              />
            )}

            {(phase === 'done' || phase === 'failed') && (
              <div className="new-chat-bar">
                <button onClick={handleNewChat} className="back-btn">
                  ✦ 开始新对话
                </button>
              </div>
            )}
          </>
        )}
      </main>

      {/* 底部常驻输入 Dock */}
      {view === 'research' && (
        <footer className="console-dock">
          <section className="console">
            <form className="console-form" onSubmit={handleSubmit}>
              <div className="console-input-wrap">
                <span className="console-prompt">▍</span>
                <input
                  className="console-input"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="输入你想研究的问题，如：市场环境怎么样 / 分析一下贵州茅台"
                  disabled={disabled}
                />
              </div>
              <div className="risk-group">
                {RISK_OPTIONS.map((r) => (
                  <button
                    type="button"
                    key={r}
                    className={`risk-pill ${riskPreference === r ? 'active' : ''}`}
                    onClick={() => setRiskPreference(r)}
                  >
                    {r}
                  </button>
                ))}
              </div>
              <button type="submit" className="run-btn" disabled={!query.trim() || disabled}>
                <Sparkles size={16} />
                {submitting ? '研究中…' : '开始研究'}
              </button>
            </form>
            <div className="console-hint">
              编排 Agent 将按需调度市场 / 新闻 / 知识三路调研智能体并行研究，最终汇成投研报告
            </div>
          </section>
        </footer>
      )}
    </div>
  )
}

export default App
