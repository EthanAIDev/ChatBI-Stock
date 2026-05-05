import api from './api';
import type { ChatSession, ChatMessage, ApiResponse } from '../types';

export async function getSessions(): Promise<ApiResponse<ChatSession[]>> {
  const { data } = await api.get('/sessions');
  return data;
}

export async function createSession(title = '新对话'): Promise<ApiResponse<{ session_id: string }>> {
  const { data } = await api.post('/sessions', { title });
  return data;
}

export async function getMessages(sessionId: string): Promise<ApiResponse<ChatMessage[]>> {
  const { data } = await api.get(`/sessions/${sessionId}/messages`);
  return data;
}

export async function renameSession(sessionId: string, title: string): Promise<ApiResponse<null>> {
  const { data } = await api.put(`/sessions/${sessionId}/rename`, { title });
  return data;
}

export async function deleteSession(sessionId: string): Promise<ApiResponse<null>> {
  const { data } = await api.delete(`/sessions/${sessionId}`);
  return data;
}

export async function pinSession(sessionId: string, isPinned: boolean): Promise<ApiResponse<{ session_id: string; is_pinned: boolean }>> {
  const { data } = await api.post(`/sessions/${sessionId}/pin`, { is_pinned: isPinned });
  return data;
}
