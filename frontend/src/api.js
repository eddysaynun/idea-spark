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

// ============ API Methods ============

// 模型选择
export const modelAPI = {
  listModels: async () => {
    const response = await apiClient.get('/models');
    return response.data;
  },
};

export const authAPI = {
  me: async () => (await apiClient.get('/auth/me')).data,
  providers: async () => (await apiClient.get('/auth/providers')).data,
  exchange: async (accessToken) => (await apiClient.post('/auth/exchange', { access_token: accessToken })).data,
  restore: async (accessToken) => (await apiClient.post('/auth/restore', { access_token: accessToken })).data,
  logout: async () => (await apiClient.post('/auth/logout')).data,
};

export const accountAPI = {
  requestDeletion: async (confirmation) => (await apiClient.post('/account/deletion', { confirmation })).data,
};

export const productAPI = {
  record: async (projectId, ideaIndex, action) => (await apiClient.post('/product-events', {
    project_id: projectId, idea_index: ideaIndex, action,
  }, { headers: { 'Idempotency-Key': crypto.randomUUID() } })).data,
};

export const adminAPI = {
  metrics: async (token, days = 30) => (await apiClient.get('/admin/metrics', {
    params: { days }, headers: { 'X-Admin-Token': token },
  })).data,
  users: async (token, query = '') => (await apiClient.get('/admin/users', {
    params: { q: query }, headers: { 'X-Admin-Token': token },
  })).data,
  adjustQuota: async (token, userId, resource, delta, reason) => (await apiClient.post(
    `/admin/users/${userId}/quota`, { resource, delta, reason },
    { headers: { 'X-Admin-Token': token } },
  )).data,
  repairQuota: async (token, userId, resource, reason) => (await apiClient.post(
    `/admin/users/${userId}/quota/repair`, { resource, reason },
    { headers: { 'X-Admin-Token': token } },
  )).data,
  audit: async (token, userId) => (await apiClient.get(`/admin/users/${userId}/quota/audit`, {
    headers: { 'X-Admin-Token': token },
  })).data,
  rechargeHistory: async (token, userId) => (await apiClient.get(`/admin/users/${userId}/recharge`, {
    headers: { 'X-Admin-Token': token },
  })).data,
  paymentOrders: async (token, status = '') => (await apiClient.get('/admin/payment-orders', {
    params: { status }, headers: { 'X-Admin-Token': token },
  })).data,
  queryPayment: async (token, orderId) => (await apiClient.post(
    `/admin/payment-orders/${orderId}/query`, {}, { headers: { 'X-Admin-Token': token } },
  )).data,
  refundPayment: async (token, orderId) => (await apiClient.post(
    `/admin/payment-orders/${orderId}/refund`, {}, { headers: { 'X-Admin-Token': token } },
  )).data,
};

export const billingAPI = {
  packages: async () => (await apiClient.get('/billing/packages')).data,
  orders: async () => (await apiClient.get('/billing/orders')).data,
  order: async (orderId) => (await apiClient.get(`/billing/orders/${orderId}`)).data,
  createOrder: async (packageId, channel) => (await apiClient.post('/billing/orders', {
    package_id: packageId, channel,
  })).data,
};

// Ideas 生成
export const ideasAPI = {
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
