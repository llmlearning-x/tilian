import os
import sys
from alembic import context
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import OperationalError

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.database import SQLALCHEMY_DATABASE_URL, Base
from backend.models import User, KnowledgePoint, QuestionBank, Question

# Alembic配置
config = context.config

# 设置目标元数据
target_metadata = Base.metadata

def run_migrations_offline():
    """Offline模式运行迁移"""
    url = SQLALCHEMY_DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Online模式运行迁移"""
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = SQLALCHEMY_DATABASE_URL
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()