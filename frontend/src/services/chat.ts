import api from './api';
import type { ChatQueryRequest, ChatQueryResponse, ApiResponse } from '../types';

export async function queryChat(req: ChatQueryRequest): Promise<ApiResponse<ChatQueryResponse>> {
  const { data } = await api.post('/chat/query', req);
  return data;
}
