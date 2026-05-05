from pydantic import BaseModel, ConfigDict, Field

from backend.models.chat import ChatMessageItem


class PageResult(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


class AdminOverviewStats(BaseModel):
    today_logins: int
    total_users: int
    active_users: int
    total_sessions: int
    failed_logins: int


class AdminUser(BaseModel):
    id: int
    username: str
    nickname: str | None = None
    role: str
    status: str
    login_attempts: int = 0
    locked_until: str | None = None
    last_login_time: str | None = None
    created_at: str


class AdminLoginLog(BaseModel):
    id: int
    username: str
    success: int
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: str


class AdminActionLog(BaseModel):
    id: int
    actor_username: str
    actor_role: str
    action: str
    target_type: str
    target_id: str
    target_label: str | None = None
    detail: dict | None = None
    created_at: str


class AdminSession(BaseModel):
    session_id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    is_pinned: bool = False
    message_count: int = 0


class AdminSessionDetail(BaseModel):
    session: AdminSession
    messages: list[ChatMessageItem]


class AdminQueryAudit(BaseModel):
    id: int
    username: str
    session_id: str
    question: str
    sql_text: str | None = None
    duration_ms: int = 0
    from_cache: bool = False
    chart_generated: bool = False
    status: str
    error_message: str | None = None
    created_at: str


class ModelSettings(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str
    base_url: str
    timeout_seconds: int = Field(..., ge=1, le=300)
    retry_count: int = Field(..., ge=0, le=10)
    max_context_rounds: int = Field(..., ge=1, le=20)


class PromptTemplate(BaseModel):
    template_key: str
    template_name: str
    content: str
    description: str | None = None
    updated_at: str | None = None


class UpdateUserStatusRequest(BaseModel):
    status: str = Field(..., pattern='^(active|disabled)$')


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(..., pattern='^(user|admin)$')


class ResetPasswordResponse(BaseModel):
    temporary_password: str


class PinSessionRequest(BaseModel):
    is_pinned: bool = True


class UpdateModelSettingsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., min_length=1, max_length=500)
    timeout_seconds: int = Field(..., ge=1, le=300)
    retry_count: int = Field(..., ge=0, le=10)
    max_context_rounds: int = Field(..., ge=1, le=20)


class UpdatePromptTemplatesRequest(BaseModel):
    templates: list[PromptTemplate]


class CreateUserRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=8)
    password: str | None = Field(default=None, min_length=1, max_length=12)
    nickname: str | None = None


class CreateUserResponse(BaseModel):
    id: int
    username: str
    nickname: str | None
    role: str
    status: str
    login_attempts: int = 0
    locked_until: str | None = None
    last_login_time: str | None = None
    created_at: str
