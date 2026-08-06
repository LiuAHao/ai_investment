import React from 'react'
import Markdown from '../common/Markdown'

/**
 * SummaryAgent 总结分析卡片（研报版式）
 * 展示：总体判断 / 关键判断 / 多空论据 / 推理过程 / 主要风险(矩阵) / 信息缺口 / 时间框架 / 合规声明
 * 所有 Markdown 内容均渲染
 */

// 结构化风险表格样式
const riskThStyle = { padding: '6px 8px', fontSize: 12, color: 'var(--text2)', fontWeight: 600, borderBottom: '1px solid var(--line)', whiteSpace: 'nowrap' }
const riskTdStyle = { padding: '6px 8px', fontSize: 13, color: 'var(--text)', borderBottom: '1px solid rgba(0,0,0,0.03)', verticalAlign: 'top' }

const RiskBadge = ({ level }) => {
  const color = level === 'high' ? '#ef4444' : (level === 'low' ? '#22c55e' : '#eab308')
  const label = level === 'high' ? '高' : (level === 'low' ? '低' : '中')
  return (
    <span style={{ color, fontWeight: 600, whiteSpace: 'nowrap' }}>{label}</span>
  )
}

const SummaryCard = ({ answer }) => {
  if (!answer) return null
  const keyPoints = answer.key_points || []
  const bullCases = answer.bull_cases || []
  const bearCases = answer.bear_cases || []
  const risks = answer.risks || []
  const structuredRisks = answer.structured_risks || []
  const gaps = answer.information_gaps || []
  const disclaimer = answer.compliance_disclaimer
  const confidence = typeof answer.confidence === 'number' ? answer.confidence : null

  // 置信度分档
  const confLabel = confidence === null ? null : (confidence >= 0.8 ? '高可信' : (confidence >= 0.6 ? '中可信' : '低可信'))
  const confColor = confidence === null ? null : (confidence >= 0.8 ? '#22c55e' : (confidence >= 0.6 ? '#eab308' : '#ef4444'))

  return (
    <div className="card">
      <div className="card-head">
        <div className="card-avatar av-sum">研</div>
        <div className="card-name">
          SummaryAgent · 投研报告
          <small style={{ display: 'block', fontSize: 11, color: 'var(--text3)', fontWeight: 400, letterSpacing: '.12em', marginTop: 2 }}>
            FINAL RESEARCH REPORT
          </small>
        </div>
        {confidence !== null && (
          <span className="agent-status st-done" title={`置信度 ${(confidence * 100).toFixed(0)}%`}
            style={{ background: 'transparent', color: confColor, border: `1px solid ${confColor}`, fontWeight: 600 }}>
            可信度 {confLabel} · {(confidence * 100).toFixed(0)}%
          </span>
        )}
        <span className="agent-status st-done">已完成</span>
      </div>
      <div className="card-body">
        <div className="final-report">
          {answer.summary && (
            <div className="report-section">
              <div className="report-label">总体判断</div>
              <div className="report-content"><Markdown text={answer.summary} /></div>
            </div>
          )}
          {keyPoints.length > 0 && (
            <div className="report-section">
              <div className="report-label">关键判断</div>
              <div>
                {keyPoints.map((point, i) => (
                  <div key={i} style={{ marginBottom: 8 }}>
                    <Markdown text={`- ${point}`} />
                  </div>
                ))}
              </div>
            </div>
          )}
          {(bullCases.length > 0 || bearCases.length > 0) && (
            <div className="report-section">
              <div className="report-label">多空论据</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {bullCases.length > 0 && (
                  <div style={{ background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 8, padding: '10px 12px' }}>
                    <div style={{ fontSize: 12, color: '#22c55e', fontWeight: 600, marginBottom: 6 }}>看多论据</div>
                    {bullCases.map((c, i) => (
                      <div key={i} style={{ marginBottom: 6, fontSize: 13, lineHeight: 1.5 }}>
                        <Markdown text={`- ${c.point || ''}`} />
                        <small style={{ color: 'var(--text3)', fontSize: 11 }}>
                          {c.strength === 'high' ? '强' : c.strength === 'low' ? '弱' : '中'}
                          {c.source ? ` · ${c.source}` : ''}
                        </small>
                      </div>
                    ))}
                  </div>
                )}
                {bearCases.length > 0 && (
                  <div style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '10px 12px' }}>
                    <div style={{ fontSize: 12, color: '#ef4444', fontWeight: 600, marginBottom: 6 }}>看空论据</div>
                    {bearCases.map((c, i) => (
                      <div key={i} style={{ marginBottom: 6, fontSize: 13, lineHeight: 1.5 }}>
                        <Markdown text={`- ${c.point || ''}`} />
                        <small style={{ color: 'var(--text3)', fontSize: 11 }}>
                          {c.strength === 'high' ? '强' : c.strength === 'low' ? '弱' : '中'}
                          {c.source ? ` · ${c.source}` : ''}
                        </small>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
          {answer.reasoning && (
            <div className="report-section">
              <div className="report-label">推理过程</div>
              <div className="report-content"><Markdown text={answer.reasoning} /></div>
            </div>
          )}
          {(structuredRisks.length > 0 || risks.length > 0) && (
            <div className="report-section">
              <div className="report-label">主要风险</div>
              {structuredRisks.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ textAlign: 'left' }}>
                        <th style={riskThStyle}>类型</th>
                        <th style={riskThStyle}>风险描述</th>
                        <th style={riskThStyle}>概率</th>
                        <th style={riskThStyle}>影响</th>
                        <th style={riskThStyle}>已反映在价格</th>
                      </tr>
                    </thead>
                    <tbody>
                      {structuredRisks.map((r, i) => (
                        <tr key={i} style={{ borderTop: '1px solid var(--line)' }}>
                          <td style={riskTdStyle}>{r.type || '其他'}</td>
                          <td style={riskTdStyle}>{r.desc || ''}</td>
                          <td style={riskTdStyle}><RiskBadge level={r.probability} /></td>
                          <td style={riskTdStyle}><RiskBadge level={r.impact} /></td>
                          <td style={riskTdStyle}>{r.priced_in === null || r.priced_in === undefined ? '—' : (r.priced_in ? '是' : '否')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div>
                  {risks.map((risk, i) => (
                    <div key={i} style={{ marginBottom: 8 }}>
                      <Markdown text={`- ${risk}`} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {gaps.length > 0 && (
            <div className="report-section">
              <div className="report-label">信息缺口</div>
              <div>
                {gaps.map((gap, i) => (
                  <div key={i} style={{ marginBottom: 8 }}>
                    <Markdown text={`- ${gap}`} />
                  </div>
                ))}
              </div>
            </div>
          )}
          {answer.time_frame && (
            <div className="report-section">
              <div className="report-label">时间框架</div>
              <div className="report-content"><Markdown text={answer.time_frame} /></div>
            </div>
          )}
          {disclaimer && (
            <div className="compliance-banner">
              <span style={{ color: 'var(--gold)', fontSize: 16, flexShrink: 0 }}>⚠</span>
              <span>{disclaimer}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SummaryCard
