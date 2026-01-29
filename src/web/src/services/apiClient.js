const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';
const TOKEN_KEY = 'ai_investment_token';

const getAuthHeader = () => {
  const token = getAuthToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
};

export const getAuthToken = () => localStorage.getItem(TOKEN_KEY);

export const setAuthToken = (token) => {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
};

const apiRequest = async (path, options = {}) => {
  const { method = 'GET', body, auth = false } = options;
  const headers = {
    'Content-Type': 'application/json',
    ...(auth ? getAuthHeader() : {}),
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = data?.error || data?.message || '请求失败';
    throw new Error(message);
  }

  return data;
};

export const loginUser = async (username, password) => {
  return apiRequest('/api/auth/login', {
    method: 'POST',
    body: { username, password },
  });
};

export const registerUser = async (username, email, password, nickname) => {
  return apiRequest('/api/auth/register', {
    method: 'POST',
    body: { username, email, password, nickname },
  });
};

export const fetchProfile = async () => {
  return apiRequest('/api/user/profile', { auth: true });
};

export const startAnalyzeWorkflow = async (symbol, newsLimit = 20, preferences = null) => {
  return apiRequest('/api/agent/analyze', {
    method: 'POST',
    auth: true,
    body: { symbol, news_limit: newsLimit, preferences },
  });
};

export const startQueryWorkflow = async (query, preferences = null) => {
  return apiRequest('/api/agent/query', {
    method: 'POST',
    auth: true,
    body: { query, preferences },
  });
};

export const getWorkflowStatus = async (sessionId) => {
  return apiRequest(`/api/agent/status/${sessionId}`, { auth: true });
};

export const fetchNewsTitles = async (limit = 5) => {
  return apiRequest(`/api/news/titles?limit=${limit}`, { auth: true });
};

export const sendChatMessage = async (content, sessionId, role = 'user') => {
  return apiRequest('/api/chat/send', {
    method: 'POST',
    auth: true,
    body: { content, session_id: sessionId, role },
  });
};

export const fetchChatHistory = async (sessionId, limit = 50, offset = 0) => {
  return apiRequest(`/api/chat/history?session_id=${sessionId}&limit=${limit}&offset=${offset}`, {
    auth: true,
  });
};
