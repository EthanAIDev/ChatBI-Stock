from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    message: str = 'success'
    data: object = None


class ErrorResponse(BaseModel):
    code: int = -1
    message: str = 'error'
    data: None = None
