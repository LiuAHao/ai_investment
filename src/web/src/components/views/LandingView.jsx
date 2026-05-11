import React from 'react';

const AGENTS = [
  { id: 'context_loader', name: 'ContextLoader', desc: '加载会话上下文' },
  { id: 'router', name: 'RouterAgent', desc: '识别意图与资产' },
  { id: 'asset_resolver', name: 'AssetResolver', desc: '解析资产信息' },
  { id: 'planner', name: 'PlannerAgent', desc: '动态规划分析任务' },
  { id: 'tool_executor', name: 'ToolExecutor', desc: '并行执行工具调用' },
  { id: 'evidence_agent', name: 'EvidenceAgent', desc: '整理证据池' },
  { id: 'answer_draft', name: 'AnswerDraftAgent', desc: '生成分析草稿' },
  { id: 'critic', name: 'CriticAgent', desc: '事实与逻辑校验' },
  { id: 'compliance', name: 'ComplianceAgent', desc: '合规校验' },
  { id: 'answer_composer', name: 'AnswerComposer', desc: '生成最终结论' },
];

const FEATURES = [
  { icon: '◉', title: '过程可视化', desc: '实时观察每个 Agent 的工作状态, 工具调用、证据收集、风险校验全程透明' },
  { icon: '◎', title: '证据链追溯', desc: '每条结论都有明确的数据来源和置信度, 知其然更知其所以然' },
  { icon: '◈', title: '多轮追问', desc: '围绕同一主题持续追问, 形成无限迭代的研究线程, 深挖到底' },
  { icon: '◇', title: '合规分析', desc: '内置 Critic 校验和合规审查, 确保分析严谨、表述合规' },
];

const LandingView = ({ currentUser, onNavigate, onLogout }) => {
  return (
    <div style={{ minHeight: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header className="v2-header">
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }} onClick={() => onNavigate('home')}>
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <rect width="28" height="28" rx="6" fill="url(#lg)" />
              <path d="M8 20V8l6 6 6-6v12" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              <defs>
                <linearGradient id="lg" x1="0" y1="0" x2="28" y2="28">
                  <stop stopColor="#dc2626" />
                  <stop offset="1" stopColor="#f97316" />
                </linearGradient>
              </defs>
            </svg>
            <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: '-0.01em' }}>AI 投资研究</span>
          </div>

          <nav style={{ display: 'flex', gap: 4 }}>
            {[
              ['home', '首页'],
              ['research', '研究'],
              ['history', '历史'],
              ['settings', '设置'],
            ].map(([key, label]) => (
              <button
                key={key}
                onClick={() => onNavigate(key)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 500,
                  color: key === 'home' ? 'var(--text)' : 'var(--text3)',
                  background: key === 'home' ? 'rgba(220, 38, 38, 0.12)' : 'transparent',
                }}
              >
                {label}
              </button>
            ))}
          </nav>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {currentUser ? (
              <>
                <span style={{ fontSize: 13, color: 'var(--text2)' }}>
                  {currentUser.nickname || currentUser.username}
                </span>
                <button
                  onClick={onLogout}
                  style={{
                    padding: '6px 16px',
                    borderRadius: 6,
                    fontSize: 13,
                    color: 'var(--text2)',
                    border: '1px solid var(--border)',
                  }}
                >
                  退出
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => onNavigate('login')}
                  style={{
                    padding: '6px 16px',
                    borderRadius: 6,
                    fontSize: 13,
                    color: 'var(--text2)',
                    border: '1px solid var(--border)',
                  }}
                >
                  登录
                </button>
                <button
                  onClick={() => onNavigate('research')}
                  style={{
                    padding: '6px 16px',
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 600,
                    background: 'linear-gradient(135deg, var(--red), var(--orange))',
                    color: '#fff',
                  }}
                >
                  开始研究
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Page content */}
      <div style={{ flex: 1, maxWidth: 1200, margin: '0 auto', padding: '32px 24px 80px', width: '100%' }}>
        {/* Hero */}
        <div style={{ textAlign: 'center', padding: '80px 0 64px' }}>
          <div style={{
            display: 'inline-block',
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: 'var(--red)',
            background: 'rgba(220, 38, 38, 0.1)',
            border: '1px solid rgba(220, 38, 38, 0.2)',
            borderRadius: 20,
            padding: '4px 14px',
            marginBottom: 24,
          }}>
            V2 · 过程可视化
          </div>
          <h1 style={{
            fontSize: 'clamp(36px, 6vw, 56px)',
            fontWeight: 800,
            letterSpacing: '-0.03em',
            lineHeight: 1.1,
            marginBottom: 16,
            background: 'linear-gradient(135deg, var(--text), var(--text2))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}>
            AI 投资研究 Agent
          </h1>
          <p style={{
            fontSize: 18,
            color: 'var(--text2)',
            maxWidth: 500,
            margin: '0 auto 36px',
            lineHeight: 1.6,
          }}>
            让每一次分析都有过程、有证据、有风险边界
          </p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
            <button
              onClick={() => onNavigate('research')}
              style={{
                padding: '12px 32px',
                borderRadius: 8,
                fontSize: 15,
                fontWeight: 600,
                background: 'linear-gradient(135deg, var(--red), var(--orange))',
                color: '#fff',
              }}
            >
              开始研究 →
            </button>
            <button
              onClick={() => onNavigate(currentUser ? 'research' : 'login')}
              style={{
                padding: '12px 32px',
                borderRadius: 8,
                fontSize: 15,
                background: 'var(--card)',
                color: 'var(--text2)',
                border: '1px solid var(--border)',
              }}
            >
              {currentUser ? '进入工作台' : '注册 / 登录'}
            </button>
          </div>
        </div>

        {/* Features */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 20,
          marginBottom: 64,
        }}>
          {FEATURES.map((f, i) => (
            <div key={i} style={{
              background: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: '28px 24px',
            }}>
              <div style={{ fontSize: 28, color: 'var(--red)', marginBottom: 16 }}>{f.icon}</div>
              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>{f.title}</h3>
              <p style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.6 }}>{f.desc}</p>
            </div>
          ))}
        </div>

        {/* Agent Grid */}
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 24, letterSpacing: '-0.02em' }}>
          10 个 Agent 协同工作
        </h2>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: 12,
          marginBottom: 48,
        }}>
          {AGENTS.map((a, i) => (
            <div key={a.id} style={{
              background: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '12px 16px',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
            }}>
              <span style={{ fontSize: 11, fontFamily: 'ui-monospace, monospace', color: 'var(--red)', fontWeight: 600 }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{a.name}</span>
              <span style={{ fontSize: 12, color: 'var(--text3)' }}>{a.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default LandingView;
