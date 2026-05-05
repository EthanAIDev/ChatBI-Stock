from typing import TypedDict, Annotated
from pydantic import BaseModel, Field


class IntentOutput(BaseModel):
    """Intent Router 输出"""
    data_query: bool = Field(description="是否需要查询数据库")
    reply: str = Field("", description="寒暄回复，仅data_query=false时有效")


class SQLOutput(BaseModel):
    """SQL Generator 输出"""
    sql: str = Field(description="生成的SELECT语句")


class AnalystOutput(BaseModel):
    """Data Analyst 输出（不做严格解析，仅结构化）"""
    answer: str = Field(description="分析结果")
