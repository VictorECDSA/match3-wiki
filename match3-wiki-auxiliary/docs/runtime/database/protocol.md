# DatabaseEngine Protocol

> **功能**: PostgreSQL 数据访问层 (ORM)  
> **推荐实现**: SQLAlchemy v2.0.48 (2026-03-02)  
> **Runtime 接口**: `rt.db: DatabaseEngine` (Protocol)

## 📚 相关文档

- **上级文档**: [runtime.md](../runtime.md) - Runtime 系统总览和 Protocol 设计理念
- **实现方案**: [implementation.md](./implementation.md) - SQLAlchemy 适配器实现和配置说明
- **版本技术文档**: [versions/](./versions/) - 具体实现库的详细 API 文档
  - [SQLAlchemy v2.0.48](./versions/sqlalchemy-v2.0.48.md) - 推荐实现

---

## Protocol 定义

### 接口说明

`DatabaseEngine` 提供关系型数据库访问能力,用于:
- **数据持久化**: 应用数据的 CRUD 操作
- **事务管理**: ACID 事务保证数据一致性
- **ORM 集成**: 与 SQLAlchemy ORM 模型配合使用

### 主接口定义

```python
from typing import Protocol, ContextManager

class DatabaseEngine(Protocol):
    """数据库引擎抽象接口 (不依赖任何 ORM)"""
    
    def session(self) -> ContextManager[DatabaseSession]:
        """创建数据库会话的上下文管理器
        
        Returns:
            会话上下文管理器,退出时自动提交或回滚
        """
        ...
    
    def dispose(self) -> None:
        """释放连接池资源"""
        ...
```

### 会话 Protocol

```python
from typing import Protocol, Any

class DatabaseSession(Protocol):
    """数据库会话抽象接口 (不依赖任何 ORM)"""
    
    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """执行 SQL 查询
        
        Args:
            query: SQL 查询语句
            params: 查询参数 (可选)
            
        Returns:
            查询结果 (具体类型由实现决定)
        """
        ...
    
    def add(self, entity: Any) -> None:
        """将实体添加到会话 (待提交)
        
        Args:
            entity: 要添加的实体对象
        """
        ...
    
    def commit(self) -> None:
        """提交当前事务"""
        ...
    
    def rollback(self) -> None:
        """回滚当前事务"""
        ...
    
    def close(self) -> None:
        """关闭会话"""
        ...
```

---

## 使用示例

### 业务代码 (创建实体)

```python
from runtime import Runtime

def create_user(rt: Runtime, username: str, email: str) -> None:
    """创建用户 (不知道底层是 SQLAlchemy 还是其他 ORM)"""
    
    with rt.db.session() as session:
        user = User(username=username, email=email)
        session.add(user)
        # 退出 with 块时自动提交
```

### 业务代码 (查询)

```python
def get_user_by_id(rt: Runtime, user_id: int) -> dict | None:
    """根据 ID 查询用户"""
    
    with rt.db.session() as session:
        result = session.execute(
            "SELECT * FROM users WHERE id = :user_id",
            params={"user_id": user_id},
        )
        
        row = result.fetchone()
        if row:
            return dict(row)
        return None
```

### 业务代码 (事务)

```python
def transfer_balance(rt: Runtime, from_user: int, to_user: int, amount: float) -> None:
    """转账操作 (事务保证原子性)"""
    
    with rt.db.session() as session:
        try:
            # 扣除发送者余额
            session.execute(
                "UPDATE users SET balance = balance - :amount WHERE id = :user_id",
                params={"amount": amount, "user_id": from_user},
            )
            
            # 增加接收者余额
            session.execute(
                "UPDATE users SET balance = balance + :amount WHERE id = :user_id",
                params={"amount": amount, "user_id": to_user},
            )
            
            # 自动提交 (退出 with 块时)
        except Exception:
            # 自动回滚 (异常时)
            raise
```

### 单元测试

```python
from unittest.mock import MagicMock
from runtime import Runtime

def test_create_user():
    # Mock 数据库接口
    mock_session = MagicMock()
    mock_engine = MagicMock()
    mock_engine.session.return_value.__enter__.return_value = mock_session
    
    # 创建测试 Runtime
    rt = Runtime(
        cache=MagicMock(),
        queue=MagicMock(),
        vector_db=MagicMock(),
        graph_db=MagicMock(),
        db=mock_engine,
        search=MagicMock(),
        storage=MagicMock(),
    )
    
    # 测试业务逻辑
    create_user(rt, "alice", "alice@example.com")
    
    # 验证调用
    mock_session.add.assert_called_once()
```

---

## 设计说明

### 抽象粒度

- ✅ **好的抽象**: `execute(query: str, params: dict)` (通用)
- ❌ **过度抽象**: `execute(query: SQLAlchemyQuery)` (依赖具体库)

### 返回值类型

Protocol 的返回值应尽量使用:
- 基础类型 (`str`, `int`, `bool`)
- 标准库类型 (`dict`, `list`)
- 自定义领域模型 (不依赖 ORM)

避免返回 SQLAlchemy 特有类型 (如 `Result`、`Row`)。

### 类型检查

推荐使用 Pyright 或 mypy 进行静态类型检查:

```bash
# 检查 Runtime 是否只依赖 Protocol
pyright --verifytypes runtime
```

---

## 扩展性

### 切换到 Django ORM

```python
class DjangoORMAdapter:
    """Django ORM 适配器 (实现 DatabaseEngine Protocol)"""
    
    @contextmanager
    def session(self):
        # Django 使用 transaction.atomic()
        from django.db import transaction
        with transaction.atomic():
            yield DjangoSessionAdapter()
    
    def dispose(self):
        from django.db import connection
        connection.close()
```

**无需修改 Runtime 或业务代码！**

### 添加新方法

如果需要添加查询方法:

```python
class DatabaseSession(Protocol):
    # ... 原有方法 ...
    
    def query(self, model: type) -> Any:
        """查询特定模型 (可选方法)"""
        ...
```

已有代码继续兼容 (Protocol 支持渐进式扩展)。

---

**创建时间**: 2026-04-23  
**最后更新**: 2026-04-23  
**版本**: 2.0
