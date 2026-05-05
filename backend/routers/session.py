from fastapi import APIRouter, Depends, HTTPException

from backend.models.chat import (
    ChatMessageItem,
    PinSessionRequest,
    ChatSessionItem,
    CreateSessionRequest,
    CreateSessionResponse,
    RenameSessionRequest,
)
from backend.models.common import ApiResponse
from backend.routers.auth import get_current_user
from backend.services.session_service import (
    create_session,
    delete_session_for_user,
    get_messages,
    list_sessions,
    rename_session_for_user,
    set_session_pinned_for_user,
    user_can_access_session,
)

router = APIRouter(prefix='/api/sessions', tags=['sessions'])


@router.get('', response_model=ApiResponse)
async def get_sessions(user: dict = Depends(get_current_user)):
    sessions = list_sessions(user['username'])
    return ApiResponse(code=0, message='success', data=[ChatSessionItem(**s).model_dump() for s in sessions])


@router.post('', response_model=ApiResponse)
async def post_session(req: CreateSessionRequest, user: dict = Depends(get_current_user)):
    session_id = create_session(user['username'], req.title)
    return ApiResponse(code=0, message='success', data=CreateSessionResponse(session_id=session_id).model_dump())


@router.get('/{session_id}/messages', response_model=ApiResponse)
async def get_session_messages(session_id: str, user: dict = Depends(get_current_user)):
    if not user_can_access_session(session_id, user['username'], user['role'] in {'admin', 'superadmin'}):
        raise HTTPException(status_code=404, detail='会话不存在或无权访问')
    messages = get_messages(session_id)
    return ApiResponse(code=0, message='success', data=[ChatMessageItem(**m).model_dump() for m in messages])


@router.put('/{session_id}/rename', response_model=ApiResponse)
async def put_session_rename(session_id: str, req: RenameSessionRequest, user: dict = Depends(get_current_user)):
    ok = rename_session_for_user(session_id, user['username'], req.title, user['role'] in {'admin', 'superadmin'})
    if not ok:
        raise HTTPException(status_code=404, detail='会话不存在或无权访问')
    return ApiResponse(code=0, message='success', data=None)


@router.post('/{session_id}/pin', response_model=ApiResponse)
async def post_session_pin(session_id: str, req: PinSessionRequest, user: dict = Depends(get_current_user)):
    ok = set_session_pinned_for_user(
        session_id,
        user['username'],
        req.is_pinned,
        user['role'] in {'admin', 'superadmin'},
    )
    if not ok:
        raise HTTPException(status_code=404, detail='会话不存在或无权访问')
    return ApiResponse(code=0, message='success', data={'session_id': session_id, 'is_pinned': req.is_pinned})


@router.delete('/{session_id}', response_model=ApiResponse)
async def delete_session_route(session_id: str, user: dict = Depends(get_current_user)):
    ok = delete_session_for_user(session_id, user['username'], user['role'] in {'admin', 'superadmin'})
    if not ok:
        raise HTTPException(status_code=404, detail='会话不存在或无权访问')
    return ApiResponse(code=0, message='success', data=None)
