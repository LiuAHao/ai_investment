const API_BASE_URL = 'http://localhost:5000/api';

let authToken = localStorage.getItem('authToken') || '';

export const setAuthToken = (token) => {
  authToken = token;
  if (token) {
    localStorage.setItem('authToken', token);
  } else {
    localStorage.removeItem('authToken');
  }
};

const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(authToken && { 'Authorization': `Bearer ${authToken}` }),
    ...options.headers,
  };

  try {
    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || '请求失败');
    }

    return await response.json();
  } catch (error) {
    console.error('API请求错误:', error);
    throw error;
  }
};

export const authService = {
  register: async (username, email, password, nickname) => {
    return apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, email, password, nickname }),
    });
  },

  login: async (username, password) => {
    const data = await apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    if (data.token) {
      setAuthToken(data.token);
    }
    return data;
  },

  logout: () => {
    setAuthToken(null);
  },

  getProfile: async () => {
    return apiRequest('/user/profile');
  },

  updateProfile: async (nickname, email) => {
    return apiRequest('/user/profile', {
      method: 'PUT',
      body: JSON.stringify({ nickname, email }),
    });
  },
};

export const agentService = {
  analyze: async (symbol, newsLimit = 20) => {
    return apiRequest('/agent/analyze', {
      method: 'POST',
      body: JSON.stringify({ symbol, news_limit: newsLimit }),
    });
  },

  query: async (query) => {
    return apiRequest('/agent/query', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
  },

  getStatus: async (sessionId) => {
    return apiRequest(`/agent/status/${sessionId}`);
  },

  getSessions: async (limit = 20, offset = 0) => {
    return apiRequest(`/agent/sessions?limit=${limit}&offset=${offset}`);
  },
};

export const stockService = {
  analyze: async (symbol, startDate, endDate, period = 'daily', adjust = '') => {
    const params = new URLSearchParams({ symbol });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    params.append('period', period);
    if (adjust) params.append('adjust', adjust);

    return apiRequest(`/stock/analyze?${params}`);
  },

  technical: async (symbol, startDate, endDate, period = 'daily', adjust = '', maWindows = []) => {
    const params = new URLSearchParams({ symbol });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    params.append('period', period);
    if (adjust) params.append('adjust', adjust);
    maWindows.forEach(w => params.append('ma_windows', w));

    return apiRequest(`/stock/technical?${params}`);
  },

  history: async (symbol, startDate, endDate, period = 'daily', adjust = '') => {
    const params = new URLSearchParams({ symbol });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    params.append('period', period);
    if (adjust) params.append('adjust', adjust);

    return apiRequest(`/stock/history?${params}`);
  },

  summary: async (symbol) => {
    return apiRequest(`/stock/summary?symbol=${symbol}`);
  },
};

export const newsService = {
  getTitles: async (limit = 50) => {
    return apiRequest(`/news/titles?limit=${limit}`);
  },

  filter: async (keywords, titles) => {
    return apiRequest('/news/filter', {
      method: 'POST',
      body: JSON.stringify({ keywords, titles }),
    });
  },

  getRelevant: async (keywords, limit = 50) => {
    return apiRequest('/news/relevant', {
      method: 'POST',
      body: JSON.stringify({ keywords, limit }),
    });
  },
};

export const chatService = {
  send: async (content, sessionId = 'default', role = 'user') => {
    return apiRequest('/chat/send', {
      method: 'POST',
      body: JSON.stringify({ content, session_id: sessionId, role }),
    });
  },

  getHistory: async (sessionId = 'default', limit = 50, offset = 0) => {
    return apiRequest(`/chat/history?session_id=${sessionId}&limit=${limit}&offset=${offset}`);
  },

  getSessions: async () => {
    return apiRequest('/chat/sessions');
  },

  clear: async (sessionId = 'default') => {
    return apiRequest(`/chat/clear?session_id=${sessionId}`, {
      method: 'DELETE',
    });
  },
};
