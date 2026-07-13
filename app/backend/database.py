"""
数据库配置与连接管理
支持 SQLite（开发）、MySQL（生产）和 PostgreSQL（生产）
"""
import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from config import settings

# 数据库连接URL
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# 创建引擎 - 根据数据库类型设置不同参数
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True
    )

# 创建SessionLocal类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建Base类
Base = declarative_base()


# 数据库依赖项
def get_db():
    """
    获取数据库会话（依赖注入）

    Yields:
        数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化数据库（创建所有表）
    注意：生产环境应使用 Alembic 迁移
    """
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        _migrate_sqlite_compatibility()
    Base.metadata.create_all(bind=engine)


def _migrate_sqlite_compatibility():
    """Add non-destructive MVP columns to existing development databases."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    statements = []
    if "users" in table_names:
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "role" not in columns:
            statements.append("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'student'")
    if "question_banks" in table_names:
        columns = {column["name"] for column in inspector.get_columns("question_banks")}
        if "source_type" not in columns:
            statements.append("ALTER TABLE question_banks ADD COLUMN source_type VARCHAR(20) NOT NULL DEFAULT 'document'")
        if "status" not in columns:
            statements.append("ALTER TABLE question_banks ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'ready'")
    if "questions" in table_names:
        columns = {column["name"] for column in inspector.get_columns("questions")}
        if "source_type" not in columns:
            statements.append("ALTER TABLE questions ADD COLUMN source_type VARCHAR(20) NOT NULL DEFAULT 'manual'")
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
    with engine.begin() as connection:
        if "question_banks" in table_names:
            connection.execute(text("UPDATE question_banks SET source_type='platform', owner_id=NULL WHERE is_public=1"))
        if "quiz_items" in table_names:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_quiz_items_question_submitted ON quiz_items (question_id, submitted_at)"))
        if "user_question_stats" in table_names:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_user_question_stats_user_wrong_mastered ON user_question_stats (user_id, wrong_count, is_mastered)"))
