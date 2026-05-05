from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.models.auth import LoginRequest, LoginResponse, RefreshRequest, RefreshResponse, UserInfoResponse
from backend.models.common import ApiResponse
from backend.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_runtime_user_context,
    verify_token,
)

router = APIRouter(prefix='/api/auth', tags=['auth'])
security = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail='未提供认证信息')
    payload = verify_token(credentials.credentials)
    if not payload or payload.get('type') != 'access':
        raise HTTPException(status_code=401, detail='token无效或已过期')
    user = get_runtime_user_context(payload['sub'])
    if not user:
        raise HTTPException(status_code=401, detail='用户不存在或已被禁用')
    return user


def require_role(required_role: str):
    async def dependency(user: dict = Depends(get_current_user)):
        role = user.get('role', '')
        role_hierarchy = {'superadmin': 3, 'admin': 2, 'user': 1}
        if role_hierarchy.get(role, 0) < role_hierarchy.get(required_role, 0):
            raise HTTPException(status_code=403, detail='无权限访问')
        return user

    return dependency


@router.post('/login', response_model=ApiResponse)
async def login(req: LoginRequest, request: Request):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get('user-agent')
    user = authenticate_user(req.username, req.password, ip_address=ip_address, user_agent=user_agent)
    if not user:
        raise HTTPException(status_code=401, detail='用户名或密码错误')
    access_token = create_access_token(user['username'], user['role'])
    refresh_token = create_refresh_token(user['username'], user['role'])
    data = LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        username=user['username'],
        nickname=user.get('nickname', user['username']),
        role=user['role'],
    )
    return ApiResponse(code=0, message='success', data=data.model_dump())


@router.post('/refresh', response_model=ApiResponse)
async def refresh(req: RefreshRequest):
    payload = verify_token(req.refresh_token)
    if not payload or payload.get('type') != 'refresh':
        raise HTTPException(status_code=401, detail='refresh_token无效或已过期')
    user = get_runtime_user_context(payload['sub'])
    if not user:
        raise HTTPException(status_code=401, detail='用户不存在或已被禁用')
    access_token = create_access_token(user['username'], user['role'])
    return ApiResponse(code=0, message='success', data=RefreshResponse(access_token=access_token).model_dump())


@router.get('/me', response_model=ApiResponse)
async def me(user: dict = Depends(get_current_user)):
    data = UserInfoResponse(
        username=user['username'],
        nickname=user.get('nickname', user['username']),
        role=user['role'],
        status=user['status'],
        last_login_time=user.get('last_login_time'),
    )
    return ApiResponse(code=0, message='success', data=data.model_dump())
