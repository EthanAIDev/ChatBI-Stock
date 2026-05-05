import api from './api';
import type { LoginRequest, LoginResponse, ApiResponse, UserInfo } from '../types';

export async function login(req: LoginRequest): Promise<ApiResponse<LoginResponse>> {
  const { data } = await api.post('/auth/login', req);
  return data;
}

export async function getMe(): Promise<ApiResponse<UserInfo>> {
  const { data } = await api.get('/auth/me');
  return data;
}
