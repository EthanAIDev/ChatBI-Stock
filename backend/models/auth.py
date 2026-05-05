from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    username: str
    nickname: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description='刷新token')


class RefreshResponse(BaseModel):
    access_token: str


class UserInfoResponse(BaseModel):
    username: str
    nickname: str
    role: str
    status: str
    last_login_time: str | None = None
