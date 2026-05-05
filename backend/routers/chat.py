from fastapi import APIRouter, Depends, HTTPException

from backend.models.chat import ChatQueryRequest, ChatQueryResponse
from backend.models.common import ApiResponse
from backend.routers.auth import get_current_user
from backend.services.chat_service import execute_chat_for_session
from backend.services.session_service import user_can_access_session

router = APIRouter(prefix='/api/chat', tags=['chat'])


@router.post('/query', response_model=ApiResponse)
async def query(req: ChatQueryRequest, user: dict = Depends(get_current_user)):
    is_admin = user['role'] in {'admin', 'superadmin'}
    if not user_can_access_session(req.session_id, user['username'], is_admin):
        raise HTTPException(status_code=404, detail='会话不存在或无权访问')
    try:
        result = execute_chat_for_session(req.session_id, req.question, user['username'])
        return ApiResponse(
            code=0,
            message='success',
            data=ChatQueryResponse(
                content=result['content'],
                sql_text=result.get('sql_text'),
                result_preview=result.get('result_preview'),
                chart_url=result.get('chart_path'),
                from_cache=result.get('from_cache', False),
            ).model_dump(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
