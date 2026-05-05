from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class PipelineState(TypedDict):
    question: str
    messages: Annotated[list[BaseMessage], add_messages]
    data_query: bool
    reply: str
    sql: str
    df_json: str
    result_preview: str
    chart_path: str | None
    analysis_mode: str
    answer: str
    from_cache: bool
    error: str | None
