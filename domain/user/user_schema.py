from pydantic import BaseModel, field_validator, EmailStr
from pydantic_core.core_schema import FieldValidationInfo
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    name: str
    passwd1: str
    passwd2: str
    email: EmailStr

    @field_validator('name', 'passwd1', 'passwd2', 'email')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Blank entries are not allowed.")
        return v

    @field_validator('passwd2')
    def passwd_check(cls, v, info: FieldValidationInfo):
        if 'passwd1' in info.data and v != info.data['passwd1']:
            raise ValueError("Password does not match.")
        return v


class AccountRequestCreate(BaseModel):
    name: str
    email: EmailStr
    passwd1: str
    passwd2: str
    message: Optional[str] = None

    @field_validator('name', 'passwd1', 'passwd2')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Blank entries are not allowed.")
        return v

    @field_validator('passwd2')
    def passwd_check(cls, v, info: FieldValidationInfo):
        if 'passwd1' in info.data and v != info.data['passwd1']:
            raise ValueError("Password does not match.")
        return v


class AccountRequestResponse(BaseModel):
    id: int
    name: str
    email: str
    message: Optional[str] = None
    created_at: datetime
    status: str

    class Config:
        from_attributes = True


class UserUpdateName(BaseModel):
    new_name: str
    password: str

    @field_validator('new_name', 'password')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Blank entries are not allowed.")
        return v


class UserUpdateEmail(BaseModel):
    new_email: EmailStr
    password: str

    @field_validator('password')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Blank entries are not allowed.")
        return v


class UserUpdatePassword(BaseModel):
    current_password: str
    new_password: str
    new_password2: str

    @field_validator('current_password', 'new_password', 'new_password2')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Blank entries are not allowed.")
        return v

    @field_validator('new_password2')
    def passwd_check(cls, v, info: FieldValidationInfo):
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError("Password does not match.")
        return v


class UserDelete(BaseModel):
    password: str

    @field_validator('password')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Blank entries are not allowed.")
        return v


class UserVerifyPassword(BaseModel):
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    is_admin: bool
    failed_login: int
    locked_until: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_dormant: bool = False
    profile_image: Optional[str] = None
    storage_path: Optional[str] = None
    storage_limit: Optional[int] = None

    class Config:
        from_attributes = True
