/**
 * 统一 API 客户端
 * 封装 Agent 研究提交、SSE 事件流、会话历史接口。
 */

const fallbackHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost'
const API_BASE = (
  import.meta.env.VITE_API_BASE_URL
  || import.meta.env.VITE_API_BASE
  || `http://${fallbackHost}:5001`
).replace(/\/+$/, '')

const REQUEST_TIMEOUT = 30000

async function request(path, options = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT)
  const headers = options.body ? { 'Content-Type': 'application/json', ...(options.headers || {}) } : options.headers
  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers, signal: controller.signal })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      const error = new Error(err.error || `请求失败 (${res.status})`)
      error.status = res.status
      throw error
    }
    return res.json()
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('请求超时，请检查后端服务或网络')
    }
    throw error
  } finally {
    clearTimeout(timer)
  }
}

export function submitQuery(query, { riskPreference = '', sessionId = '' } = {}) {
  return request('/api/agent/query', {
    method: 'POST',
    body: JSON.stringify({
      query,
      risk_preference: riskPreference,
      session_id: sessionId,
    }),
  })
}

export function getHistory() {
  return request('/api/history')
}

export function getSessionHistory(sessionId) {
  return request(`/api/history/${sessionId}`)
}

/**
 * 查询任务状态（SSE 断流时的轮询兜底）
 * @returns {Promise<{status: string, result?: object, error?: string}>}
 */
export function getTaskStatus(taskId) {
  return request(`/api/agent/tasks/${taskId}`)
}

/**
 * 订阅 Agent 研究事件流（SSE）
 * @param {string} taskId 任务 ID
 * @param {(event: {type: string, data: any, timestamp?: number}) => void} onEvent 事件回调
 * @param {() => void} [onError] 连接中断回调（EventSource 会自行重连，调用方可用轮询兜底）
 * @returns {{close: () => void}} 控制对象
 */
export function subscribeAgentEvents(taskId, onEvent, onError) {
  const source = new EventSource(`${API_BASE}/api/agent/events/${taskId}`)
  // 后端 SSE 帧: data = {type, task_id, timestamp, data: {业务数据}}
  // 统一解包为 onEvent({ type, data: 业务数据, timestamp })
  // 注意：EventSource 需要显式订阅事件名（无通配），新增事件必须加到这里
  const EVENT_TYPES = [
    'connected',
    'task_started',
    'plan_ready',
    'orchestrator_thinking',
    'orchestrator_decided',
    'phase_started',
    'phase_completed',
    'agent_started',
    'agent_thinking',
    'agent_completed',
    'agent_failed',
    'agent_degraded',
    'tool_started',
    'tool_completed',
    'tool_failed',
    'evidence_added',
    'thesis_submitted',
    'debate_turn',
    'verdict_ready',
    'verification_failed',
    'decision_recorded',
    'final_answer',
    'task_completed',
    'task_failed',
    'heartbeat',
  ]

  EVENT_TYPES.forEach((eventName) => {
    source.addEventListener(eventName, (msg) => {
      try {
        const frame = JSON.parse(msg.data)
        onEvent({
          type: eventName,
          data: frame.data || {},
          timestamp: frame.timestamp,
          taskId: frame.task_id,
        })
      } catch {
        /* 忽略解析失败 */
      }
    })
  })

  source.onerror = () => {
    // EventSource 自动重连；通知调用方启用轮询兜底
    if (onError) onError()
  }

  return {
    close: () => source.close(),
  }
}
