# Candy Crush Saga Level Data Extraction Record

本文记录针对 Candy Crush Saga 实际执行方案 B（APK 逆向）的完整过程、产物与验证结果。字段含义参见 [level-format.md](./level-format.md)，通用三消提取方案参见 [../level-data-extraction.md](../level-data-extraction.md)。

---

## 一、基本信息

| 项目 | 值 |
|---|---|
| 包名 | `com.king.candycrushsaga` |
| 关卡概念 | Level（游戏内显示为 Level 1、Level 2…） |
| APK 大小 | 156 MB（`base.apk`，无 split APK） |
| APK 内嵌关卡数 | **22,205 关**（ordinal 0–22204） |
| 数据格式 | JSON，原存于 SQLite BLOB 列，已导出为 `all_levels.jsonl` |

---

## 二、提取步骤

### 2.1 拉取 APK

```bash
# 查找 APK 路径
adb shell pm path com.king.candycrushsaga
# 输出示例：package:/data/app/~~Z8fYoEjT.../com.king.candycrushsaga-UlGRXyB7.../base.apk

# 拉取（替换为实际路径）
adb pull "/data/app/~~Z8fYoEjT.../com.king.candycrushsaga-UlGRXyB7.../base.apk" \
  workspace/candy-crush-saga_apk-analysis/base.apk
```

### 2.2 定位关卡数据

APK 本质是 ZIP，先搜索关卡相关路径：

```bash
unzip -l base.apk | grep -i level
```

关卡数据位于 APK 内：

```
assets/res_output/bundled/ccsm_levels/
├── levels.xml                    # 关卡索引（King 私有二进制格式，暂无法解析）
├── levels/
│   ├── episode437level1.txt      # 少量单关卡 JSON 样本
│   └── episode763level1.txt
└── levels_batched/
    └── levels_batched.db         # 主数据库，41 MB SQLite，含全部 22,205 关
```

### 2.3 解压

```bash
cd workspace/candy-crush-saga_apk-analysis/
unzip -j base.apk "assets/res_output/bundled/ccsm_levels/*" -d ccsm_levels/
```

### 2.4 导出全量 JSONL

原始导出后发现各关卡字段顺序不一致（原始 JSON 有 11,552 种不同排列）。用 `sort_keys=True` 重新导出，确保相同字段集合的关卡顺序完全一致：

```python
# import sqlite3, json
#
# db = sqlite3.connect("ccsm_levels/levels_batched.db")
# with open("all_levels.jsonl", "w") as f:
#     for ordinal, raw in db.execute(
#         "SELECT ordinal, level_data FROM batched_levels ORDER BY ordinal"
#     ):
#         f.write(json.dumps(json.loads(raw), sort_keys=True) + "\n")
# db.close()
```

产物 `all_levels.jsonl`：37 MB，22,205 行，每行一关完整 JSON，按关卡编号顺序排列。

---

## 三、产物清单

| 路径 | 大小 | 说明 |
|---|---|---|
| `docs/candy-crush-saga_levels/all_levels.jsonl` | 37 MB | **主数据文件**，22,205 关完整配置，字段已按字母排序 |
| `workspace/candy-crush-saga_apk-analysis/base.apk` | 156 MB | 原始 APK（备用） |
| `workspace/candy-crush-saga_apk-analysis/ccsm_levels/levels_batched.db` | 41 MB | 原始 SQLite（备用） |
| `workspace/candy-crush-saga_apk-analysis/screen_current.png` | — | 第 11 关截图（验证用） |

---

## 四、读取 all_levels.jsonl

```python
# import json
#
# with open("all_levels.jsonl") as f:
#     for line in f:
#         level = json.loads(line)
#         print(
#             f"Level {level['id_meta']}: {level['gameModeName']}, "
#             f"{level['moveLimit']} moves, "
#             f"board {level.get('boardRows', 9)}x{level.get('boardColumns', 9)}"
#         )
```

---

## 五、tileMap 解码验证

对第 11 关（`id_meta=11`，JSONL 第 11 行）进行了截图与数据交叉比对：

| 验证项 | 截图观测 | 数据值 | 结论 |
|---|---|---|---|
| 棋盘形状 | 倒梯形，顶部两侧空缺 | tileMap 前两行含 `000` | ✅ 吻合 |
| 步数 | 27 步 | `moveLimit: 27` | ✅ 吻合 |
| 目标1 | 粉色心形方块 × 24 | `_itemsToOrder: [{item:32, quantity:24}]` | ✅ 吻合 |
| 目标2 | 甘草漩涡 × 65 | `_itemsToOrder: [{item:17, quantity:65}]` | ✅ 吻合 |

item ID 与 tileMap 段 ID 的对应关系通过对全量 22,205 关做统计共现分析确认，详见 [level-format.md 第五节](./level-format.md#五收集目标-item-id--tilemap-段-id-对照)。

---

## 六、已知局限

| 问题 | 状态 | 可行解法 |
|---|---|---|
| APK 仅含 22,205 关，King 持续 OTA 下发新关卡 | 未解决 | 方案 C：mitmproxy + Frida 绕过 SSL Pinning 捕获新关卡 |
| tileMap 段 ID `107`–`181` 部分含义未确认 | **大部分已确认**（见 level-format.md 第五节）：`109`–`120` 颜色簇、`122`–`124` 糖衣、`129`–`133` 重型分层、`134`–`137` 瑞典鱼、`159`–`163` UFO 方块，均通过原生库枚举 + 统计共现双重验证；`140`–`158`、`164`–`181` 及食材 `107`–`108` 仍待逐一确认 | 逐关截图比对；或反编译 DEX 找字符串映射表 |
| `levels.xml` 为 King 私有二进制格式，无法解析 | 未解决 | 不影响主数据；如有需要可用 010 Editor 手动逆向 |
