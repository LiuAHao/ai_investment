import { useCallback, useEffect, useRef, useState } from 'react'
import { getTaskStatus, submitQuery, subscribeAgentEvents } from '../services/apiClient'
import { phasesFromTrace } from '../utils/phases'

const POLL_INITIAL = 1200
const POLL_FACTOR = 1.4
const POLL_MAX = 3000
const POLL_DEADLINE = 15 * 60 * 1000
const STORAGE_KEY = 'aii.currentTask.v1'

const RUNNING_STATUS = new Set(['waiting', 'thinking', 'tooling'])

const TERMINAL_EVENTS = new Set(['task_completed', 'task_failed'])

function readSavedTask() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || !parsed.taskId) return null
    return parsed
  } catch {
    return null
  }
}

/**
 * Agent 事件流状态管理
 * 维护编排卡片、Agent 卡片、最终报告的实时状态。
 * SSE 断流时用任务状态接口轮询兜底，保证最终结论不丢。
 */
export function useAgentStream() {
  const [saved] = useState(readSavedTask)
  const [taskId, setTaskId] = useState(saved?.taskId || '')
  const [sessionId, setSessionId] = useState(saved?.sessionId || '')
  const [phase, setPhase] = useState(saved?.taskId ? 'orchestrating' : 'idle')
  const [error, setError] = useState('')
  const [recoveredByPolling, setRecoveredByPolling] = useState(false)

  const [orchestrator, setOrchestrator] = useState({ thoughts: [], plan: null })
  const [agents, setAgents] = useState({}) // agentName -> {status, round, thoughts[], tools[], summary, round1Summary}
  const [finalAnswer, setFinalAnswer] = useState(null)
  const [agentOrder, setAgentOrder] = useState([])
  const [evidence, setEvidence] = useState([])
  const [debateTurns, setDebateTurns] = useState([])
  const [verdict, setVerdict] = useState(null)
  const [verification, setVerification] = useState(null)
  const [theses, setTheses] = useState({})
  const [phases, setPhases] = useState({})
  const [planMeta, setPlanMeta] = useState(null)
  const [decisionId, setDecisionId] = useState('')
  const [debateInfo, setDebateInfo] = useState(null)

  const sourceRef = useRef(null)
  const pollRef = useRef(null)
  const finishedRef = useRef(false)
  const restoredRef = useRef(false)
  const sessionIdRef = useRef(saved?.sessionId || '')
  const seenEventsRef = useRef(new Set())

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearTimeout(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const closeSource = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close()
      sourceRef.current = null
    }
  }, [])

  const reset = useCallback((keepSession = false) => {
    setTaskId('')
    if (!keepSession) {
      setSessionId('')
      sessionIdRef.current = ''
    }
    setPhase('idle')
    setError('')
    setRecoveredByPolling(false)
    setOrchestrator({ thoughts: [], plan: null })
    setAgents({})
    setFinalAnswer(null)
    setAgentOrder([])
    setEvidence([])
    setDebateTurns([])
    setPlanMeta(null)
    setDecisionId('')
    setDebateInfo(null)
    setVerdict(null)
    setVerification(null)
    setTheses({})
    setPhases({})
    finishedRef.current = false
    seenEventsRef.current.clear()
    stopPolling()
    closeSource()
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* 隐私模式下忽略 */
    }
  }, [closeSource, stopPolling])

  /** 用任务状态接口返回的完整结果补全页面状态 */
  const applyTaskResult = useCallback((result = {}) => {
    const rawPlan = result.plan
    const plan = Array.isArray(rawPlan) ? rawPlan : (rawPlan?.agents || [])
    const agentResults = result.agent_results || []
    const thoughts = result.orchestrator?.thoughts || []

    if (thoughts.length) {
      setOrchestrator((prev) => ({ ...prev, thoughts, plan: plan.length ? plan : prev.plan }))
    } else if (plan.length) {
      setOrchestrator((prev) => ({ ...prev, plan }))
    }
    if (plan.length) setAgentOrder(plan)

    if (agentResults.length) {
      setAgents((prev) => {
        const next = { ...prev }
        agentResults.forEach((r) => {
          const name = r.agent_name
          if (!name) return
          const base = next[name] || { thoughts: [], tools: [] }
          const restoredTools = (r.tool_calls || []).map((tool) => ({
            tool: tool.tool_name || tool.tool,
            status: tool.status === 'failed' ? 'failed'
              : tool.status === 'skipped' ? 'skipped' : 'completed',
            latency: tool.latency_ms ?? tool.latency,
            summary: tool.summary,
            error: tool.error,
            params: tool.params,
          }))
          next[name] = {
            ...base,
            status: r.error ? 'failed' : 'done',
            error: r.error || '',
            summary: r.conclusion || base.summary || '',
            thoughts: base.thoughts?.length ? base.thoughts : (r.thinking_log || []),
            tools: base.tools?.length ? base.tools : restoredTools,
            degraded: Boolean(r.degraded) || Boolean(base.degraded),
          }
        })
        Object.keys(next).forEach((name) => {
          if (RUNNING_STATUS.has(next[name].status)) {
            next[name] = { ...next[name], status: 'done' }
          }
        })
        return next
      })
    } else {
      setAgents((prev) => {
        const next = { ...prev }
        Object.keys(next).forEach((name) => {
          if (RUNNING_STATUS.has(next[name].status)) {
            next[name] = { ...next[name], status: 'done' }
          }
        })
        return next
      })
    }

    if (result.evidence) setEvidence(result.evidence)
    if (result.debate?.turns) setDebateTurns(result.debate.turns)
    if (result.debate) setDebateInfo(result.debate)
    if (result.decision_id) setDecisionId(result.decision_id)
    if (result.verdict) setVerdict(result.verdict)
    if (result.thesis) setTheses(result.thesis)
    if (result.verification) setVerification(result.verification)
    if (result.trace?.phases?.length) {
      const fromTrace = phasesFromTrace(result.trace)
      setPhases((prev) => {
        const merged = { ...prev, ...fromTrace }
        // trace 不记录未执行阶段（如 L3 skipped），保留实时事件里的详情
        if (prev?.L3?.detail?.skipped) {
          merged.L3 = { ...(fromTrace.L3 || {}), ...prev.L3, status: 'done' }
        }
        return merged
      })
    }

    if (result.answer) {
      setFinalAnswer(result.answer)
      setPhase('done')
    } else {
      setError('任务已完成但未返回结论文本')
      setPhase('failed')
    }
  }, [])

  /** SSE 断流后的轮询兜底（幂等：已在轮询则忽略） */
  const startPolling = useCallback((tid) => {
    if (!tid || finishedRef.current || pollRef.current) return
    const deadline = Date.now() + POLL_DEADLINE
    let delay = POLL_INITIAL

    const finishWithError = (message) => {
      finishedRef.current = true
      stopPolling()
      closeSource()
      setRecoveredByPolling(true)
      setError(message)
      setPhase('failed')
    }

    const tick = async () => {
      if (finishedRef.current) return
      if (Date.now() > deadline) {
        finishWithError('任务状态查询超时，请稍后在历史记录中查看结果')
        return
      }
      try {
        const status = await getTaskStatus(tid)
        if (status.status === 'completed') {
          finishedRef.current = true
          stopPolling()
          closeSource()
          setRecoveredByPolling(true)
          applyTaskResult(status.result || {})
          return
        }
        if (status.status === 'failed') {
          finishWithError(status.error || '任务执行失败')
          return
        }
      } catch (e) {
        if (e.status === 404) {
          finishWithError('任务已失效（后端可能已重启），请到历史记录查看')
        } else {
          finishWithError(e.message || '无法获取任务状态，请检查网络或后端服务')
        }
        return
      }

      delay = Math.min(POLL_MAX, Math.round(delay * POLL_FACTOR))
      pollRef.current = setTimeout(tick, delay)
    }

    tick()
  }, [applyTaskResult, closeSource, stopPolling])

  const handleEvent = useCallback(({ type, data = {}, timestamp }) => {
    // 重连会回放事件缓冲：用 timestamp + 类型 + agent/tool 去重
    if (timestamp !== undefined && timestamp !== null) {
      const key = `${type}|${timestamp}|${data.agent || ''}|${data.tool || ''}`
      if (seenEventsRef.current.has(key)) return
      seenEventsRef.current.add(key)
      if (seenEventsRef.current.size > 2000) seenEventsRef.current.clear()
    }

    switch (type) {
      case 'plan_ready': {
        const plan = data.plan || data || {}
        setPlanMeta(plan)
        const planAgents = plan.agents || data.agents || []
        if (planAgents.length) {
          setOrchestrator((prev) => ({ ...prev, plan: planAgents, reason: plan.reason || prev.reason }))
          setAgentOrder(planAgents)
        }
        break
      }
      case 'phase_started':
        setPhases((prev) => ({ ...prev, [data.phase]: { status: 'running', label: data.label } }))
        break
      case 'phase_completed':
        setPhases((prev) => ({
          ...prev,
          [data.phase]: {
            ...(prev[data.phase] || {}),
            status: 'done',
            duration_ms: data.duration_ms,
            degraded: data.degraded,
            detail: data.detail || {},
          },
        }))
        if (data.phase === 'L3' && data.detail?.skipped) {
          const reason = data.detail.reason
          const label = reason === 'debate_disabled'
            ? '本次为宏观/无明确标的研究，未启用辩论'
            : reason === 'insufficient_theses'
              ? '一方论点不足（<3 条），跳过辩论'
              : '争议度不足，跳过辩论'
          setDebateInfo((prev) => ({
            ...(prev || {}),
            stopped_reason: label,
            controversy: data.detail.controversy,
          }))
        }
        break
      case 'evidence_added':
        setEvidence((prev) => {
          if (prev.some((item) => item.evidence_id === data.evidence_id)) return prev
          return [...prev, data]
        })
        break
      case 'debate_turn':
        setDebateTurns((prev) => [...prev, data])
        break
      case 'verdict_ready':
        setVerdict(data)
        break
      case 'thesis_started':
        setTheses((prev) => ({
          ...prev,
          [data.side]: { ...(prev[data.side] || {}), side: data.side, status: 'running' },
        }))
        break
      case 'thesis_submitted':
        setTheses((prev) => ({ ...prev, [data.side]: { ...data, status: 'done' } }))
        break
      case 'verification_failed':
        setVerification((prev) => ({
          ...(prev || {}),
          passed: false,
          issues: data.issues || [],
        }))
        break
      case 'plan_ready':
        if (data.plan) setPlanMeta(data.plan)
        break
      case 'orchestrator_thinking':
        setOrchestrator((prev) => {
          if (!data.thought || prev.thoughts[prev.thoughts.length - 1] === data.thought) return prev
          return { ...prev, thoughts: [...prev.thoughts, data.thought] }
        })
        break
      case 'orchestrator_decided': {
        const plan = data.plan || []
        setOrchestrator((prev) => ({ ...prev, plan }))
        setAgentOrder(plan)
        // 按 plan 预创建卡片（只渲染实际启动的 Agent）
        setAgents((prev) => {
          const next = { ...prev }
          plan.forEach((name) => {
            if (!next[name]) {
              next[name] = { status: 'waiting', thoughts: [], tools: [], summary: '' }
            }
          })
          return next
        })
        setPhase((p) => (p === 'orchestrating' ? 'researching' : p))
        break
      }
      case 'agent_started':
        if (data.agent === 'SummaryAgent') {
          setPhase('summarizing')
        }
        setAgents((prev) => ({
          ...prev,
          [data.agent]: {
            ...(prev[data.agent] || {}),
            status: 'thinking',
            round: data.round || 1,
            task: data.task,
            ...(data.round === 2 ? { round1Summary: prev[data.agent]?.summary || '' } : {}),
          },
        }))
        break
      case 'agent_thinking':
        setAgents((prev) => {
          const agent = prev[data.agent] || {}
          const thoughts = agent.thoughts || []
          if (thoughts[thoughts.length - 1] === data.thought) return prev
          return {
            ...prev,
            [data.agent]: {
              ...agent,
              status: 'thinking',
              thoughts: [...thoughts, data.thought],
            },
          }
        })
        break
      case 'tool_started':
        setAgents((prev) => {
          const agent = prev[data.agent] || {}
          const tools = agent.tools || []
          const duplicated = tools.some((t) => (
            t.status === 'running'
            && t.tool === data.tool
            && JSON.stringify(t.params) === JSON.stringify(data.params)
          ))
          if (duplicated) return prev
          return {
            ...prev,
            [data.agent]: {
              ...agent,
              status: 'tooling',
              tools: [...tools, { tool: data.tool, params: data.params, status: 'running' }],
            },
          }
        })
        break
      case 'decision_recorded':
        setDecisionId(data.decision_id || '')
        break
      case 'tool_completed':
        setAgents((prev) => {
          const current = prev[data.agent] || {}
          const tools = (current.tools || []).map((tool) => ({ ...tool }))
          let index = -1
          for (let i = tools.length - 1; i >= 0; i -= 1) {
            if (tools[i].status === 'running' && (!data.tool || tools[i].tool === data.tool)) {
              index = i
              break
            }
          }
          if (index === -1) index = tools.length - 1
          if (index >= 0) {
            tools[index] = {
              ...tools[index],
              status: data.status === 'failed' ? 'failed'
                : data.status === 'skipped' ? 'skipped' : 'completed',
              latency: data.latency,
              summary: data.summary,
              error: data.error,
            }
          }
          return {
            ...prev,
            [data.agent]: {
              ...current,
              status: 'thinking',
              tools,
            },
          }
        })
        break
      case 'tool_failed':
        setAgents((prev) => {
          const current = prev[data.agent] || {}
          const tools = (current.tools || []).map((tool) => ({ ...tool }))
          let index = -1
          for (let i = tools.length - 1; i >= 0; i -= 1) {
            if (tools[i].status === 'running' && (!data.tool || tools[i].tool === data.tool)) {
              index = i
              break
            }
          }
          if (index === -1) index = tools.length - 1
          if (index >= 0) {
            tools[index] = { ...tools[index], status: 'failed', error: data.error }
          }
          return {
            ...prev,
            [data.agent]: {
              ...current,
              status: 'thinking',
              tools,
            },
          }
        })
        break
      case 'agent_failed':
        setAgents((prev) => ({
          ...prev,
          [data.agent]: { ...(prev[data.agent] || {}), status: 'failed', error: data.error },
        }))
        break
      case 'agent_degraded':
        setAgents((prev) => ({
          ...prev,
          [data.agent]: {
            ...(prev[data.agent] || {}),
            degraded: true,
            degradedReason: data.reason || '',
            degradedPermanent: Boolean(data.permanent),
          },
        }))
        break
      case 'agent_completed':
        setAgents((prev) => {
          const round = data.round || 1
          const prevAgent = prev[data.agent] || {}
          const nextStatus = 'done'
          return {
            ...prev,
            [data.agent]: {
              ...prevAgent,
              status: nextStatus,
              round,
              summary: data.result_summary,
              ...(round === 1 ? { round1Summary: data.result_summary } : {}),
            },
          }
        })
        break
      case 'final_answer':
        // 只标记答案已到，不提前关闭终态：task_completed 仍会带来完整明细
        setFinalAnswer(data.answer)
        setPhase('done')
        setAgents((prev) => {
          const next = { ...prev }
          Object.keys(next).forEach((name) => {
            if (next[name].status === 'round1_done') next[name] = { ...next[name], status: 'done' }
          })
          return next
        })
        break
      case 'task_completed':
        if (finishedRef.current) return
        finishedRef.current = true
        stopPolling()
        closeSource()
        applyTaskResult(data.result || {})
        break
      case 'task_failed':
        if (finishedRef.current) return
        finishedRef.current = true
        stopPolling()
        closeSource()
        setError(data.error || '任务失败')
        setPhase('failed')
        setAgents((prev) => {
          const next = { ...prev }
          Object.keys(next).forEach((name) => {
            if (RUNNING_STATUS.has(next[name].status)) {
              next[name] = { ...next[name], status: 'failed' }
            }
          })
          return next
        })
        break
      default:
        break
    }
  }, [applyTaskResult, closeSource, stopPolling])

  const listen = useCallback((tid) => {
    closeSource()
    sourceRef.current = subscribeAgentEvents(
      tid,
      (event) => {
        handleEvent(event)
      },
      () => {
        // EventSource 会自行重连；同时开启轮询，避免断流后结论丢失
        if (!finishedRef.current) startPolling(tid)
      },
    )
  }, [closeSource, handleEvent, startPolling])

  const start = useCallback(async (query, options = {}) => {
    const keepSessionId = options.sessionId ?? sessionIdRef.current
    reset(true)
    sessionIdRef.current = keepSessionId
    setSessionId(keepSessionId)
    try {
      const { task_id, session_id } = await submitQuery(query, {
        ...options,
        sessionId: keepSessionId,
      })
      setTaskId(task_id)
      setSessionId(session_id)
      sessionIdRef.current = session_id
      setPhase('orchestrating')
      listen(task_id)
      return true
    } catch (e) {
      setError(e.message || '提交失败')
      setPhase('failed')
      return false
    }
  }, [listen, reset])

  // 保存/恢复任务元信息，刷新页面后可以重新接回正在运行的任务
  useEffect(() => {
    if (!taskId && !sessionId) return
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ taskId, sessionId, phase }))
    } catch {
      /* 隐私模式下忽略 */
    }
  }, [taskId, sessionId, phase])

  useEffect(() => {
    if (restoredRef.current || !saved?.taskId) return
    restoredRef.current = true
    const tid = saved.taskId
    finishedRef.current = false

    getTaskStatus(tid)
      .then((status) => {
        if (status.status === 'completed') {
          finishedRef.current = true
          applyTaskResult(status.result || {})
        } else if (status.status === 'failed') {
          finishedRef.current = true
          setError(status.error || '任务执行失败')
          setPhase('failed')
        } else {
          listen(tid)
        }
      })
      .catch((e) => {
        finishedRef.current = true
        if (e.status === 404) {
          setError('上次任务已失效（后端可能已重启），请到历史记录查看或开始新对话')
        } else {
          setError(e.message || '无法恢复上次任务')
        }
        setPhase('failed')
      })
  }, [applyTaskResult, listen, saved])

  useEffect(() => {
    return () => {
      stopPolling()
      closeSource()
    }
  }, [closeSource, stopPolling])

  return {
    taskId,
    sessionId,
    phase,
    error,
    recoveredByPolling,
    orchestrator,
    agents,
    agentOrder,
    finalAnswer,
    evidence,
    debateTurns,
    verdict,
    verification,
    theses,
    phases,
    planMeta,
    decisionId,
    debateInfo,
    start,
    reset,
  }
}
