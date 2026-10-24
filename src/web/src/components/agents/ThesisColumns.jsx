import React from 'react'

const SIDE_META = {
  bull: { label: '多方', color: '#22c55e' },
  bear: { label: '空方', color: '#ef4444' },
}

/**
 * 多空建论双列：实时显示构建状态、核心主张、前 3 条论据。
 * theses[side] 来自 thesis_started / thesis_submitted / 历史快照。
 */
const ThesisColumns = ({ theses = {} }) => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
    {['bull', 'bear'].map((side) => {
      const thesis = theses?.[side]
      const meta = SIDE_META[side]
      const claims = thesis?.claims || []
      const count = thesis?.claim_count ?? claims.length
      const confidence = typeof thesis?.confidence === 'number'
        ? Math.round(thesis.confidence * 100)
        : null
      const running = thesis?.status === 'running'

      return (
        <div
          key={side}
          style={{
            border: '1px solid var(--line)',
            borderRadius: 8,
            padding: '10px 12px',
            background: 'rgba(255,255,255,.015)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: meta.color }}>{meta.label}</span>
            <span style={{ fontSize: 11, color: 'var(--text3)' }}>
              {running
                ? '构建中…'
                : (thesis ? `${count} 条${confidence !== null ? ` · ${confidence}%` : ''}` : '等待生成')}
            </span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.5, marginBottom: 6 }}>
            {thesis?.core_claim || (running ? '正在生成核心主张…' : '等待生成')}
          </div>
          {claims.slice(0, 3).map((claim, index) => (
            <div
              key={claim.claim_id || index}
              style={{ fontSize: 11, color: 'var(--text3)', lineHeight: 1.5, marginTop: 2 }}
            >
              · {claim.statement}
            </div>
          ))}
        </div>
      )
    })}
  </div>
)

export default ThesisColumns
