"""
应用配置
支持环境变量和 .env 文件
"""
import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置类"""

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./aiquiz.db"

    # JWT 认证配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 天

    # Redis 配置（可选）
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI Provider 配置
    # 默认使用本地 Kimi / Moonshot 环境变量；也可在 .env 中显式覆盖
    LLM_PROVIDER: str = "moonshot"
    LLM_API_URL: str = "https://api.moonshot.cn/v1/chat/completions"
    LLM_API_KEY: str = Field(default_factory=lambda: os.getenv("MOONSHOT_API_KEY", ""))
    LLM_MODEL: str = "moonshot-v1-8k"
    # DeepAgents 题库整理 Agent 专用模型，建议 32k 以上上下文
    AGENT_LLM_MODEL: str = Field(default_factory=lambda: os.getenv("AGENT_LLM_MODEL", "moonshot-v1-32k"))

    # 文件上传
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024

    # 应用配置
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api"

    # CORS 配置
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例

    Returns:
        Settings: 配置对象
    """
    return Settings()


# 导出设置实例
settings = get_settings()
