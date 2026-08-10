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
  const [agents, setAgents] = useState({}) // agentName -> {status, round, thoughts[], tools[], summary, round1Summary}
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
        // SummaryAgent 开始分析 → 进入 PHASE 03（展示总结进度卡，不必等完成）
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
        setAgents((prev) => {
          const round = data.round || 1
          const prevAgent = prev[data.agent] || {}
          // SummaryAgent 单轮完成直接置为已完成（随后 final_answer 渲染完整研报）
          const isSummary = data.agent === 'SummaryAgent'
          // 调研 Agent：第一轮完成保存结论等待补充；第二轮完成置为已完成
          const nextStatus = isSummary ? 'done' : (round === 1 ? 'round1_done' : 'done')
          return {
            ...prev,
            [data.agent]: {
              ...prevAgent,
              status: nextStatus,
              round,
              summary: data.result_summary,
              // 第一轮完成时记录本轮摘要；第二轮完成时覆盖最终摘要
              ...(round === 1 ? { round1Summary: data.result_summary } : {}),
            },
          }
        })
        break
      case 'final_answer':
        setFinalAnswer(data.answer)
        setPhase('done')
        // 无第二轮时，将第一轮完成的 Agent 置为已完成
        setAgents((prev) => {
          const next = { ...prev }
          Object.keys(next).forEach((name) => {
            if (next[name].status === 'round1_done') next[name] = { ...next[name], status: 'done' }
          })
          return next
        })
        break
      case 'task_completed':
        if (data.result?.answer) setFinalAnswer(data.result.answer)
        setPhase('done')
        setAgents((prev) => {
          const next = { ...prev }
          Object.keys(next).forEach((name) => {
            if (next[name].status === 'round1_done') next[name] = { ...next[name], status: 'done' }
          })
          return next
        })
        break
      case 'task_failed':
        setError(data.error || '任务失败')
        setPhase('failed')
        break
      default:
        break
    }
  }, [])

  const listen = useCallback((tid) => {
    sourceRef.current = subscribeAgentEvents(tid, (event) => {
      handleEvent(event)
    })
  }, [handleEvent])

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
  }, [reset, listen])

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
