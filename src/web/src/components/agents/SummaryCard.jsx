import React from 'react'
import Markdown from '../common/Markdown'

/**
 * SummaryAgent 总结分析卡片（研报版式）
 * 展示：总体判断 / 关键判断 / 推理过程 / 主要风险 / 信息缺口 / 时间框架 / 合规声明
 * 所有 Markdown 内容均渲染
 */
const SummaryCard = ({ answer }) => {
  if (!answer) return null
  const keyPoints = answer.key_points || []
  const risks = answer.risks || []
  const gaps = answer.information_gaps || []
  const disclaimer = answer.compliance_disclaimer

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
          {answer.reasoning && (
            <div className="report-section">
              <div className="report-label">推理过程</div>
              <div className="report-content"><Markdown text={answer.reasoning} /></div>
            </div>
          )}
          {risks.length > 0 && (
            <div className="report-section">
              <div className="report-label">主要风险</div>
              <div>
                {risks.map((risk, i) => (
                  <div key={i} style={{ marginBottom: 8 }}>
                    <Markdown text={`- ${risk}`} />
                  </div>
                ))}
              </div>
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
