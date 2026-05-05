from fastapi import APIRouter, Depends, HTTPException, Query

from backend.models.admin import (
    CreateUserRequest,
    PinSessionRequest,
    ResetPasswordResponse,
    UpdateModelSettingsRequest,
    UpdatePromptTemplatesRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
)
from backend.models.common import ApiResponse
from backend.routers.auth import require_role
from backend.services.admin_service import (
    create_admin_user,
    delete_admin_session,
    get_admin_overview,
    get_admin_session_detail,
    get_admin_user_by_id,
    get_prompt_templates,
    get_runtime_model_settings,
    list_admin_action_logs,
    list_admin_login_logs,
    list_admin_sessions,
    list_admin_users,
    list_query_audits,
    log_admin_action,
    reset_admin_user_password,
    set_session_pinned,
    update_admin_user_role,
    update_admin_user_status,
    update_prompt_templates,
    update_runtime_model_settings,
)

admin_required = require_role('admin')
router = APIRouter(prefix='/api/admin', tags=['admin'])


@router.get('/overview', response_model=ApiResponse, dependencies=[Depends(admin_required)])
async def get_overview():
    return ApiResponse(code=0, message='success', data=get_admin_overview())


@router.post('/users', response_model=ApiResponse)
async def post_user(req: CreateUserRequest, user: dict = Depends(admin_required)):
    try:
        created = create_admin_user(
            username=req.username,
            password=req.password,
            nickname=req.nickname,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    log_admin_action(
        user['username'],
        user['role'],
        'create_user',
        'user',
        str(created['id']),
        created['username'],
        {'nickname': created['nickname']},
    )
    return ApiResponse(code=0, message='success', data=created)


@router.get('/users', response_model=ApiResponse, dependencies=[Depends(admin_required)])
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
):
    return ApiResponse(code=0, message='success', data=list_admin_users(page, page_size, keyword, role, status))


@router.patch('/users/{user_id}/status', response_model=ApiResponse)
async def patch_user_status(
    user_id: int,
    req: UpdateUserStatusRequest,
    user: dict = Depends(admin_required),
):
    try:
        updated = update_admin_user_status(user_id, req.status)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail='用户不存在')
    log_admin_action(
        user['username'],
        user['role'],
        'update_user_status',
        'user',
        str(user_id),
        updated['username'],
        {'status': req.status},
    )
    return ApiResponse(code=0, message='success', data=updated)


@router.patch('/users/{user_id}/role', response_model=ApiResponse)
async def patch_user_role(
    user_id: int,
    req: UpdateUserRoleRequest,
    user: dict = Depends(admin_required),
):
    try:
        updated = update_admin_user_role(user_id, req.role, actor_role=user['role'])
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail='用户不存在')
    log_admin_action(
        user['username'],
        user['role'],
        'update_user_role',
        'user',
        str(user_id),
        updated['username'],
        {'role': req.role},
    )
    return ApiResponse(code=0, message='success', data=updated)


@router.post('/users/{user_id}/reset-password', response_model=ApiResponse)
async def post_user_reset_password(user_id: int, user: dict = Depends(admin_required)):
    target = get_admin_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail='用户不存在')
    try:
        updated, temporary_password = reset_admin_user_password(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    log_admin_action(
        user['username'],
        user['role'],
        'reset_user_password',
        'user',
        str(user_id),
        target['username'],
        {},
    )
    return ApiResponse(
        code=0,
        message='success',
        data=ResetPasswordResponse(temporary_password=temporary_password).model_dump(),
    )


@router.get('/login-logs', response_model=ApiResponse, dependencies=[Depends(admin_required)])
async def get_login_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    username: str | None = None,
    success: int | None = Query(None, ge=0, le=1),
    start_time: str | None = None,
    end_time: str | None = None,
):
    data = list_admin_login_logs(page, page_size, username, success, start_time, end_time)
    return ApiResponse(code=0, message='success', data=data)


@router.get('/action-logs', response_model=ApiResponse, dependencies=[Depends(admin_required)])
async def get_action_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
):
    data = list_admin_action_logs(page, page_size, keyword, start_time, end_time)
    return ApiResponse(code=0, message='success', data=data)


@router.get('/sessions', response_model=ApiResponse, dependencies=[Depends(admin_required)])
async def get_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str | None = None,
    user_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    is_pinned: bool | None = None,
):
    data = list_admin_sessions(page, page_size, keyword, user_id, start_time, end_time, is_pinned)
    return ApiResponse(code=0, message='success', data=data)


@router.get('/sessions/{session_id}', response_model=ApiResponse, dependencies=[Depends(admin_required)])
async def get_session_detail(session_id: str):
    detail = get_admin_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail='会话不存在')
    return ApiResponse(code=0, message='success', data=detail)


@router.delete('/sessions/{session_id}', response_model=ApiResponse)
async def delete_session(session_id: str, user: dict = Depends(admin_required)):
    detail = get_admin_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail='会话不存在')
    ok = delete_admin_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail='会话不存在')
    log_admin_action(
        user['username'],
        user['role'],
        'delete_session',
        'session',
        session_id,
        detail['session']['title'],
        {'session_user': detail['session']['user_id']},
    )
    return ApiResponse(code=0, message='success', data=None)


@router.post('/sessions/{session_id}/pin', response_model=ApiResponse)
async def pin_session(session_id: str, req: PinSessionRequest, user: dict = Depends(admin_required)):
    detail = get_admin_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail='会话不存在')
    ok = set_session_pinned(session_id, req.is_pinned)
    if not ok:
        raise HTTPException(status_code=404, detail='会话不存在')
    log_admin_action(
        user['username'],
        user['role'],
        'pin_session' if req.is_pinned else 'unpin_session',
        'session',
        session_id,
        detail['session']['title'],
        {'is_pinned': req.is_pinned},
    )
    return ApiResponse(code=0, message='success', data={'session_id': session_id, 'is_pinned': req.is_pinned})


@router.get('/query-audits', response_model=ApiResponse, dependencies=[Depends(admin_required)])
async def get_query_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    username: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
):
    data = list_query_audits(page, page_size, username, session_id, status, keyword, start_time, end_time)
    return ApiResponse(code=0, message='success', data=data)


@router.get('/model-settings', response_model=ApiResponse, dependencies=[Depends(admin_required)])
async def get_model_settings():
    return ApiResponse(code=0, message='success', data=get_runtime_model_settings())


@router.put('/model-settings', response_model=ApiResponse)
async def put_model_settings(req: UpdateModelSettingsRequest, user: dict = Depends(admin_required)):
    data = update_runtime_model_settings(req.model_dump())
    log_admin_action(
        user['username'],
        user['role'],
        'update_model_settings',
        'system_setting',
        'model_settings',
        '模型配置',
        req.model_dump(),
    )
    return ApiResponse(code=0, message='success', data=data)


@router.get('/prompt-templates', response_model=ApiResponse, dependencies=[Depends(admin_required)])
async def get_templates():
    return ApiResponse(code=0, message='success', data=get_prompt_templates())


@router.put('/prompt-templates', response_model=ApiResponse)
async def put_prompt_templates(req: UpdatePromptTemplatesRequest, user: dict = Depends(admin_required)):
    data = update_prompt_templates([item.model_dump() for item in req.templates])
    log_admin_action(
        user['username'],
        user['role'],
        'update_prompt_templates',
        'prompt_template',
        'prompt_templates',
        'Prompt 模板',
        {'template_keys': [item.template_key for item in req.templates]},
    )
    return ApiResponse(code=0, message='success', data=data)
