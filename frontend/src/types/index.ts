export interface ChatQueryRequest {
  session_id: string;
  question: string;
}

export interface ChatQueryResponse {
  content: string;
  sql_text: string | null;
  result_preview: string | null;
  chart_url: string | null;
  from_cache: boolean;
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  sql_text: string | null;
  result_preview: string | null;
  chart_path: string | null;
  status_text: string | null;
  render_key: number;
  created_at: string;
}

export interface ChatSession {
  session_id: string;
  user_id?: string | null;
  title: string;
  created_at: string;
  updated_at: string;
  is_pinned?: boolean;
}

export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export interface ResultPreview {
  columns: string[];
  data: unknown[][];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  username: string;
  nickname: string;
  role: string;
}

export interface UserInfo {
  username: string;
  nickname: string;
  role: string;
  status: string;
  last_login_time: string | null;
}

export interface AdminStatSummary {
  today_logins: number;
  total_users: number;
  active_users: number;
  total_sessions: number;
  failed_logins: number;
}

export interface AdminUser {
  id: number;
  username: string;
  nickname: string | null;
  role: string;
  status: string;
  login_attempts: number;
  locked_until: string | null;
  last_login_time: string | null;
  created_at: string;
}

export interface AdminLoginLog {
  id: number;
  username: string;
  success: number;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AdminOverview {
  stats: AdminStatSummary;
  recent_login_logs: AdminLoginLog[];
  recent_failures: AdminQueryAudit[];
}

export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminActionLog {
  id: number;
  actor_username: string;
  actor_role: string;
  action: string;
  target_type: string;
  target_id: string;
  target_label: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface AdminSession {
  session_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  is_pinned: boolean;
  message_count: number;
}

export interface AdminSessionDetail {
  session: AdminSession;
  messages: ChatMessage[];
}

export interface AdminQueryAudit {
  id: number;
  username: string;
  session_id: string;
  question: string;
  sql_text: string | null;
  duration_ms: number;
  from_cache: boolean;
  chart_generated: boolean;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface ModelSettings {
  model_name: string;
  base_url: string;
  timeout_seconds: number;
  retry_count: number;
  max_context_rounds: number;
}

export interface PromptTemplate {
  template_key: string;
  template_name: string;
  content: string;
  description: string | null;
  updated_at: string | null;
}

export interface CreateUserResponse {
  id: number;
  username: string;
  nickname: string | null;
  role: string;
  status: string;
  login_attempts: number;
  locked_until: string | null;
  last_login_time: string | null;
  created_at: string;
}
