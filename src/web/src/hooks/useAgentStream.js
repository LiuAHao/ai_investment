import { useCallback, useEffect, useRef, useState } from 'react'
import { subscribeAgentEvents } from '../services/apiClient'

/**
 * Agent 事件流状态管理
 * 维护编排卡片、Agent 卡片、最终报告的实时状态。
 */
export function useAgentStream() {
  const [taskId, setTaskId] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [phase, setPhase] = useState('idle') // idle | orchestrating | researching | summarizing | done | failed
  const [error, setError] = useState('')

  const [orchestrator, setOrchestrator] = useState({ thoughts: [], plan: null })
  const [agents, setAgents] = useState({}) // agentName -> {status, thoughts[], tools[], summary}
  const [finalAnswer, setFinalAnswer] = useState(null)
  const [agentOrder, setAgentOrder] = useState([])

  const sourceRef = useRef(null)

  const reset = useCallback(() => {
    setTaskId('')
    setSessionId('')
    setPhase('idle')
    setError('')
    setOrchestrator({ thoughts: [], plan: null })
    setAgents({})
    setFinalAnswer(null)
    setAgentOrder([])
    if (sourceRef.current) {
      sourceRef.current.close()
      sourceRef.current = null
    }
  }, [])

  const start = useCallback(async (query, options = {}) => {
    reset()
    try {
      const { submitQuery } = await import('../services/apiClient')
      const { task_id, session_id } = await submitQuery(query, options)
      setTaskId(task_id)
      setSessionId(session_id)
      setPhase('orchestrating')
      listen(task_id)
    } catch (e) {
      setError(e.message || '提交失败')
      setPhase('failed')
    }
  }, [reset])

  const listen = useCallback((tid) => {
    sourceRef.current = subscribeAgentEvents(tid, (event) => {
      handleEvent(event)
    })
  }, [])

  const handleEvent = useCallback(({ type, data }) => {
    switch (type) {
      case 'orchestrator_thinking':
        setOrchestrator((prev) => ({ ...prev, thoughts: [...prev.thoughts, data.thought] }))
        break
      case 'orchestrator_decided': {
        const plan = data.plan || []
        setOrchestrator((prev) => ({ ...prev, plan }))
        setAgentOrder(plan)
        // 按 plan 预创建卡片（P4：只以 plan 为准创建）
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
        setAgents((prev) => ({
          ...prev,
          [data.agent]: { ...(prev[data.agent] || {}), status: 'thinking', task: data.task },
        }))
        break
      case 'agent_thinking':
        setAgents((prev) => ({
          ...prev,
          [data.agent]: {
            ...(prev[data.agent] || {}),
            status: 'thinking',
            thoughts: [...(prev[data.agent]?.thoughts || []), data.thought],
          },
        }))
        break
      case 'tool_started':
        setAgents((prev) => ({
          ...prev,
          [data.agent]: {
            ...(prev[data.agent] || {}),
            status: 'tooling',
            tools: [...(prev[data.agent]?.tools || []), { tool: data.tool, params: data.params, status: 'running' }],
          },
        }))
        break
      case 'tool_completed':
        setAgents((prev) => {
          const tools = [...(prev[data.agent]?.tools || [])]
          const last = tools.findLast((t) => t.status === 'running') || tools[tools.length - 1]
          if (last) {
            last.status = 'completed'
            last.latency = data.latency
            last.summary = data.summary
          }
          return {
            ...prev,
            [data.agent]: {
              ...(prev[data.agent] || {}),
              status: 'thinking',
              tools,
            },
          }
        })
        break
      case 'tool_failed':
        setAgents((prev) => {
          const tools = [...(prev[data.agent]?.tools || [])]
          const last = tools.findLast((t) => t.status === 'running') || tools[tools.length - 1]
          if (last) {
            last.status = 'failed'
            last.error = data.error
          }
          return {
            ...prev,
            [data.agent]: {
              ...(prev[data.agent] || {}),
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
      case 'agent_completed':
        setAgents((prev) => ({
          ...prev,
          [data.agent]: {
            ...(prev[data.agent] || {}),
            status: 'done',
            summary: data.result_summary,
          },
        }))
        break
      case 'final_answer':
        setFinalAnswer(data.answer)
        setPhase('done')
        break
      case 'task_completed':
        if (data.result?.answer) setFinalAnswer(data.result.answer)
        setPhase('done')
        break
      case 'task_failed':
        setError(data.error || '任务失败')
        setPhase('failed')
        break
      default:
        break
    }
  }, [])

  useEffect(() => {
    return () => {
      if (sourceRef.current) sourceRef.current.close()
    }
  }, [])

  return {
    taskId,
    sessionId,
    phase,
    error,
    orchestrator,
    agents,
    agentOrder,
    finalAnswer,
    start,
    reset,
  }
}
