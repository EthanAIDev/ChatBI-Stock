import langchain
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from langchain_community.cache import SQLiteCache

from backend.config import settings
from backend.routers import chat, session, auth, chat_stream, admin
from backend.routers.auth import get_current_user
from backend.services.session_service import ensure_app_tables
from backend.services.auth_service import init_auth_tables
from backend.services.admin_service import init_admin_tables
from backend.vector_store import seed_chroma_from_sqlite
from semantic_layer import (
    init_schema_metadata_table,
    init_example_table,
    init_semantic_table,
    init_cache_table,
    seed_all_metadata,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title='ChatBI API',
        description='股票查询助手后端API',
        version='2.0.0',
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    image_dir = Path(settings.image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    app.mount('/api/charts', StaticFiles(directory=str(image_dir)), name='charts')

    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(chat.router, dependencies=[Depends(get_current_user)])
    app.include_router(session.router, dependencies=[Depends(get_current_user)])
    app.include_router(chat_stream.router)

    @app.on_event('startup')
    async def startup():
        langchain.llm_cache = SQLiteCache(
            database_path=str(Path(settings.db_path).parent / "llm_cache.db")
        )
        init_schema_metadata_table()
        init_example_table()
        init_semantic_table()
        init_cache_table()
        seed_all_metadata()
        seed_chroma_from_sqlite()
        ensure_app_tables()
        init_auth_tables()
        init_admin_tables()

    @app.get('/api/health')
    async def health():
        return {'status': 'ok'}

    return app


app = create_app()
