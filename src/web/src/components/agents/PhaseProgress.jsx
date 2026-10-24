import React from 'react'
import { GitBranch } from 'lucide-react'
import { formatDuration } from '../../utils/format'

const PHASE_META = [
  { key: 'L0', label: '研究计划' },
  { key: 'L1', label: '证据采集' },
  { key: 'L2', label: '多空建论' },
  { key: 'L3', label: '结构化辩论' },
  { key: 'L4', label: '裁决' },
  { key: 'L5', label: '质检' },
  { key: 'L6', label: '决策落库' },
]

/**
 * 研究进度：一条紧凑的阶段轨道，细节只在悬停时出现。
 * phases 形如 { L0: {status, duration_ms, degraded, detail}, ... }
 */
const PhaseProgress = ({ phases = {} }) => {
  const hasAny = Object.keys(phases || {}).length > 0
  if (!hasAny) return null

  const doneCount = PHASE_META.filter(({ key }) => {
    const state = phases[key]
    return state && (state.status === 'done' || state.status === 'degraded' || state.detail?.skipped)
  }).length

  return (
    <section className="pipeline" aria-label="研究进度">
      <div className="pipeline-head">
        <span className="pipeline-title">
          <GitBranch size={13} />
          研究进度
        </span>
        <span className="pipeline-count">{doneCount} / {PHASE_META.length}</span>
      </div>
      <ol className="pipeline-track">
        {PHASE_META.map(({ key, label }) => {
          const state = phases[key]
          const skipped = Boolean(state?.detail?.skipped)
          const status = skipped ? 'skipped' : (state?.status || 'pending')
          const degraded = Boolean(state?.degraded) && status !== 'skipped'
          const duration = formatDuration(state?.duration_ms)
          const reason = state?.detail?.reason
          const stateText = skipped
            ? (reason === 'insufficient_theses' ? '论点不足'
              : reason === 'low_controversy' ? '争议不足' : '未启用')
            : ''
          const title = degraded
            ? `${label} · 有降级`
            : `${label} · ${status === 'done' ? '完成' : status === 'running' ? '进行中' : status === 'pending' ? '待执行' : stateText || '未启用'}`

          return (
            <li
              key={key}
              className={`pipeline-step is-${status}`}
              title={title}
            >
              <span className="pipeline-dot">{key}</span>
              <span className="pipeline-label">{label}</span>
              {duration && <span className="pipeline-time">{duration}</span>}
              {status === 'running' && <span className="loading-dots" />}
              {stateText && <span className="pipeline-state">{stateText}</span>}
            </li>
          )
        })}
      </ol>
    </section>
  )
}

export default PhaseProgress
