/**
 * API 客户端
 * 封装 fetch 请求，自动附加 JWT token
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

let authToken = localStorage.getItem('auth_token');
let feedbackHandler = null;

export function setFeedbackHandler(handler) {
  feedbackHandler = handler;
}

export function getAuthToken() {
  return authToken;
}

export function setAuthToken(token) {
  authToken = token;
  if (token) {
    localStorage.setItem('auth_token', token);
  } else {
    localStorage.removeItem('auth_token');
  }
}

async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    ...(options.headers || {}),
  };

  // 显示加载状态
  const loadingKey = options.loadingKey || path;
  if (feedbackHandler?.setLoading) {
    feedbackHandler.setLoading(loadingKey, true);
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errorMsg = data?.error || data?.message || '请求失败';
      
      // 显示错误提示
      if (feedbackHandler?.showError) {
        feedbackHandler.showError(errorMsg);
      }
      
      throw new Error(errorMsg);
    }

    // 显示成功提示（如果配置了）
    if (options.successMessage && feedbackHandler?.showSuccess) {
      feedbackHandler.showSuccess(options.successMessage);
    }

    return data;
  } catch (error) {
    // 网络错误处理
    if (error.name === 'TypeError' && error.message === 'Failed to fetch') {
      const networkError = '网络连接失败，请检查网络设置';
      if (feedbackHandler?.showError) {
        feedbackHandler.showError(networkError);
      }
    }
    
    throw error;
  } finally {
    // 隐藏加载状态
    if (feedbackHandler?.setLoading) {
      feedbackHandler.setLoading(loadingKey, false);
    }
  }
}

// 认证相关
export async function register(username, password, email) {
  return request('/api/auth/register', {
    method: 'POST',
    body: { username, password, email },
    successMessage: '注册成功！',
  });
}

export async function login(username, password) {
  return request('/api/auth/login', {
    method: 'POST',
    body: { username, password },
    successMessage: '登录成功！',
  });
}

export async function fetchProfile() {
  return request('/api/user/profile');
}

export async function updateProfile(data) {
  return request('/api/user/profile', {
    method: 'PUT',
    body: data,
    successMessage: '个人信息更新成功！',
  });
}

export async function updatePhone(phone) {
  return request('/api/user/phone', {
    method: 'PUT',
    body: { phone },
    successMessage: '手机号更新成功！',
  });
}

export async function updatePassword(currentPassword, newPassword) {
  return request('/api/user/password', {
    method: 'PUT',
    body: { current_password: currentPassword, new_password: newPassword },
    successMessage: '密码更新成功！',
  });
}

// 配额相关
export async function getQuota() {
  return request('/api/user/quota');
}

export async function getTiers() {
  return request('/api/user/tiers');
}

export async function upgradeTier(tier) {
  return request('/api/user/upgrade', {
    method: 'POST',
    body: { tier },
    successMessage: `已升级到${tier}！`,
  });
}

// 股票相关
export async function analyzeStock(symbol) {
  return request(`/api/stock/analyze?symbol=${encodeURIComponent(symbol)}`, {
    loadingKey: `stock-${symbol}`,
  });
}

export async function getStockTechnical(symbol) {
  return request(`/api/stock/technical?symbol=${encodeURIComponent(symbol)}`);
}

export async function getStockHistory(symbol, days = 30) {
  return request(`/api/stock/history?symbol=${encodeURIComponent(symbol)}&days=${days}`);
}

export async function getStockSummary(symbol) {
  return request(`/api/stock/summary?symbol=${encodeURIComponent(symbol)}`);
}

// 新闻相关
export async function getNewsTitles(limit = 20) {
  return request(`/api/news/titles?limit=${limit}`);
}

export async function filterNews(keywords) {
  return request('/api/news/filter', {
    method: 'POST',
    body: { keywords },
  });
}

export async function getRelevantNews(query) {
  return request('/api/news/relevant', {
    method: 'POST',
    body: { query },
  });
}

// 聊天相关
export async function sendMessage(message, sessionId = null) {
  return request('/api/chat/send', {
    method: 'POST',
    body: { message, session_id: sessionId },
  });
}

export async function getChatHistory(sessionId) {
  return request(`/api/chat/history?session_id=${sessionId}`);
}

export async function getChatSessions() {
  return request('/api/chat/sessions');
}

export async function clearChatHistory(sessionId) {
  return request('/api/chat/clear', {
    method: 'DELETE',
    body: { session_id: sessionId },
    successMessage: '聊天历史已清空',
  });
}

export async function askQuestion(question) {
  return request('/api/chat/ask', {
    method: 'POST',
    body: { question },
  });
}

// 反馈相关
export async function submitFeedback(sessionId, feedbackData) {
  return request('/api/feedback', {
    method: 'POST',
    body: {
      session_id: sessionId,
      ...feedbackData,
    },
    successMessage: '反馈提交成功！',
  });
}

export async function getFeedback(sessionId) {
  return request(`/api/feedback/${sessionId}`);
}

// 评测相关
export async function getEvalRuns() {
  return request('/api/eval/runs');
}

// V2 API 相关
export async function submitV2Query(query, sessionId = null, preferences = {}) {
  return request('/api/agent/v2/query', {
    method: 'POST',
    body: { query, session_id: sessionId, preferences },
    loadingKey: 'v2-query',
  });
}

export async function getV2TaskStatus(taskId) {
  return request(`/api/agent/v2/status/${taskId}`);
}

export async function getV2Session(sessionId) {
  return request(`/api/agent/v2/session/${sessionId}`);
}

export async function v2HealthCheck() {
  return request('/api/agent/v2/health');
}