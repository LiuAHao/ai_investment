import React from 'react'

const ACTION_LABEL = {
  attack: '攻击',
  defend: '防守',
  revise: '修正',
  concede: '让步',
}

const ACTION_COLOR = {
  attack: 'var(--red)',
  defend: 'var(--text2)',
  revise: 'var(--gold)',
  concede: 'var(--green, #2f9e44)',
}

const ATTACK_LABEL = {
  evidence_gap: '证据缺口',
  logic: '逻辑断裂',
  caliber: '口径问题',
  timing: '时效错配',
  base_rate: '忽略基准',
  priced_in: '已被定价',
}

const thesisMeta = (theses, side) => {
  const thesis = theses?.[side]
  if (!thesis) return null
  const count = thesis.claim_count ?? (thesis.claims ? thesis.claims.length : 0)
  const confidence = typeof thesis.confidence === 'number' ? thesis.confidence : null
  return { count, confidence }
}

/**
 * 结构化辩论：按 target_claim_id 配对成“论据 → 攻击 → 回应”线程。
 */
const DebateTimeline = ({
  turns = [],
  theses = {},
  active = false,
  skippedLabel = '',
  reason = '',
  controversy = null,
}) => {
  const bull = thesisMeta(theses, 'bull')
  const bear = thesisMeta(theses, 'bear')

  if (!turns.length && !bull && !bear) {
    if (!active) return null
    return (
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <div className="card-avatar av-sum">辩</div>
          <div className="card-name">
            多空辩论
            <span style={{ fontSize: 11, color: 'var(--text3)', marginLeft: 8 }}>
              {skippedLabel ? '未启用' : '准备中'}
            </span>
          </div>
        </div>
        <div className="card-body" style={{ fontSize: 12, color: 'var(--text3)' }}>
          {reason || skippedLabel || '多空论点生成后，这里会按“论据 → 攻击 → 回应”成对展示。'}
        </div>
      </div>
    )
  }

  const rounds = [...new Set(turns.map((turn) => turn.round || 1))].sort()
  const threads = []
  const threadMap = new Map()
  turns.forEach((turn, index) => {
    const key = turn.target_claim_id || `_turn_${index}`
    if (!threadMap.has(key)) {
      const thread = { key, target: turn.target_claim_id || '', turns: [] }
      threadMap.set(key, thread)
      threads.push(thread)
    }
    threadMap.get(key).turns.push(turn)
  })
  threads.forEach((thread) => {
    thread.turns.sort((a, b) => (a.round || 1) - (b.round || 1))
  })

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="card-head">
        <div className="card-avatar av-sum">辩</div>
        <div className="card-name">
          多空辩论
          <span style={{ fontSize: 11, color: 'var(--text3)', marginLeft: 8 }}>
            {turns.length} 个动作 · {rounds.length} 轮
            {controversy?.score != null ? ` · 争议度 ${(controversy.score * 100).toFixed(0)}%` : ''}
          </span>
        </div>
        {bull && (
          <span className="agent-status" style={{ color: '#22c55e', border: '1px solid rgba(34,197,94,.35)' }}>
            多方 {bull.count} 条{bull.confidence !== null ? ` · ${(bull.confidence * 100).toFixed(0)}%` : ''}
          </span>
        )}
        {bear && (
          <span className="agent-status" style={{ color: '#ef4444', border: '1px solid rgba(239,68,68,.35)' }}>
            空方 {bear.count} 条{bear.confidence !== null ? ` · ${(bear.confidence * 100).toFixed(0)}%` : ''}
          </span>
        )}
      </div>
      <div className="card-body">
        {!turns.length && (
          <div style={{ fontSize: 12, color: 'var(--text3)' }}>
            {reason || skippedLabel || '本次未产生辩论动作'}
          </div>
        )}
        {threads.map((thread) => (
          <div
            key={thread.key}
            style={{
              border: '1px solid var(--line)',
              borderRadius: 8,
              padding: '8px 10px',
              marginBottom: 10,
            }}
          >
            {thread.target && (
              <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>
                论题 {thread.target}
              </div>
            )}
            {thread.turns.map((turn, index) => (
              <div key={`${thread.key}-${index}`} className="item" style={{ alignItems: 'flex-start' }}>
                <span
                  className="item-icon"
                  style={{
                    fontSize: 11,
                    minWidth: 40,
                    color: turn.side === 'bull' ? '#22c55e' : '#ef4444',
                  }}
                >
                  {turn.side === 'bull' ? '多方' : '空方'}
                </span>
                <div className="item-body">
                  <div style={{ fontSize: 11, marginBottom: 3 }}>
                    <span style={{ color: 'var(--text3)' }}>R{turn.round || 1} · </span>
                    <span style={{ color: ACTION_COLOR[turn.action] || 'var(--text2)', fontWeight: 600 }}>
                      {ACTION_LABEL[turn.action] || turn.action}
                    </span>
                    {turn.attack_type && (
                      <span style={{ color: 'var(--text3)', marginLeft: 6 }}>
                        {ATTACK_LABEL[turn.attack_type] || turn.attack_type}
                      </span>
                    )}
                    {turn.cited_evidence_ids?.length > 0 && (
                      <span style={{ color: 'var(--text3)', marginLeft: 6 }}>
                        引用 {turn.cited_evidence_ids.join(', ')}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, lineHeight: 1.5 }}>{turn.argument}</div>
                  {turn.concession && (
                    <div style={{ fontSize: 11, color: 'var(--gold)', marginTop: 3 }}>
                      让步：{turn.concession}
                    </div>
                  )}
                  {turn.no_concession_reason && (
                    <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 3 }}>
                      零让步说明：{turn.no_concession_reason}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export default DebateTimeline
