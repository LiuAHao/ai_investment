import React, { useState } from 'react'
import { Scale, ShieldAlert, ShieldCheck } from 'lucide-react'
import Markdown from '../common/Markdown'
import { localizeHorizon } from '../../utils/format'

const STANCE_META = {
  bullish: { label: '看多', className: 'is-bull' },
  bearish: { label: '看空', className: 'is-bear' },
  neutral: { label: '中性', className: 'is-neutral' },
}

const RESOLVABLE_LABEL = {
  yes: '可解决',
  no: '不可解决',
  needs_data: '需要数据',
}

/**
 * 投资裁决：盲判 → 终判、分歧矩阵、仓位区间、观察项与质检。
 */
const VerdictPanel = ({ verdict, verification, active = false }) => {
  const [showIssues, setShowIssues] = useState(false)

  if (!verdict) {
    if (!active) return null
    return (
      <section className="card">
        <header className="card-head">
          <div className="card-avatar av-summary"><Scale size={17} /></div>
          <div className="card-name">
            投资裁决
            <small>裁决中</small>
          </div>
        </header>
        <div className="card-body" style={{ fontSize: 12, color: 'var(--text3)' }}>
          裁判正在先做盲判，再结合多空辩论给出终判…
        </div>
      </section>
    )
  }

  const stance = STANCE_META[verdict.stance] || STANCE_META.neutral
  const blindStance = STANCE_META[verdict.blind_stance] || STANCE_META.neutral
  const conviction = Number(verdict.conviction || 0)
  const blindConviction = Number(verdict.blind_conviction || 0)
  const changed = Boolean(verdict.blind_stance && verdict.blind_stance !== verdict.stance)
  const delta = conviction - blindConviction

  const disagreements = verdict.disagreement_map || []
  const falsifiers = verdict.falsifiers_to_watch || []
  const mindChangers = verdict.what_would_change_my_mind || []
  const issues = verification?.issues || []

  return (
    <section className="card">
      <header className="card-head">
        <div className="card-avatar av-summary"><Scale size={17} /></div>
        <div className="card-name">
          投资裁决
          <small>盲判 · 辩论 · 终判</small>
        </div>
        {verification?.passed === false && (
          <span className="agent-status st-failed">
            <ShieldAlert size={11} />
            质检未通过
          </span>
        )}
      </header>

      <div className="card-body">
        <div className="verdict-hero">
          <div>
            <div className={`verdict-stance ${stance.className}`}>{stance.label}</div>
            <div className="verdict-sub">最终方向</div>
          </div>
          <div className="confidence-block">
            <div className="verdict-sub">置信度 {(conviction * 100).toFixed(0)}%</div>
            <div className="confidence-track">
              <div className="confidence-fill" style={{ width: `${Math.min(100, conviction * 100)}%` }} />
            </div>
          </div>
          {verdict.blind_stance && (
            <>
              <span className="verdict-arrow">← 盲判 {blindStance.label} {(blindConviction * 100).toFixed(0)}%</span>
              <span className="verdict-sub">
                {changed ? '辩论改变了方向' : '方向未变'}
                {Number.isFinite(delta) && Math.abs(delta) >= 0.01
                  ? ` · 置信度 ${delta > 0 ? '+' : ''}${(delta * 100).toFixed(0)}pt`
                  : ''}
              </span>
            </>
          )}
        </div>

        {verdict.blind_stance && (
          <div className="report-section">
            <div className="report-label">盲判 → 终判</div>
            <div className="verdict-inline">
              <span>盲判：{blindStance.label} {(blindConviction * 100).toFixed(0)}%</span>
              <span className="verdict-arrow">→</span>
              <span style={{ color: 'var(--text)' }}>终判：{stance.label} {(conviction * 100).toFixed(0)}%</span>
            </div>
            {verdict.revision_reason && (
              <div className="report-content" style={{ marginTop: 7, fontSize: 12.5 }}>
                修订说明：{verdict.revision_reason}
              </div>
            )}
          </div>
        )}

        {(verdict.key_drivers || []).length > 0 && (
          <div className="report-section">
            <div className="report-label">核心驱动</div>
            <div className="report-points">
              {verdict.key_drivers.map((driver, index) => (
                <div key={index} className="report-point"><Markdown text={`- ${driver}`} /></div>
              ))}
            </div>
          </div>
        )}

        {disagreements.length > 0 && (
          <div className="report-section">
            <div className="report-label">分歧矩阵</div>
            <div className="table-wrap">
              <table className="data-table verdict-table">
                <thead>
                  <tr>
                    <th>分歧点</th>
                    <th>多方</th>
                    <th>空方</th>
                    <th>性质</th>
                    <th>裁决</th>
                  </tr>
                </thead>
                <tbody>
                  {disagreements.map((item, index) => (
                    <tr key={index}>
                      <td>{item.topic}</td>
                      <td style={{ color: 'var(--green)' }}>{item.bull_view || '—'}</td>
                      <td style={{ color: 'var(--red)' }}>{item.bear_view || '—'}</td>
                      <td>{RESOLVABLE_LABEL[item.resolvable] || item.resolvable}</td>
                      <td>{item.resolution || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {(verdict.position_hint || verdict.time_frame) && (
          <div className="report-section">
            <div className="report-label">仓位与时间框架</div>
            <div className="verdict-inline">
              {verdict.position_hint && (
                <span>仓位区间：<span style={{ color: 'var(--text)' }}>{verdict.position_hint}</span></span>
              )}
              {verdict.time_frame && (
                <span>判断有效期：<span style={{ color: 'var(--text)' }}>{localizeHorizon(verdict.time_frame)}</span></span>
              )}
            </div>
          </div>
        )}

        {(falsifiers.length > 0 || mindChangers.length > 0) && (
          <div className="report-section">
            <div className="report-label">后续观察</div>
            <div className="report-grid">
              {falsifiers.length > 0 && (
                <div className="report-col bear">
                  <div className="report-col-title">否证信号</div>
                  <div className="report-points">
                    {falsifiers.map((item, index) => (
                      <div key={index} className="report-point"><Markdown text={`- ${item}`} /></div>
                    ))}
                  </div>
                </div>
              )}
              {mindChangers.length > 0 && (
                <div className="report-col bull">
                  <div className="report-col-title">改变判断的条件</div>
                  <div className="report-points">
                    {mindChangers.map((item, index) => (
                      <div key={index} className="report-point"><Markdown text={`- ${item}`} /></div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {(verdict.confidence_calibration || verification) && (
          <div className="report-section">
            <div className="report-label">置信度校准</div>
            {verdict.confidence_calibration && (
              <div className="report-content" style={{ fontSize: 12.5 }}>
                {verdict.confidence_calibration}
              </div>
            )}
            {verification && (
              <div style={{ marginTop: 8, fontSize: 12 }}>
                <span style={{ color: verification.passed ? 'var(--green)' : 'var(--red)', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  {verification.passed ? <ShieldCheck size={13} /> : <ShieldAlert size={13} />}
                  质检：{verification.passed ? '通过' : '未通过'}
                </span>
                {issues.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowIssues((value) => !value)}
                    style={{
                      marginLeft: 8, background: 'transparent', border: 'none',
                      color: 'var(--text3)', fontSize: 11, cursor: 'pointer',
                    }}
                  >
                    {showIssues ? '收起' : `查看 ${issues.length} 条`}
                  </button>
                )}
              </div>
            )}
            {showIssues && issues.length > 0 && (
              <div style={{ marginTop: 6 }}>
                {issues.map((issue, index) => (
                  <div key={index} style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>
                    [{issue.kind}] {issue.detail}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}

export default VerdictPanel
