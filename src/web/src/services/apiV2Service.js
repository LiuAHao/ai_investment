/**
 * V2 API 服务
 * 提供 V2 版本的 API 调用和 SSE 事件流
 */

import { getAuthToken } from './apiClient';

const API_BASE = '/api/agent/v2';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001';

function normalizeApiError(response, data) {
  const message = data?.error || data?.message || '请求失败';
  if (response.status === 404) {
    return new Error(message.includes('V2') ? message : 'V2 功能未启用，请设置 AGENT_V2_ENABLED=true 并重启后端');
  }
  if (response.status === 401) {
    return new Error('未授权或登录已过期，请重新登录');
  }
  if (response.status === 429) {
    return new Error(data?.error || '今日分析额度已用完');
  }
  return new Error(message);
}

async function apiRequest(path, options = {}) {
  const token = getAuthToken();
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new Error('后端服务不可达，请确认服务已启动');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw normalizeApiError(response, data);
  }
  return data;
}

/**
 * 提交 V2 查询
 */
export async function submitQuery(query, sessionId = null, preferences = {}) {
  return apiRequest(`${API_BASE}/query`, {
    method: 'POST',
    body: { query, session_id: sessionId, preferences },
  });
}

/**
 * 获取任务状态
 */
export async function getTaskStatus(taskId) {
  return apiRequest(`${API_BASE}/status/${taskId}`);
}

/**
 * 获取会话详情
 */
export async function getSession(sessionId) {
  return apiRequest(`${API_BASE}/session/${sessionId}`);
}

/**
 * V2 健康检查
 */
export async function healthCheck() {
  return apiRequest(`${API_BASE}/health`);
}

/**
 * 创建 SSE 事件流连接
 */
export function createEventStream(taskId, onEvent, onError = null) {
  const token = getAuthToken();
  const eventSource = new EventSource(
    `${API_BASE_URL}${API_BASE}/events/${taskId}${token ? `?token=${encodeURIComponent(token)}` : ''}`
  );
  let fallbackStarted = false;

  const eventHandlers = {
    connected: (data) => console.log('SSE connected:', data),
    task_started: (data) => onEvent?.({ type: 'task_started', ...data }),
    node_started: (data) => onEvent?.({ type: 'node_started', ...data }),
    node_completed: (data) => onEvent?.({ type: 'node_completed', ...data }),
    tool_started: (data) => onEvent?.({ type: 'tool_started', ...data }),
    tool_completed: (data) => onEvent?.({ type: 'tool_completed', ...data }),
    evidence_added: (data) => onEvent?.({ type: 'evidence_added', ...data }),
    draft_created: (data) => onEvent?.({ type: 'draft_created', ...data }),
    critic_completed: (data) => onEvent?.({ type: 'critic_completed', ...data }),
    compliance_completed: (data) => onEvent?.({ type: 'compliance_completed', ...data }),
    task_completed: (data) => onEvent?.({ type: 'task_completed', ...data }),
    task_failed: (data) => onEvent?.({ type: 'task_failed', ...data }),
    heartbeat: () => {},
  };

  Object.entries(eventHandlers).forEach(([event, handler]) => {
    eventSource.addEventListener(event, (e) => {
      try {
        const data = JSON.parse(e.data);
        handler(data);
      } catch (err) {
        console.error(`Parse error for ${event}:`, err);
      }
    });
  });

  eventSource.onerror = (error) => {
    console.error('SSE error:', error);
    if (fallbackStarted) return;
    fallbackStarted = true;
    eventSource.close();
    onError?.(error);
  };

  return {
    close: () => eventSource.close(),
    eventSource,
  };
}

/**
 * 提交反馈
 */
export async function submitFeedback(sessionId, feedbackData) {
  return apiRequest('/api/feedback', {
    method: 'POST',
    body: {
      session_id: sessionId,
      ...feedbackData,
    },
  });
}

/**
 * 获取反馈
 */
export async function getFeedback(sessionId) {
  return apiRequest(`/api/feedback/${sessionId}`);
}

export async function getEvalRuns() {
  return apiRequest('/api/eval/runs');
}
