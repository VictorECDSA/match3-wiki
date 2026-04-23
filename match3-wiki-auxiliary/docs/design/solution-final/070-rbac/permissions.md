# RBAC 与权限控制

## 角色

| 角色 | 范围 | 描述 |
|------|------|------|
| `owner` | 工作区 | 完全控制权；创建工作区时自动分配 |
| `admin` | 工作区 | 与 owner 相同，但不能删除工作区本身 |
| `member` | 工作区 | 上传文件、提问、查看 Wiki |
| `viewer` | 工作区 | 只读：提问、查看 Wiki；不能上传 |

角色存储在 `t_workspace_members.f_role` 中。数据模型中没有全局管理员角色——系统级管理操作（工作区 CRUD、统计）在基础设施层面（内网或 API Key 请求头）加以保护，而不通过角色表。

---

## 能力矩阵

| 操作 | owner | admin | member | viewer |
|------|:-----:|:-----:|:------:|:------:|
| 上传文件 | ✓ | ✓ | ✓ | ✗ |
| 删除文件 | ✓ | ✓ | 仅自己 | ✗ |
| 提问（Q&A） | ✓ | ✓ | ✓ | ✓ |
| 查看 Wiki 页面 | ✓ | ✓ | ✓ | ✓ |
| 触发 Wiki 编译 | ✓ | ✓ | ✓ | ✗ |
| 删除 Wiki 页面 | ✓ | ✓ | ✗ | ✗ |
| 添加成员 | ✓ | ✓ | ✗ | ✗ |
| 移除成员 | ✓ | ✓ | ✗ | ✗ |
| 更新工作区 | ✓ | ✓ | ✗ | ✗ |
| 删除工作区 | ✓ | ✗ | ✗ | ✗ |

"仅自己" = 只能删除请求用户自己上传的文件。

---

## 权限校验器

```python
# app/common/permissions.py
from __future__ import annotations
from enum import Enum
from app.common.exceptions import Match3Exception
from app.common.constants import codes


class Action(str, Enum):
    UPLOAD_FILE       = "upload_file"
    DELETE_OWN_FILE   = "delete_own_file"
    DELETE_ANY_FILE   = "delete_any_file"
    ASK_QUESTION      = "ask_question"
    VIEW_WIKI         = "view_wiki"
    COMPILE_WIKI      = "compile_wiki"
    DELETE_WIKI       = "delete_wiki"
    ADD_MEMBER        = "add_member"
    REMOVE_MEMBER     = "remove_member"
    UPDATE_WORKSPACE  = "update_workspace"
    DELETE_WORKSPACE  = "delete_workspace"


# 角色按权限从高到低排列
_ROLE_RANK = {
    "owner":  4,
    "admin":  3,
    "member": 2,
    "viewer": 1,
}

# 各操作所需的最低角色
_REQUIRED_RANK: dict[Action, int] = {
    Action.UPLOAD_FILE:      _ROLE_RANK["member"],
    Action.DELETE_OWN_FILE:  _ROLE_RANK["member"],
    Action.DELETE_ANY_FILE:  _ROLE_RANK["admin"],
    Action.ASK_QUESTION:     _ROLE_RANK["viewer"],
    Action.VIEW_WIKI:        _ROLE_RANK["viewer"],
    Action.COMPILE_WIKI:     _ROLE_RANK["member"],
    Action.DELETE_WIKI:      _ROLE_RANK["admin"],
    Action.ADD_MEMBER:       _ROLE_RANK["admin"],
    Action.REMOVE_MEMBER:    _ROLE_RANK["admin"],
    Action.UPDATE_WORKSPACE: _ROLE_RANK["admin"],
    Action.DELETE_WORKSPACE: _ROLE_RANK["owner"],
}


def require(role: str, action: Action) -> None:
    """
    若角色权限不足，则抛出带有 PERMISSION_DENIED 错误码的 Match3Exception。

    用法：
        require(member.role, Action.UPLOAD_FILE)

    这是一个纯函数，不涉及数据库调用——调用方负责提前加载 WorkspaceMember 记录。
    """
    rank = _ROLE_RANK.get(role, 0)
    required = _REQUIRED_RANK[action]
    if rank < required:
        raise Match3Exception.of_code(
            codes.PERMISSION_DENIED,
            "unauthorized insufficient role for action",
        ).ctx(role=role, action=action.value)
```

---

## 工作区隔离

每个数据库查询都在 WHERE 子句中包含 `workspace_id`。即使用户提供了不匹配的 ID，也绝不会返回跨工作区的数据。

```python
# 示例：文件列表查询始终限定在工作区范围内
def find_paginated(self, workspace_id: str, ...) -> tuple[list[RawFile], int]:
    base = select(RawFile).where(
        RawFile.workspace_id == workspace_id,   # 必须始终包含
        RawFile.delete_time.is_(None),
    )
    ...
```

Milvus 查询在每个标量过滤表达式中包含 `workspace_id == "{workspace_id}"`。Neo4j 查询在每个 MATCH 子句中包含 `workspace_id = $workspace_id`。

---

## 成员校验辅助函数

需要在操作前验证用户是否属于某个工作区的服务使用：

```python
# app/common/permissions.py  (continued)
from app.storage.repositories.workspace_member_repo import WorkspaceMemberRepository
from sqlalchemy import Engine


def get_member_or_raise(
    engine: Engine,
    user_id: str,
    workspace_id: str,
) -> "WorkspaceMember":
    """
    加载 (user_id, workspace_id) 对应的 WorkspaceMember。
    若不存在，则抛出带有 WORKSPACE_NOT_MEMBER 错误码的 Match3Exception。
    """
    from app.storage.entities.workspace_member import WorkspaceMember as WM
    repo = WorkspaceMemberRepository(engine)
    member = repo.find_by_user_workspace(user_id, workspace_id)
    if not member:
        raise Match3Exception.of_code(
            codes.WORKSPACE_NOT_MEMBER,
            "unauthorized user is not a member of workspace",
        ).ctx(user_id=user_id, workspace_id=workspace_id)
    return member
```

在 Service 方法中的用法：

```python
def upload_file(self, workspace_id: str, user_id: str, ...) -> RawFileResp:
    member = get_member_or_raise(self._rt.db_engine, user_id, workspace_id)
    require(member.role, Action.UPLOAD_FILE)
    ...
```

---

## 认证错误业务码

定义在 `app/common/constants/codes.py` 中：

```python
# 以下业务码定义于 app/common/constants/codes.py（权威来源）。
# 此处仅供参考——请勿在其他地方重复定义。
WORKSPACE_NOT_FOUND  = 404001   # 404xxx：资源未找到类错误码
WORKSPACE_NOT_MEMBER = 404006   # 404xxx：资源未找到类错误码
PERMISSION_DENIED    = 401003   # 401xxx：认证类错误码（工作区操作权限不足）
```

这些业务码在 `ApiResp.code` 字段中返回，并在 SSE 错误事件中发送。

---

## Admin 端点

Admin API（`/api/v1/admin/...`）执行工作区和成员管理，无需检查工作区成员资格。它仅供后台管理面板使用，**绝不能**暴露在公网上。可通过以下方式保护：

- nginx 在 `/api/v1/admin` location 块上配置 `allow 10.0.0.0/8; deny all;`，或
- 在 FastAPI 依赖中校验共享密钥请求头：

```python
# app/api/deps/admin_auth.py
from fastapi import Header, HTTPException, Request


async def require_admin_key(
    request: Request,
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
) -> None:
    rt = request.app.state.rt
    if x_admin_key != rt.env.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
```

将该依赖添加到每个 Admin 路由端点：

```python
router.post(
    "/admin/workspaces",
    response_model=ApiResp[WorkspaceResp],
    dependencies=[Depends(require_admin_key)],
)(api.create_workspace)
```
