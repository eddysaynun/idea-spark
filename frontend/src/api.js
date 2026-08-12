import axios from 'axios';

// API 基础配置
const API_BASE_URL = '/api';

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60 秒超时（模型生成可能需要较长时间）
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    console.error('Request error:', error.message);
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('Response error:', error.message);
    return Promise.reject(error);
  }
);

// ============ API Methods ============

// 配置相关
export const configAPI = {
  // 获取配置
  getConfig: async (adminToken = '') => {
    const response = await apiClient.get('/config', {
      headers: adminToken ? { 'X-Admin-Token': adminToken } : {},
    });
    return response.data;
  },

  // 更新配置
  updateConfig: async (config, adminToken = '') => {
    const response = await apiClient.post('/config', config, {
      headers: adminToken ? { 'X-Admin-Token': adminToken } : {},
    });
    return response.data;
  },

  detectModels: async (adminToken = '') => {
    const response = await apiClient.get('/detect-models', {
      headers: adminToken ? { 'X-Admin-Token': adminToken } : {},
    });
    return response.data;
  },

  listModels: async () => {
    const response = await apiClient.get('/models');
    return response.data;
  },
};

export const authAPI = {
  me: async () => (await apiClient.get('/auth/me')).data,
  logout: async () => (await apiClient.post('/auth/logout')).data,
  loginUrl: (returnTo = '/') => `/api/auth/login?return_to=${encodeURIComponent(returnTo)}`,
};

// Ideas 生成
export const ideasAPI = {
  // 生成 Ideas
  generate: async (params) => {
    const response = await apiClient.post('/generate', params);
    return response.data;
  },

  // 获取详细方案
  getDetail: async (sessionId, ideaIndex, model = '', idempotencyKey) => {
    const response = await apiClient.post('/detail', {
      session_id: sessionId,
      idea_index: ideaIndex,
      model: model || undefined,
    }, { timeout: 180000, headers: { 'Idempotency-Key': idempotencyKey } });
    return response.data;
  },
};

// 会话管理
export const sessionAPI = {
  importLocal: async (session, idempotencyKey) => (await apiClient.post('/projects/import', {
    idempotency_key: idempotencyKey,
    direction: session.direction,
    count: session.ideas.length,
    category: session.category || 'general',
    model: session.model,
    ideas: session.ideas,
    detailed_plans: session.detailed_plans || {},
  })).data,
  // 获取会话列表
  listSessions: async () => {
    const response = await apiClient.get('/sessions');
    return response.data;
  },

  // 获取单个会话
  getSession: async (sessionId) => {
    const response = await apiClient.get(`/sessions/${sessionId}`);
    return response.data;
  },

  // 删除会话
  deleteSession: async (sessionId) => {
    const response = await apiClient.delete(`/sessions/${sessionId}`);
    return response.data;
  },
};

export default apiClient;
