import React, { useState } from 'react'
import { AlertTriangle, Check, Copy, FileText } from 'lucide-react'
import Markdown from '../common/Markdown'
import { cleanSource, localizeHorizon } from '../../utils/format'

const RISK_LEVEL = {
  high: { label: '高', className: 'is-bad' },
  medium: { label: '中', className: 'is-warn' },
  low: { label: '低', className: 'is-good' },
}

const RISK_LABEL = { high: '高', medium: '中', low: '低' }

const buildReportText = (answer) => {
  const parts = []
  if (answer.summary) parts.push(`## 总体判断\n${answer.summary}`)
  if (answer.key_points?.length) parts.push(`## 关键判断\n${answer.key_points.map((point) => `- ${point}`).join('\n')}`)
  if (answer.reasoning) parts.push(`## 推理过程\n${answer.reasoning}`)
  if (answer.risks?.length) parts.push(`## 主要风险\n${answer.risks.map((risk) => `- ${risk}`).join('\n')}`)
  if (answer.information_gaps?.length) parts.push(`## 信息缺口\n${answer.information_gaps.map((gap) => `- ${gap}`).join('\n')}`)
  return parts.join('\n\n')
}

/**
 * 投研报告：结论优先、证据可追溯，技术字段默认折叠。
 */
const SummaryCard = ({ answer }) => {
  const [copied, setCopied] = useState(false)

  if (!answer) return null

  const keyPoints = answer.key_points || []
  const bullCases = answer.bull_cases || []
  const bearCases = answer.bear_cases || []
  const risks = answer.risks || []
  const structuredRisks = answer.structured_risks || []
  const gaps = answer.information_gaps || []
  const disclaimer = answer.compliance_disclaimer
  const timeFrame = localizeHorizon(answer.time_frame)
  const confidence = typeof answer.confidence === 'number' ? answer.confidence : null
  const summaryText = typeof answer.summary === 'string' ? answer.summary.trim() : ''
  const summaryFailed = /^(模型调用失败|综合分析过程中发生错误|研究过程中发生错误)|Authentication Fails|invalid_request_error/i.test(summaryText)
  const confLabel = confidence === null ? null : (confidence >= 0.8 ? '高' : (confidence >= 0.6 ? '中' : '低'))
  const confTone = confidence === null ? '' : (confidence >= 0.8 ? 'st-done' : (confidence >= 0.6 ? 'st-thinking' : 'st-failed'))

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(buildReportText(answer))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section className="card" id="research-report">
      <header className="card-head">
        <div className="card-avatar av-summary"><FileText size={16} /></div>
        <div className="card-name">
          投研报告
          <small>综合裁决 · 可追溯</small>
        </div>
        {confidence !== null && (
          <span className={`agent-status ${confTone}`} title={`置信度 ${(confidence * 100).toFixed(0)}%`}>
            可信度 {confLabel} · {(confidence * 100).toFixed(0)}%
          </span>
        )}
        <button
          type="button"
          className="disclosure"
          onClick={handleCopy}
          aria-label="复制研报正文"
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? '已复制' : '复制'}
        </button>
      </header>

      <div className="card-body">
        {summaryFailed && (
          <div className="report-failure">
            <AlertTriangle size={15} />
            <span>总结阶段出现异常，以下内容为后端兜底文本，本轮结论不建议直接作为研究依据。</span>
          </div>
        )}

        {answer.summary && (
          <div className="report-section">
            <div className="report-label">总体判断</div>
            <div className="report-callout">
              <Markdown text={answer.summary} />
            </div>
          </div>
        )}

        {keyPoints.length > 0 && (
          <div className="report-section">
            <div className="report-label">关键判断</div>
            <div className="report-points">
              {keyPoints.map((point, index) => (
                <div key={index} className="report-point"><Markdown text={`- ${point}`} /></div>
              ))}
            </div>
          </div>
        )}

        {(bullCases.length > 0 || bearCases.length > 0) && (
          <div className="report-section">
            <div className="report-label">多空论据</div>
            <div className="report-grid">
              {bullCases.length > 0 && (
                <div className="report-col bull">
                  <div className="report-col-title">看多论据</div>
                  {bullCases.map((item, index) => {
                    const source = cleanSource(item.source)
                    return (
                      <div key={index} className="report-point">
                        <Markdown text={`- ${item.point || ''}`} />
                        <span className="report-source">
                          强度：{item.strength === 'high' ? '强' : item.strength === 'low' ? '弱' : '中'}
                          {source ? ` · ${source}` : ''}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
              {bearCases.length > 0 && (
                <div className="report-col bear">
                  <div className="report-col-title">看空论据</div>
                  {bearCases.map((item, index) => {
                    const source = cleanSource(item.source)
                    return (
                      <div key={index} className="report-point">
                        <Markdown text={`- ${item.point || ''}`} />
                        <span className="report-source">
                          强度：{item.strength === 'high' ? '强' : item.strength === 'low' ? '弱' : '中'}
                          {source ? ` · ${source}` : ''}
                        </span>
                      </div>
                    )
                  })}
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
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>类型</th>
                      <th>风险描述</th>
                      <th>概率</th>
                      <th>影响</th>
                      <th>已反映在价格</th>
                    </tr>
                  </thead>
                  <tbody>
                    {structuredRisks.map((risk, index) => {
                      const probability = RISK_LEVEL[risk.probability] || null
                      const impact = RISK_LEVEL[risk.impact] || null
                      return (
                        <tr key={index}>
                          <td>{risk.type || '其他'}</td>
                          <td>{risk.desc || ''}</td>
                          <td className={probability?.className}>{probability?.label || RISK_LABEL[risk.probability] || '—'}</td>
                          <td className={impact?.className}>{impact?.label || RISK_LABEL[risk.impact] || '—'}</td>
                          <td>{risk.priced_in === null || risk.priced_in === undefined ? '—' : (risk.priced_in ? '是' : '否')}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="report-points">
                {risks.map((risk, index) => (
                  <div key={index} className="report-point"><Markdown text={`- ${risk}`} /></div>
                ))}
              </div>
            )}
          </div>
        )}

        {gaps.length > 0 && (
          <div className="report-section">
            <div className="report-label">信息缺口</div>
            <div className="report-points">
              {gaps.map((gap, index) => (
                <div key={index} className="report-point"><Markdown text={`- ${gap}`} /></div>
              ))}
            </div>
          </div>
        )}

        {timeFrame && (
          <div className="report-section">
            <div className="report-label">时间框架</div>
            <div className="report-content">{timeFrame}</div>
          </div>
        )}

        {disclaimer && (
          <div className="compliance-banner">
            <AlertTriangle size={14} />
            <span>{disclaimer}</span>
          </div>
        )}
      </div>
    </section>
  )
}

export default SummaryCard
