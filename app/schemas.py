from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
import uuid

class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

class UserCreate(UserBase):
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Пароль должен содержать минимум 6 символов')
        if len(v) > 128:
            raise ValueError('Пароль слишком длинный (максимум 128 символов)')
        return v

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserInDB(UserResponse):
    hashed_password: str

# Схемы для аутентификации
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

# Схемы для Job
class JobBase(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    file_type: Optional[str] = "single"  # single, zip

class JobCreate(JobBase):
    pass

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class JobResponse(JobBase):
    id: int
    uuid: uuid.UUID
    status: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_content_type: Optional[str] = None
    file_type: Optional[str] = "single"
    zip_contents: Optional[str] = None  # JSON строка с содержимым ZIP архива
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class JobWithOwner(JobResponse):
    owner: UserResponse
