# ORM（对象关系映射）

**ORM（Object-Relational Mapping，对象关系映射）** 是一种将面向对象语言中的类与关系数据库中的表一一对应的技术，使开发者可以用操作对象的方式操作数据库，无需手写 SQL。本项目使用 SQLAlchemy 2.0 的声明式 ORM（Declarative ORM）。

## 核心思想

ORM 建立三层映射：

```
Python 类  ←→  数据库表
类的属性   ←→  表的列
类的实例   ←→  表中的一行记录
```

## SQLAlchemy 2.0 的模型定义

SQLAlchemy 2.0 引入了类型注解风格（`Mapped[T]`），比旧版更简洁且 IDE 友好：

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class RawFile(Base):
    __tablename__ = "t_raw_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

## ORM vs 原始 SQL

| 特性 | ORM | 原始 SQL |
|------|-----|----------|
| 开发效率 | 高（类型安全，IDE 补全） | 低（字符串拼接易出错） |
| 复杂查询 | 受限（需 fallback 到 SQL） | 灵活 |
| 迁移支持 | ✓（Alembic 自动生成 DDL） | 手动维护 |
| 性能 | 轻微开销（对象构建） | 最优 |

## 关系加载

ORM 中关联查询（如一个文件对应多个 TextChunk）的加载策略见 [loading/](./loading/)，N+1 问题见 [N+1.md](./N+1.md)。
