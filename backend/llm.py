from langchain_openai import ChatOpenAI
from langchain_community.embeddings import DashScopeEmbeddings
from backend.config import settings

llm = ChatOpenAI(
    model=settings.model_name,
    temperature=0.1,
    api_key=settings.dashscope_api_key,
    base_url=settings.dashscope_base_url,
    max_retries=3,
    streaming=True,
)

embeddings = DashScopeEmbeddings(
    model="text-embedding-v3",
    dashscope_api_key=settings.dashscope_api_key,
)
