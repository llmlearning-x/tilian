"""
用户认证路由
包含注册、登录、获取用户信息等接口
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from crud import get_user_by_username, get_user_by_email
from schemas import UserResponse
from database import get_db
from security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from models import User as UserModel, InvitationCode

router = APIRouter(prefix="/api/auth", tags=["auth"])


# 请求模型
class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    invite_code: str


# 响应模型
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserLogin(BaseModel):
    id: int
    username: str
    email: str


@router.post("/register", response_model=Token)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    用户注册

    Args:
        request: 注册请求（用户名、邮箱、密码）
        db: 数据库会话

    Returns:
        Token 和用户信息

    Raises:
        HTTPException: 用户名或邮箱已存在
    """
    # 检查用户名是否存在
    db_user = get_user_by_username(db, username=request.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    # 检查邮箱是否存在
    db_user = get_user_by_email(db, email=request.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )

    # 校验邀请码（存在、未使用、未过期、未禁用）
    invite_code = (
        db.query(InvitationCode)
        .filter(InvitationCode.code == request.invite_code.strip())
        .with_for_update()
        .first()
    )
    now = datetime.utcnow()
    if not invite_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码无效"
        )
    if not invite_code.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已被禁用"
        )
    if invite_code.used_by is not None or invite_code.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已被使用"
        )
    if invite_code.expires_at is not None and invite_code.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已过期"
        )

    # 创建用户并标记邀请码已使用（同一事务）
    db_user = UserModel(
        username=request.username,
        email=request.email,
        hashed_password=get_password_hash(request.password),
        role="student",
    )
    db.add(db_user)
    db.flush()  # 获取 db_user.id

    invite_code.used_by = db_user.id
    invite_code.used_at = now
    db.add(invite_code)

    db.commit()
    db.refresh(db_user)

    # 生成 Token
    access_token = create_access_token(data={"sub": str(db_user.id)})

    return Token(
        access_token=access_token,
        user=UserResponse(
            id=db_user.id,
            username=db_user.username,
            email=db_user.email,
            role=db_user.role,
            is_active=db_user.is_active,
            created_at=db_user.created_at
        )
    )


@router.post("/login", response_model=Token)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    用户登录

    Args:
        request: 登录请求（用户名、密码）
        db: 数据库会话

    Returns:
        Token 和用户信息

    Raises:
        HTTPException: 用户名或密码错误
    """
    # 查找用户
    user = db.query(UserModel).filter(UserModel.username == request.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # 验证密码
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # 检查用户是否活跃
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被禁用"
        )

    # 生成 Token
    access_token = create_access_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at
        )
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
):
    """
    修改当前登录用户密码
    """
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码错误"
        )
    current_user.hashed_password = get_password_hash(request.new_password)
    db.commit()
    return {"message": "密码修改成功"}


@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: UserModel = Depends(get_current_active_user)):
    """
    获取当前用户信息

    Args:
        current_user: 当前认证用户

    Returns:
        用户信息
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )


# OAuth2 兼容的登录端点（可选）
@router.post("/token", response_model=Token)
async def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2 标准的登录端点

    Args:
        form_data: OAuth2 表单数据
        db: 数据库会话

    Returns:
        Token 和用户信息
    """
    user = db.query(UserModel).filter(UserModel.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at
        )
    )
