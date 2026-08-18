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
  logout: async () => (await apiClient.post('/auth/logout')).data,
  loginUrl: (returnTo = '/') => `/api/auth/login?return_to=${encodeURIComponent(returnTo)}`,
};

export const adminAPI = {
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
  purchaseRequests: async (token, status = 'pending') => (await apiClient.get('/admin/purchase-requests', {
    params: { status }, headers: { 'X-Admin-Token': token },
  })).data,
  updatePurchaseRequest: async (token, requestId, status) => (await apiClient.patch(
    `/admin/purchase-requests/${requestId}`, { status }, { headers: { 'X-Admin-Token': token } },
  )).data,
  paymentOrders: async (token, status = '') => (await apiClient.get('/admin/payment-orders', {
    params: { status }, headers: { 'X-Admin-Token': token },
  })).data,
};

export const billingAPI = {
  packages: async () => (await apiClient.get('/billing/packages')).data,
  requests: async () => (await apiClient.get('/billing/requests')).data,
  requestPackage: async (packageId, note = '') => (await apiClient.post('/billing/requests', {
    package_id: packageId, note,
  })).data,
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
