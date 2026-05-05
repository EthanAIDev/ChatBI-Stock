import api from './api';
import type {
  AdminActionLog,
  AdminOverview,
  AdminQueryAudit,
  AdminSession,
  AdminSessionDetail,
  AdminLoginLog,
  AdminUser,
  ApiResponse,
  CreateUserResponse,
  ModelSettings,
  PageResult,
  PromptTemplate,
} from '../types';

interface ListQuery {
  page?: number;
  page_size?: number;
  keyword?: string;
  start_time?: string;
  end_time?: string;
}

export async function getAdminOverview(): Promise<ApiResponse<AdminOverview>> {
  const { data } = await api.get('/admin/overview');
  return data;
}

export async function getAdminUsers(params: ListQuery & { role?: string; status?: string }): Promise<ApiResponse<PageResult<AdminUser>>> {
  const { data } = await api.get('/admin/users', { params });
  return data;
}

export async function updateAdminUserStatus(userId: number, status: string): Promise<ApiResponse<AdminUser>> {
  const { data } = await api.patch(`/admin/users/${userId}/status`, { status });
  return data;
}

export async function createAdminUser(params?: {
  username?: string;
  password?: string;
  nickname?: string;
}): Promise<ApiResponse<CreateUserResponse>> {
  const { data } = await api.post('/admin/users', params || {});
  return data;
}

export async function updateAdminUserRole(userId: number, role: string): Promise<ApiResponse<AdminUser>> {
  const { data } = await api.patch(`/admin/users/${userId}/role`, { role });
  return data;
}

export async function resetAdminUserPassword(userId: number): Promise<ApiResponse<{ temporary_password: string }>> {
  const { data } = await api.post(`/admin/users/${userId}/reset-password`);
  return data;
}

export async function getAdminLoginLogs(params: ListQuery & { username?: string; success?: number }): Promise<ApiResponse<PageResult<AdminLoginLog>>> {
  const { data } = await api.get('/admin/login-logs', { params });
  return data;
}

export async function getAdminActionLogs(params: ListQuery): Promise<ApiResponse<PageResult<AdminActionLog>>> {
  const { data } = await api.get('/admin/action-logs', { params });
  return data;
}

export async function getAdminSessions(params: ListQuery & { user_id?: string; is_pinned?: boolean }): Promise<ApiResponse<PageResult<AdminSession>>> {
  const { data } = await api.get('/admin/sessions', { params });
  return data;
}

export async function getAdminSessionDetail(sessionId: string): Promise<ApiResponse<AdminSessionDetail>> {
  const { data } = await api.get(`/admin/sessions/${sessionId}`);
  return data;
}

export async function deleteAdminSession(sessionId: string): Promise<ApiResponse<null>> {
  const { data } = await api.delete(`/admin/sessions/${sessionId}`);
  return data;
}

export async function pinAdminSession(sessionId: string, isPinned: boolean): Promise<ApiResponse<{ session_id: string; is_pinned: boolean }>> {
  const { data } = await api.post(`/admin/sessions/${sessionId}/pin`, { is_pinned: isPinned });
  return data;
}

export async function getAdminQueryAudits(
  params: ListQuery & { username?: string; session_id?: string; status?: string },
): Promise<ApiResponse<PageResult<AdminQueryAudit>>> {
  const { data } = await api.get('/admin/query-audits', { params });
  return data;
}

export async function getModelSettings(): Promise<ApiResponse<ModelSettings>> {
  const { data } = await api.get('/admin/model-settings');
  return data;
}

export async function updateModelSettings(payload: ModelSettings): Promise<ApiResponse<ModelSettings>> {
  const { data } = await api.put('/admin/model-settings', payload);
  return data;
}

export async function getPromptTemplates(): Promise<ApiResponse<PromptTemplate[]>> {
  const { data } = await api.get('/admin/prompt-templates');
  return data;
}

export async function updatePromptTemplates(templates: PromptTemplate[]): Promise<ApiResponse<PromptTemplate[]>> {
  const { data } = await api.put('/admin/prompt-templates', { templates });
  return data;
}
