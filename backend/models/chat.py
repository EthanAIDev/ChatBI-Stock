from typing import Any
from pydantic import BaseModel, Field


class ChatQueryRequest(BaseModel):
    session_id: str = Field(..., description='会话ID')
    question: str = Field(..., min_length=1, max_length=2000, description='用户问题')


class ChatQueryResponse(BaseModel):
    content: str = Field(..., description='回复内容')
    sql_text: str | None = Field(None, description='生成的SQL')
    result_preview: str | None = Field(None, description='查询结果预览JSON')
    chart_url: str | None = Field(None, description='图表URL')
    from_cache: bool = Field(False, description='是否来自缓存')

    class Config:
        from_attributes = True


class ChatMessageItem(BaseModel):
    id: int
    role: str
    content: str
    sql_text: str | None = None
    result_preview: str | None = None
    chart_path: str | None = None
    created_at: str


class ChatSessionItem(BaseModel):
    session_id: str
    user_id: str | None = None
    title: str
    created_at: str
    updated_at: str
    is_pinned: bool = False


class CreateSessionRequest(BaseModel):
    title: str = Field('新对话', description='对话标题')


class CreateSessionResponse(BaseModel):
    session_id: str


class RenameSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=50, description='新标题')


class PinSessionRequest(BaseModel):
    is_pinned: bool = Field(..., description='是否置顶')
