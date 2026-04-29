# Candy Crush Saga Level Data Extraction Record

本文记录针对 Candy Crush Saga 实际执行方案 B（APK 逆向）的完整过程与结果，包括数据位置、提取命令和产物说明。数据格式详见 [level-format.md](./level-format.md)。

通用提取方案（适用于所有三消游戏）参见：[../level-data-extraction.md](../level-data-extraction.md)

---

## 一、游戏基本信息

| 项目 | 值 |
|---|---|
| 包名 | `com.king.candycrushsaga` |
| "关卡"概念 | Level（游戏内直接叫 Level 1、Level 2…） |
| APK 大小 | 156 MB（base.apk，无 split APK） |
| 总关卡数（APK 内嵌） | **22,205 关**（ordinal 0–22204） |
| 数据格式 | JSON，存储于 SQLite BLOB 列 |

---

## 二、APK 提取步骤

### 2.1 拉取 APK

```bash
# 查找 APK 路径
adb shell pm path com.king.candycrushsaga
# 示例输出：package:/data/app/~~Z8fYoEjT.../com.king.candycrushsaga-UlGRXyB7.../base.apk

# 拉取到本地（替换为实际路径）
adb pull "/data/app/~~Z8fYoEjT.../com.king.candycrushsaga-UlGRXyB7.../base.apk" \
  workspace/candy-crush-saga_apk-analysis/base.apk
```

### 2.2 定位关卡数据

APK 本质是 ZIP，先列目录找关卡相关文件：

```bash
unzip -l workspace/candy-crush-saga_apk-analysis/base.apk | grep -i level
```

关卡数据位于：

```
assets/res_output/bundled/ccsm_levels/
├── levels.xml                     # 关卡索引（King 私有二进制格式，暂无法解析）
├── levels/
│   ├── episode437level1.txt       # 单关卡 JSON 样本（少量）
│   ├── episode763level1.txt
│   └── pvp_level.txt
└── levels_batched/
    └── levels_batched.db          # 主数据库，41 MB SQLite，含全部 22,205 关
```

### 2.3 解压关卡数据

```bash
cd workspace/candy-crush-saga_apk-analysis/
unzip -j base.apk "assets/res_output/bundled/ccsm_levels/*" -d ccsm_levels/
# 注意：-j 会丢弃目录层级，所有文件平铺到 ccsm_levels/ 下
# 如需保留目录：unzip base.apk "assets/res_output/bundled/ccsm_levels/*" -d .
```

### 2.4 验证数据库

```bash
sqlite3 ccsm_levels/levels_batched.db ".tables"
# 输出：batched_levels

sqlite3 ccsm_levels/levels_batched.db ".schema"
# CREATE TABLE IF NOT EXISTS "batched_levels"
#   ("ordinal" INTEGER PRIMARY KEY, "level_data" BLOB NOT NULL);

sqlite3 ccsm_levels/levels_batched.db "SELECT COUNT(*) FROM batched_levels;"
# 22205
```

### 2.5 导出全量 JSONL

```bash
sqlite3 -separator '' ccsm_levels/levels_batched.db \
  "SELECT level_data FROM batched_levels ORDER BY ordinal;" \
  > all_levels.jsonl
# 产物：37 MB，每行一个关卡 JSON
```

---

## 三、产物清单

所有产物位于 `workspace/candy-crush-saga_apk-analysis/`：

| 文件/目录 | 大小 | 说明 |
|---|---|---|
| `base.apk` | 156 MB | 原始 APK |
| `ccsm_levels/levels_batched.db` | 41 MB | SQLite 数据库，22,205 关完整配置 |
| `ccsm_levels/levels/episode437level1.txt` | — | Level 108560 单关卡 JSON 样本 |
| `ccsm_levels/levels/episode763level1.txt` | — | Level 1027815 单关卡 JSON 样本（含传送门/炮） |
| `all_levels.jsonl` | 37 MB | 全量导出，JSONL 格式，按 ordinal 排序（位于本目录） |
| `classes.dex` / `classes2.dex` / `classes3.dex` | — | DEX 字节码（已提取，用于 strings 分析） |
| `screen_current.png` | — | 第 11 关截图（用于 tileMap 解码交叉验证） |

---

## 四、快速查询

```bash
# 进入 SQLite
sqlite3 workspace/candy-crush-saga_apk-analysis/ccsm_levels/levels_batched.db

# 按 ordinal 查（ordinal=0 即第 1 关）
SELECT level_data FROM batched_levels WHERE ordinal=0;

# 按游戏内关卡编号查（id_meta 对应游戏显示的 Level N）
SELECT level_data FROM batched_levels WHERE json_extract(level_data, '$.id_meta') = 11;

# 统计各模式关卡数
SELECT json_extract(level_data, '$.gameModeName') as mode, COUNT(*) as cnt
FROM batched_levels GROUP BY mode ORDER BY cnt DESC;

# 查询步数 <= 15 的最难关卡（Top 10）
SELECT json_extract(level_data, '$.id_meta') as id,
       json_extract(level_data, '$.gameModeName') as mode,
       json_extract(level_data, '$.moveLimit') as moves
FROM batched_levels
WHERE json_extract(level_data, '$.moveLimit') > 0
  AND json_extract(level_data, '$.moveLimit') <= 15
ORDER BY moves ASC LIMIT 10;
```

---

## 五、验证记录

### tileMap 解码验证（第 11 关）

对游戏内第 11 关（`id_meta=11`，ordinal=10）进行了截图与 DB 数据交叉比对：

| 验证项 | 截图观测 | DB 数据 | 结论 |
|---|---|---|---|
| 棋盘形状 | 倒梯形，底部完整，顶部两侧空缺 | tileMap 第 1–2 行有 `000` 填充 | ✅ 吻合 |
| 步数限制 | 界面显示 27 步 | `moveLimit: 27` | ✅ 吻合 |
| 目标 1 | 粉色心形方块 × 24 | `_itemsToOrder: [{item:32, quantity:24}]` | ✅ 吻合 |
| 目标 2 | 甘草漩涡 × 65 | `_itemsToOrder: [{item:17, quantity:65}]` | ✅ 吻合 |

---

## 六、已知局限与后续方向

1. **OTA 关卡**：APK 内仅含 22,205 关；King 持续通过服务器下发新关卡，需方案 C（流量拦截 + Frida SSL Pinning 绕过）捕获。

2. **`levels.xml` 索引**：King 私有二进制格式，尚未解析，不影响通过 SQLite 读取关卡数据。

3. **高 ID 段映射**：`082` 以上部分段 ID 含义已通过统计分析部分确认（见 [level-format.md 第四节](./level-format.md)），仍有范围待截图验证。

4. **SafetyNet / Play Integrity**：King 游戏有反作弊检测，Root 环境下建议搭配 Magisk + Hide My Applist，或在模拟器中分析。
