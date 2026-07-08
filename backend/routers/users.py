"""
用户认证路由
包含注册、登录、获取用户信息等接口
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from crud import get_user_by_username, get_user_by_email, create_user
from schemas import UserCreate, UserResponse
from database import get_db
from security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from models import User as UserModel

router = APIRouter(prefix="/api/auth", tags=["auth"])


# 请求模型
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


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

    # 创建用户
    user_data = UserCreate(
        username=request.username,
        email=request.email,
        password=request.password
    )
    db_user = create_user(db=db, user=user_data)

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
