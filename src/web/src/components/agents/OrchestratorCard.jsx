import React, { useState } from 'react'
import { Brain, ChevronDown, CircleDashed } from 'lucide-react'
import { agentMeta } from '../../utils/format'

/**
 * 研究主管：只露出"正在判断"和最终调度结果，原始思考默认收起。
 */
const OrchestratorCard = ({ thoughts = [], plan, status }) => {
  const [showThoughts, setShowThoughts] = useState(false)
  const active = status === 'orchestrating'
  const hasPlan = Array.isArray(plan) && plan.length > 0

  return (
    <section className="orchestrator-card fade-in">
      <div className="orch-head">
        <div className="orch-avatar av-orch">主</div>
        <div>
          <div className="orch-title">研究主管</div>
          <div className="orch-role">拆解问题 · 调度分析师</div>
        </div>
        <div className="orch-status">
          {active ? (
            <span className="agent-status st-thinking">
              <span className="loading-dots">思考中</span>
            </span>
          ) : hasPlan ? (
            <span className="agent-status st-done">已分工</span>
          ) : null}
        </div>
      </div>

      <div className="orch-body">
        {hasPlan ? (
          <div className="orch-plan">
            {plan.map((name) => {
              const meta = agentMeta(name)
              return (
                <span className="plan-chip" key={name}>
                  <span className="plan-chip-avatar">{meta.short}</span>
                  <b>{meta.title}</b>
                </span>
              )
            })}
          </div>
        ) : (
          <span className="orch-waiting">
            <CircleDashed size={14} className={active ? 'spin' : ''} />
            {active ? '正在判断问题类型与所需数据…' : '等待研究任务'}
          </span>
        )}

        {thoughts.length > 0 && (
          <div className="orch-thoughts">
            <button
              type="button"
              className={`disclosure ${showThoughts ? 'is-open' : ''}`}
              onClick={() => setShowThoughts((value) => !value)}
            >
              <Brain size={13} />
              {showThoughts ? '收起调度思路' : `查看调度思路 · ${thoughts.length} 条`}
              <ChevronDown size={12} />
            </button>
            {showThoughts && (
              <div style={{ marginTop: 8 }}>
                {thoughts.map((thought, index) => (
                  <div key={index} className="item fade-in">
                    <span className="item-icon"><Brain size={12} /></span>
                    <div className="item-body">{thought}</div>
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

export default OrchestratorCard
