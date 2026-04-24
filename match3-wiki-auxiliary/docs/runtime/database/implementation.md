# Database Implementation — PostgreSQL + SQLAlchemy

## 概述

使用 **PostgreSQL** 作为关系型数据库，通过 **SQLAlchemy 2.0** 提供数据访问能力。

---

## 工厂函数

```python
# backend/runtime_impl/implements/database/database.py
from sqlalchemy import create_engine
from backend.config import Config, Env
from backend.runtime.protocols.logger import Logger
from backend.runtime.protocols.database import DatabaseEngine
from .impl_postgresql.postgresql_adapter import PostgreSQLEngine

def create_database_engine(config: Config, env: Env, logger: Logger) -> DatabaseEngine:
    """创建 DatabaseEngine 实例
    
    Args:
        config: 配置对象
        env: 环境变量
        logger: 日志记录器
    
    Returns:
        实现了 DatabaseEngine Protocol 的 PostgreSQLEngine 实例
    
    Raises:
        ValueError: provider 不支持时抛出
    """
    provider = config.runtime.database.provider
    
    if provider == "postgresql":
        postgres_url = (
            f"postgresql+psycopg2://{env.POSTGRESQL_USER}:{env.POSTGRESQL_PASSWORD}"
            f"@{env.POSTGRESQL_HOST}:{env.POSTGRESQL_PORT}/{env.POSTGRESQL_DB}"
        )
        
        db_engine = create_engine(
            postgres_url,
            pool_size=config.runtime.database.implementations.postgresql.pool_size,
            max_overflow=config.runtime.database.implementations.postgresql.max_overflow,
            pool_timeout=config.runtime.database.implementations.postgresql.pool_timeout,
            pool_recycle=config.runtime.database.implementations.postgresql.pool_recycle,
            pool_pre_ping=True,  # 自动检测失效连接
        )
        
        logger.info(f"PostgreSQL engine initialized (pool_size: {config.runtime.database.implementations.postgresql.pool_size})")
        return PostgreSQLEngine(db_engine)
    else:
        raise ValueError(f"Unsupported database provider: {provider}")
```

---

## 适配器实现

```python
# backend/runtime_impl/implements/database/impl_postgresql/postgresql_adapter.py
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from backend.runtime.protocols.database import DatabaseEngine

class PostgreSQLEngine:
    """PostgreSQL + SQLAlchemy 适配器，实现 DatabaseEngine Protocol"""
    
    def __init__(self, engine: Engine):
        self._engine = engine
    
    def get_session(self) -> Session:
        """获取数据库会话
        
        使用示例:
        with rt.db.get_session() as session:
            # 执行数据库操作
            session.commit()
        """
        return Session(self._engine)
    
    def execute(self, query: str, params: dict | None = None):
        """执行原生 SQL 查询"""
        with self._engine.connect() as conn:
            return conn.execute(query, params or {})
    
    def dispose(self):
        """释放连接池"""
        self._engine.dispose()
```

---

## 配置参数

### Config (config.yaml)

```yaml
runtime:
  database:
    provider: postgresql
    implementations:
      postgresql:
        pool_size: 10          # 连接池大小
        max_overflow: 20       # 最大溢出连接数
        pool_timeout: 30       # 连接超时（秒）
        pool_recycle: 3600     # 连接回收时间（秒）
```

### Env (.env)

```bash
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DB=match3
POSTGRESQL_USER=match3_user
POSTGRESQL_PASSWORD=your_secure_password
```

---

## 相关文档

- **[protocol.md](./protocol.md)** — DatabaseEngine Protocol 定义
- **[../../design/solution-final/050-data-model/](../../design/solution-final/050-data-model/)** — 数据模型设计（ORM 模型、迁移脚本等）
