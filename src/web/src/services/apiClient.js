/**
 * 统一 API 客户端
 * 封装 Agent 研究提交、SSE 事件流、会话历史接口。
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE || 'http://localhost:5001'

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `请求失败 (${res.status})`)
  }
  return res.json()
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
 * 订阅 Agent 研究事件流（SSE）
 * @param {string} taskId 任务 ID
 * @param {(event: {type: string, data: any}) => void} onEvent 事件回调
 * @returns {{close: () => void}} 控制对象
 */
export function subscribeAgentEvents(taskId, onEvent) {
  const source = new EventSource(`${API_BASE}/api/agent/events/${taskId}`)
  // 后端 SSE 帧: data = {type, task_id, timestamp, data: {业务数据}}
  // 这里统一解包为 onEvent({ type, data: 业务数据 })
  const handlers = {
    connected: (e) => onEvent({ type: 'connected', data: e.data || {} }),
    task_started: (e) => onEvent({ type: 'task_started', data: e.data || {} }),
    orchestrator_thinking: (e) => onEvent({ type: 'orchestrator_thinking', data: e.data || {} }),
    orchestrator_decided: (e) => onEvent({ type: 'orchestrator_decided', data: e.data || {} }),
    agent_started: (e) => onEvent({ type: 'agent_started', data: e.data || {} }),
    agent_thinking: (e) => onEvent({ type: 'agent_thinking', data: e.data || {} }),
    tool_started: (e) => onEvent({ type: 'tool_started', data: e.data || {} }),
    tool_completed: (e) => onEvent({ type: 'tool_completed', data: e.data || {} }),
    tool_failed: (e) => onEvent({ type: 'tool_failed', data: e.data || {} }),
    agent_failed: (e) => onEvent({ type: 'agent_failed', data: e.data || {} }),
    agent_completed: (e) => onEvent({ type: 'agent_completed', data: e.data || {} }),
    final_answer: (e) => onEvent({ type: 'final_answer', data: e.data || {} }),
    task_completed: (e) => onEvent({ type: 'task_completed', data: e.data || {} }),
    task_failed: (e) => onEvent({ type: 'task_failed', data: e.data || {} }),
  }

  Object.entries(handlers).forEach(([type, handler]) => {
    source.addEventListener(type, (msg) => {
      try {
        handler(JSON.parse(msg.data))
      } catch {
        /* 忽略解析失败 */
      }
    })
  })

  source.onerror = () => {
    // EventSource 自动重连
  }

  return {
    close: () => source.close(),
  }
}
