# Redis v8.6.2

**Version**: 8.6.2  
**Release Date**: 2026-03-24  
**Category**: In-Memory Data Store & Cache  
**License**: Redis Source Available License 2.0 (RSALv2)

**重要更新** (8.6.x 系列):
- 🔒 **安全修复**: 修复数据注入攻击漏洞 (8.4.x 及更早版本受影响)
- 🆕 **新功能**: Streams 幂等性保证 (XADD IDMP 参数)
- 🆕 **新命令**: HOTKEYS (热键检测), XNACK (释放待处理消息)
- 🆕 **驱逐策略**: volatile-lrm, allkeys-lrm (最近最少修改)
- ⚡ **性能优化**: I/O 线程处理主从客户端, Fork 子进程 CoW 优化
- 🔧 **行为变更**: HSETEX/HGETEX 参数验证加强, HOTKEYS 响应格式变更 (RESP3)

**兼容性**: redis-py 5.3.0+ 完全兼容 Redis 8.6.x

---

## API Interface Overview

### 1. Client Connection

```python
from redis.asyncio import Redis

async def connect(
    host: str = "localhost",       # Redis server hostname or IP
    port: int = 6379,              # Redis server port
    db: int = 0,                   # Database number (0-15)
    password: str | None = None,   # Authentication password
    decode_responses: bool = True, # Auto-decode bytes to str
    max_connections: int = 50,     # Max connections in pool
    socket_timeout: float = 5.0,   # Socket operation timeout in seconds
    socket_connect_timeout: float = 5.0, # Connection timeout
    retry_on_timeout: bool = True, # Retry on timeout errors
    health_check_interval: int = 30 # Health check interval in seconds
) -> Redis:
    """Create async Redis client with connection pool"""
```

### 2. String Operations

```python
async def set(
    key: str,                      # Key name
    value: str | int | float,      # Value to store
    ex: int | None = None,         # Expiration in seconds
    px: int | None = None,         # Expiration in milliseconds
    nx: bool = False,              # Only set if key doesn't exist
    xx: bool = False               # Only set if key exists
) -> bool:
    """Set key to value with optional expiration"""

async def get(
    key: str                       # Key name
) -> str | None:
    """Get value by key"""

async def mget(
    keys: list[str]                # List of key names
) -> list[str | None]:
    """Get multiple values at once"""

async def incr(
    key: str,                      # Key name (must be integer)
    amount: int = 1                # Increment amount
) -> int:
    """Increment integer value atomically"""

async def delete(
    *keys: str                     # One or more keys to delete
) -> int:
    """Delete one or more keys, returns count of deleted keys"""
```

### 3. Hash Operations

```python
async def hset(
    name: str,                     # Hash name
    key: str,                      # Field name
    value: str,                    # Field value
    mapping: dict | None = None    # Multiple field-value pairs
) -> int:
    """Set hash field(s), returns count of fields added"""

async def hget(
    name: str,                     # Hash name
    key: str                       # Field name
) -> str | None:
    """Get hash field value"""

async def hgetall(
    name: str                      # Hash name
) -> dict[str, str]:
    """Get all fields and values in hash"""

async def hdel(
    name: str,                     # Hash name
    *keys: str                     # One or more field names to delete
) -> int:
    """Delete hash field(s), returns count deleted"""

async def hincrby(
    name: str,                     # Hash name
    key: str,                      # Field name (must be integer)
    amount: int = 1                # Increment amount
) -> int:
    """Increment integer field atomically"""
```

### 4. List Operations

```python
async def lpush(
    name: str,                     # List name
    *values: str                   # Values to push (from left)
) -> int:
    """Push value(s) to head of list, returns new length"""

async def rpush(
    name: str,                     # List name
    *values: str                   # Values to push (from right)
) -> int:
    """Push value(s) to tail of list, returns new length"""

async def lpop(
    name: str,                     # List name
    count: int | None = None       # Number of elements to pop
) -> str | list[str] | None:
    """Pop value(s) from head of list"""

async def lrange(
    name: str,                     # List name
    start: int,                    # Start index (0-based)
    end: int                       # End index (-1 for last)
) -> list[str]:
    """Get range of elements from list"""

async def llen(
    name: str                      # List name
) -> int:
    """Get length of list"""
```

### 5. Set Operations

```python
async def sadd(
    name: str,                     # Set name
    *values: str                   # Values to add
) -> int:
    """Add member(s) to set, returns count added"""

async def srem(
    name: str,                     # Set name
    *values: str                   # Values to remove
) -> int:
    """Remove member(s) from set, returns count removed"""

async def smembers(
    name: str                      # Set name
) -> set[str]:
    """Get all members of set"""

async def sismember(
    name: str,                     # Set name
    value: str                     # Value to check
) -> bool:
    """Check if value is member of set"""

async def sinter(
    *keys: str                     # Set names to intersect
) -> set[str]:
    """Get intersection of multiple sets"""

async def sunion(
    *keys: str                     # Set names to union
) -> set[str]:
    """Get union of multiple sets"""
```

### 6. Sorted Set Operations

```python
async def zadd(
    name: str,                     # Sorted set name
    mapping: dict[str, float],     # {member: score, ...}
    nx: bool = False,              # Only add new members
    xx: bool = False               # Only update existing members
) -> int:
    """Add member(s) with scores to sorted set"""

async def zrange(
    name: str,                     # Sorted set name
    start: int,                    # Start rank (0-based)
    end: int,                      # End rank (-1 for last)
    withscores: bool = False       # Include scores in result
) -> list[str] | list[tuple[str, float]]:
    """Get members by rank range (ascending)"""

async def zrevrange(
    name: str,                     # Sorted set name
    start: int,                    # Start rank
    end: int,                      # End rank
    withscores: bool = False       # Include scores
) -> list[str] | list[tuple[str, float]]:
    """Get members by rank range (descending)"""

async def zrangebyscore(
    name: str,                     # Sorted set name
    min: float,                    # Minimum score (inclusive)
    max: float,                    # Maximum score (inclusive)
    withscores: bool = False       # Include scores
) -> list[str] | list[tuple[str, float]]:
    """Get members by score range"""

async def zrem(
    name: str,                     # Sorted set name
    *values: str                   # Members to remove
) -> int:
    """Remove member(s) from sorted set"""

async def zincrby(
    name: str,                     # Sorted set name
    amount: float,                 # Increment amount
    value: str                     # Member to increment
) -> float:
    """Increment member's score atomically"""
```

### 7. Expiration & TTL

```python
async def expire(
    name: str,                     # Key name
    time: int                      # TTL in seconds
) -> bool:
    """Set expiration time for key"""

async def expireat(
    name: str,                     # Key name
    when: int                      # Unix timestamp (seconds)
) -> bool:
    """Set expiration time as absolute timestamp"""

async def ttl(
    name: str                      # Key name
) -> int:
    """Get remaining TTL in seconds (-1 if no expiration, -2 if not exists)"""

async def persist(
    name: str                      # Key name
) -> bool:
    """Remove expiration from key"""
```

### 8. Pipeline & Transaction

```python
async def pipeline(
    transaction: bool = True       # Use MULTI/EXEC transaction
) -> Pipeline:
    """Create pipeline for batching commands"""

# Usage:
async with redis.pipeline(transaction=True) as pipe:
    pipe.set("key1", "value1")
    pipe.set("key2", "value2")
    pipe.incr("counter")
    results = await pipe.execute()  # Execute all commands atomically
```

### 9. Pub/Sub Operations

```python
async def publish(
    channel: str,                  # Channel name
    message: str                   # Message to publish
) -> int:
    """Publish message to channel, returns subscriber count"""

async def subscribe(
    *channels: str                 # Channel names to subscribe
) -> PubSub:
    """Subscribe to channel(s)"""

# Usage:
pubsub = redis.pubsub()
await pubsub.subscribe("notifications")
async for message in pubsub.listen():
    if message["type"] == "message":
        print(message["data"])
```

### 10. Runtime Interface (Match3 Project)

```python
from typing import Protocol
from redis.asyncio import Redis

class IRedisClient(Protocol):
    """Redis client interface for dependency injection"""
    
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ex: int | None = None) -> bool: ...
    async def delete(self, *keys: str) -> int: ...
    async def hget(self, name: str, key: str) -> str | None: ...
    async def hgetall(self, name: str) -> dict[str, str]: ...
    async def hset(self, name: str, key: str, value: str) -> int: ...
    async def zadd(self, name: str, mapping: dict[str, float]) -> int: ...
    async def zrange(self, name: str, start: int, end: int, withscores: bool = False) -> list: ...
    async def expire(self, name: str, time: int) -> bool: ...
    async def pipeline(self, transaction: bool = True) -> Redis: ...
```

---

## Detailed Interface Usage

### 1. Client Connection

#### Basic Async Connection

```python
from redis.asyncio import Redis

# Create async client
redis = await Redis(
    host="localhost",
    port=6379,
    db=0,                          # Database 0 (0-15 available)
    password=None,                 # No password for local dev
    decode_responses=True,         # Auto-decode bytes to str
    max_connections=50,            # Connection pool size
    socket_timeout=5.0,            # 5s socket timeout
    socket_connect_timeout=5.0,    # 5s connect timeout
    retry_on_timeout=True,         # Retry on timeout
    health_check_interval=30       # Health check every 30s
)

# Test connection
pong = await redis.ping()
print(f"Connected: {pong}")  # True

# Always close when done
await redis.close()
```

#### Context Manager (Recommended)

```python
async with Redis(host="localhost", port=6379, decode_responses=True) as redis:
    await redis.set("key", "value")
    value = await redis.get("key")
```

#### Connection Pool (Production)

```python
from redis.asyncio import ConnectionPool, Redis

# Create connection pool
pool = ConnectionPool(
    host="localhost",
    port=6379,
    db=0,
    password="your_password",
    max_connections=100,           # Max pool size
    decode_responses=True
)

# Create client from pool
redis = Redis(connection_pool=pool)

# Multiple clients can share same pool
redis2 = Redis(connection_pool=pool)

# Close pool when app shuts down
await pool.disconnect()
```

#### Sentinel (High Availability)

```python
from redis.asyncio.sentinel import Sentinel

sentinel = Sentinel(
    [("sentinel1", 26379), ("sentinel2", 26379)],  # Sentinel nodes
    socket_timeout=0.1
)

# Get master client
redis = await sentinel.master_for(
    "mymaster",                    # Service name in sentinel config
    socket_timeout=0.1,
    password="password"
)
```

---

### 2. String Operations (Basic Key-Value)

#### Set and Get

```python
# Simple set
await redis.set("username", "alice")
username = await redis.get("username")  # "alice"

# Set with expiration (cache pattern)
await redis.set("session:abc123", "user_data", ex=3600)  # Expires in 1 hour

# Set only if not exists (lock pattern)
success = await redis.set("lock:resource", "owner1", nx=True, ex=10)
if success:
    # Got the lock, do work
    pass
else:
    # Lock already held
    pass
```

#### Batch Get (MGET)

```python
# Set multiple keys
await redis.set("user:1:name", "Alice")
await redis.set("user:2:name", "Bob")
await redis.set("user:3:name", "Charlie")

# Get all at once
names = await redis.mget(["user:1:name", "user:2:name", "user:3:name"])
print(names)  # ["Alice", "Bob", "Charlie"]
```

#### Atomic Increment (Counters)

```python
# Page view counter
await redis.set("page:home:views", 0)
await redis.incr("page:home:views")      # 1
await redis.incr("page:home:views")      # 2
await redis.incrby("page:home:views", 10)  # 12

# Get current count
views = await redis.get("page:home:views")  # "12"
```

#### String Manipulation

```python
# Append to string
await redis.set("log", "start")
await redis.append("log", " middle")     # "start middle"
await redis.append("log", " end")        # "start middle end"

# Get substring
substring = await redis.getrange("log", 0, 4)  # "start"
```

---

### 3. Hash Operations (Object Storage)

#### Store Object as Hash

```python
# Store user object
await redis.hset(
    "user:1001",
    mapping={
        "name": "Alice",
        "email": "alice@example.com",
        "age": "30",
        "city": "New York"
    }
)

# Get single field
name = await redis.hget("user:1001", "name")  # "Alice"

# Get all fields
user = await redis.hgetall("user:1001")
# {"name": "Alice", "email": "alice@example.com", "age": "30", "city": "New York"}
```

#### Update Fields

```python
# Update single field
await redis.hset("user:1001", "city", "San Francisco")

# Update multiple fields
await redis.hset("user:1001", mapping={"age": "31", "city": "Boston"})

# Increment numeric field
await redis.hincrby("user:1001", "login_count", 1)
```

#### Delete Fields

```python
# Delete specific fields
await redis.hdel("user:1001", "email", "city")

# Check if field exists
exists = await redis.hexists("user:1001", "email")  # False
```

---

### 4. List Operations (Queues & Stacks)

#### Queue (FIFO) Pattern

```python
# Push to queue (right side)
await redis.rpush("queue:tasks", "task1", "task2", "task3")

# Pop from queue (left side)
task = await redis.lpop("queue:tasks")  # "task1"
task = await redis.lpop("queue:tasks")  # "task2"
```

#### Stack (LIFO) Pattern

```python
# Push to stack (left side)
await redis.lpush("stack:undo", "action1", "action2", "action3")

# Pop from stack (left side)
action = await redis.lpop("stack:undo")  # "action3"
```

#### Blocking Pop (Worker Pattern)

```python
# Worker waiting for tasks
while True:
    # Block until task available (timeout 5s)
    result = await redis.blpop("queue:tasks", timeout=5)
    if result:
        queue_name, task = result
        print(f"Processing: {task}")
        # Process task...
    else:
        print("No tasks, waiting...")
```

#### Range Operations

```python
# Get all items
items = await redis.lrange("queue:tasks", 0, -1)

# Get first 10 items
top10 = await redis.lrange("queue:tasks", 0, 9)

# Get list length
length = await redis.llen("queue:tasks")
```

---

### 5. Set Operations (Unique Collections)

#### Basic Set Operations

```python
# Add members
await redis.sadd("tags:article:1", "python", "redis", "tutorial")
await redis.sadd("tags:article:2", "python", "fastapi", "tutorial")

# Check membership
is_tagged = await redis.sismember("tags:article:1", "python")  # True

# Get all members
tags = await redis.smembers("tags:article:1")  # {"python", "redis", "tutorial"}

# Remove members
await redis.srem("tags:article:1", "tutorial")
```

#### Set Operations (Union, Intersection)

```python
# Find common tags (intersection)
common = await redis.sinter("tags:article:1", "tags:article:2")
# {"python", "tutorial"}

# Find all unique tags (union)
all_tags = await redis.sunion("tags:article:1", "tags:article:2")
# {"python", "redis", "fastapi", "tutorial"}

# Find tags only in article 1 (difference)
unique = await redis.sdiff("tags:article:1", "tags:article:2")
# {"redis"}
```

#### Random Operations

```python
# Get random member (without removing)
random_tag = await redis.srandmember("tags:article:1")

# Pop random member (remove it)
random_tag = await redis.spop("tags:article:1")
```

---

### 6. Sorted Set Operations (Leaderboards, Rankings)

#### Basic Sorted Set

```python
# Add players with scores
await redis.zadd("leaderboard:game1", {
    "player1": 1500,
    "player2": 2000,
    "player3": 1800,
    "player4": 2200
})

# Get top 3 players (descending)
top3 = await redis.zrevrange("leaderboard:game1", 0, 2, withscores=True)
# [("player4", 2200.0), ("player2", 2000.0), ("player3", 1800.0)]

# Get player rank (0-based)
rank = await redis.zrevrank("leaderboard:game1", "player1")  # 3 (4th place)

# Get player score
score = await redis.zscore("leaderboard:game1", "player1")  # 1500.0
```

#### Update Scores

```python
# Increment player score
new_score = await redis.zincrby("leaderboard:game1", 100, "player1")  # 1600.0

# Update score directly
await redis.zadd("leaderboard:game1", {"player1": 2500})
```

#### Range Queries

```python
# Get players by rank range (ascending)
bottom3 = await redis.zrange("leaderboard:game1", 0, 2, withscores=True)

# Get players by score range
mid_tier = await redis.zrangebyscore(
    "leaderboard:game1",
    min=1500,
    max=2000,
    withscores=True
)

# Count players in score range
count = await redis.zcount("leaderboard:game1", 1500, 2000)
```

#### Remove Members

```python
# Remove specific player
await redis.zrem("leaderboard:game1", "player1")

# Remove by rank range (bottom 10)
await redis.zremrangebyrank("leaderboard:game1", 0, 9)

# Remove by score range (score < 1000)
await redis.zremrangebyscore("leaderboard:game1", "-inf", 1000)
```

---

### 7. Expiration & TTL (Cache Management)

#### Set Expiration

```python
# Set with expiration at creation
await redis.set("cache:data", "value", ex=300)  # 5 minutes

# Add expiration to existing key
await redis.expire("cache:data", 600)  # Change to 10 minutes

# Set expiration as absolute timestamp
import time
expire_at = int(time.time()) + 3600  # 1 hour from now
await redis.expireat("cache:data", expire_at)
```

#### Check TTL

```python
# Get remaining TTL
ttl = await redis.ttl("cache:data")
# Returns: seconds remaining, -1 if no expiration, -2 if key doesn't exist

# Remove expiration
await redis.persist("cache:data")  # Key won't expire now
```

#### Auto-Refresh Pattern

```python
async def get_with_refresh(key: str, ttl: int = 300):
    """Get value and refresh TTL"""
    value = await redis.get(key)
    if value:
        await redis.expire(key, ttl)  # Refresh expiration
    return value
```

---

### 8. Pipeline & Transactions (Batch Operations)

#### Pipeline (Performance Optimization)

```python
# Without pipeline (4 network round-trips)
await redis.set("key1", "value1")
await redis.set("key2", "value2")
await redis.incr("counter")
await redis.get("key1")

# With pipeline (1 network round-trip)
async with redis.pipeline(transaction=False) as pipe:
    pipe.set("key1", "value1")
    pipe.set("key2", "value2")
    pipe.incr("counter")
    pipe.get("key1")
    results = await pipe.execute()  # [True, True, 1, "value1"]
```

#### Transaction (MULTI/EXEC)

```python
# Atomic transaction
async with redis.pipeline(transaction=True) as pipe:
    pipe.multi()  # Start transaction
    pipe.set("balance:alice", 900)
    pipe.set("balance:bob", 1100)
    results = await pipe.execute()  # All or nothing
```

#### Watch & Optimistic Locking

```python
async def transfer_money(from_user: str, to_user: str, amount: int):
    """Transfer money with optimistic locking"""
    
    async with redis.pipeline(transaction=True) as pipe:
        while True:
            try:
                # Watch keys for changes
                await pipe.watch(f"balance:{from_user}", f"balance:{to_user}")
                
                # Get current balances
                from_balance = int(await redis.get(f"balance:{from_user}"))
                to_balance = int(await redis.get(f"balance:{to_user}"))
                
                # Check if sufficient balance
                if from_balance < amount:
                    pipe.unwatch()
                    return False
                
                # Execute transaction
                pipe.multi()
                pipe.set(f"balance:{from_user}", from_balance - amount)
                pipe.set(f"balance:{to_user}", to_balance + amount)
                await pipe.execute()
                return True
                
            except redis.WatchError:
                # Key changed, retry
                continue
```

---

### 9. Pub/Sub (Real-Time Messaging)

#### Publisher

```python
# Publish messages
await redis.publish("notifications", "New comment on your post")
await redis.publish("chat:room1", "Alice: Hello everyone!")
```

#### Subscriber

```python
# Subscribe to channels
pubsub = redis.pubsub()
await pubsub.subscribe("notifications", "chat:room1")

# Listen for messages
async for message in pubsub.listen():
    if message["type"] == "message":
        channel = message["channel"]
        data = message["data"]
        print(f"[{channel}] {data}")
```

#### Pattern Subscribe

```python
# Subscribe to all chat rooms
await pubsub.psubscribe("chat:*")

async for message in pubsub.listen():
    if message["type"] == "pmessage":
        pattern = message["pattern"]     # "chat:*"
        channel = message["channel"]     # "chat:room1"
        data = message["data"]
        print(f"[{channel}] {data}")
```

---

### 10. Runtime Integration (Match3 Project)

#### Runtime Interface Implementation

```python
from redis.asyncio import Redis
from typing import Protocol

class IRedisClient(Protocol):
    """Redis client interface for dependency injection"""
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ex: int | None = None) -> bool: ...
    async def hgetall(self, name: str) -> dict[str, str]: ...
    # ... other methods

async def build_redis_client(config: RedisConfig) -> IRedisClient:
    """Build Redis client from config"""
    return await Redis(
        host=config.host,
        port=config.port,
        db=config.db,
        password=config.password,
        decode_responses=True,
        max_connections=config.max_connections,
        socket_timeout=config.socket_timeout
    )
```

#### Injecting into Runtime

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Match3Runtime:
    """Runtime dependency container (immutable)"""
    
    redis_client: IRedisClient  # Redis client interface
    # ... other dependencies

async def build_runtime(config: Config) -> Match3Runtime:
    """Build runtime with all dependencies"""
    
    redis_client = await build_redis_client(config.redis)
    
    return Match3Runtime(
        redis_client=redis_client,
        # ... other dependencies
    )
```

#### Usage in Repository (Cache Layer)

```python
import json
from typing import Any

class CacheRepository:
    """Repository for caching with Redis"""
    
    def __init__(self, runtime: Match3Runtime):
        self._redis = runtime.redis_client
        self._default_ttl = 300  # 5 minutes
    
    async def get_cached(self, key: str) -> Any | None:
        """Get cached value"""
        data = await self._redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set_cached(
        self,
        key: str,
        value: Any,
        ttl: int | None = None
    ):
        """Set cached value with TTL"""
        data = json.dumps(value)
        await self._redis.set(
            key,
            data,
            ex=ttl or self._default_ttl
        )
    
    async def get_or_compute(
        self,
        key: str,
        compute_fn: callable,
        ttl: int | None = None
    ) -> Any:
        """Get from cache or compute and cache"""
        
        # Try cache first
        cached = await self.get_cached(key)
        if cached is not None:
            return cached
        
        # Cache miss, compute value
        value = await compute_fn()
        await self.set_cached(key, value, ttl)
        return value
```

---

## Why Redis v8.4.2?

### Key Features in v8.x

1. **Improved Performance**
   - Faster read/write operations
   - Better memory efficiency
   - Optimized data structures

2. **Enhanced Reliability**
   - Better replication mechanism
   - Improved persistence options
   - Crash recovery improvements

3. **New Data Types**
   - JSON native support
   - Time series data structures
   - Probabilistic data structures (HyperLogLog, Bloom filters)

4. **Better Developer Experience**
   - Async/await support in clients
   - Improved error messages
   - Better monitoring tools

### When to Use Redis

✅ **Use Redis when**:
- Caching frequently accessed data
- Session storage
- Rate limiting
- Real-time leaderboards/rankings
- Message queues (simple use cases)
- Distributed locks
- Real-time analytics counters

❌ **Don't use Redis when**:
- Primary persistent data store (use PostgreSQL)
- Complex queries (use Elasticsearch)
- Large binary data (use MinIO)
- Complex relationships (use Neo4j)

---

## Integration with Match3 Architecture

```
┌─────────────────────────────────────────────────┐
│                  FastAPI Layer                  │
│              (Cache Middleware)                 │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│            CacheRepository                      │
│  - get_cached()                                 │
│  - set_cached()                                 │
│  - get_or_compute()                             │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│         Match3Runtime.redis_client              │
│       (IRedisClient Protocol)                   │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│              Redis Server                       │
│         (v8.4.2, In-Memory Cache)               │
└─────────────────────────────────────────────────┘
```

---

## Configuration Example

```python
from pydantic import BaseModel

class RedisConfig(BaseModel):
    """Redis configuration"""
    
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 50
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    
    # Cache settings
    default_ttl: int = 300          # 5 minutes
    max_ttl: int = 3600             # 1 hour
```

---

## Best Practices

1. **Use Appropriate TTL**
   - Short TTL for frequently changing data
   - Long TTL for static data
   - No TTL for permanent data (with caution)

2. **Key Naming Convention**
   - Use colons as separators: `user:1001:profile`
   - Include namespace: `app:production:cache:user:1001`
   - Use descriptive names

3. **Memory Management**
   - Set maxmemory-policy (e.g., `allkeys-lru`)
   - Monitor memory usage
   - Use hashes for related fields (saves memory)

4. **Connection Pooling**
   - Always use connection pools
   - Set appropriate pool size
   - Reuse connections

5. **Error Handling**
   - Handle connection errors gracefully
   - Implement fallback logic for cache misses
   - Log cache errors but don't fail requests
