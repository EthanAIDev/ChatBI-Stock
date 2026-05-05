import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_name: str = 'deepseek-v4-pro'
    dashscope_api_key: str = ''
    dashscope_base_url: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    db_path: str = ''
    schema_db_path: str = ''
    image_dir: str = ''
    max_retry: int = 3
    max_context_rounds: int = 5
    query_cache_ttl: int = 600
    max_result_rows: int = 5000
    query_timeout_seconds: int = 60
    api_host: str = '0.0.0.0'
    api_port: int = 8000
    chroma_persist_dir: str = ''
    cors_origins: list[str] = ['http://localhost:5173', 'http://localhost:3000', 'http://localhost:8503']

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        base = Path(__file__).resolve().parent.parent
        if not self.db_path:
            self.db_path = str(base / 'stock_prices.db')
        if not self.schema_db_path:
            self.schema_db_path = str(base / 'schema_vector.db')
        if not self.image_dir:
            self.image_dir = str(base / 'image_show' / 'api')
        if not self.dashscope_api_key:
            self.dashscope_api_key = os.getenv('DASHSCOPE_API_KEY', '')
        if not self.chroma_persist_dir:
            self.chroma_persist_dir = str(base / 'chroma_db')


settings = Settings()
