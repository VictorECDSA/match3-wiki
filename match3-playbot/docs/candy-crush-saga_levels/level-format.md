# Candy Crush Saga 关卡数据格式解析

本文记录通过 APK 逆向（方案 B）从 `base.apk` 中成功提取的关卡数据结构，包括存储位置、JSON 字段含义、tileMap 编码表。

> **验证状态**：tileMap 编码已通过第 11 关截图与 DB 数据交叉比对确认正确（棋盘形状、步数、目标数量三项完全吻合）。

---

## 一、数据来源

### 位置

APK 内路径：

```
assets/res_output/bundled/ccsm_levels/
├── levels.xml                          # 关卡索引（二进制格式）
├── levels/
│   ├── episode437level1.txt            # 单关卡 JSON 样本
│   ├── episode763level1.txt
│   └── pvp_level.txt
└── levels_batched/
    └── levels_batched.db              # 主数据库，41 MB SQLite
```

### 提取命令

```bash
# 1. 从手机拉取 APK
adb shell pm path com.king.candycrushsaga
# 输出示例：package:/data/app/~~xxxxx==/com.king.candycrushsaga-xxxxx==/base.apk
adb pull <上述路径> base.apk

# 2. 解压 ccsm_levels 包
unzip -j base.apk "assets/res_output/bundled/ccsm_levels/*" -d ccsm_levels/
```

### 数据规模

| 项目 | 数量 |
|---|---|
| 总关卡数 | **22,205** |
| 数据库表 | `batched_levels`（仅一张） |
| 主键 | `ordinal`（INTEGER，0-based） |
| 数据列 | `level_data`（BLOB，实际存储 JSON 文本） |

---

## 二、关卡 JSON 字段说明

每一行 `level_data` 是一个 JSON 对象，以下是完整字段表。

### 2.1 必填字段（22205 关全部存在）

| 字段 | 类型 | 说明 |
|---|---|---|
| `protocolVersion` | `"0.3"` | 数据格式版本，当前均为 `"0.3"` |
| `numberOfColours` | int | 本关使用的糖果颜色数（通常 4–6） |
| `randomSeed` | int | 随机种子（0 = 完全随机） |
| `scoreTargets` | `[int, int, int]` | 一星/二星/三星 对应分数阈值 |
| `moveLimit` | int | 最大步数（无限时关卡为 0 或不设） |
| `gameModeName` | string | 游戏模式名（见下方列表） |
| `tileMap` | `string[][]` | 棋盘布局，9×9 二维数组（见第三节） |
| `levelDefinitionId_meta` | int | 关卡定义 ID（唯一标识） |
| `version_meta` | int | 关卡版本号 |
| `id_meta` | int | 关卡序号（对应游戏内关卡编号） |

### 2.2 常见字段

| 字段 | 出现频率 | 类型 | 说明 |
|---|---|---|---|
| `preferredColors` | 50% | `int[]` | 优先使用的糖果颜色 ID 列表 |
| `boardRows` | 56% | int | 棋盘行数（未指定默认 9） |
| `boardColumns` | 56% | int | 棋盘列数（未指定默认 9） |
| `levelType` | 97% | `string[]` | 关卡修饰标签（见下方列表） |
| `levelId` | 64% | string | 服务器端关卡 ID |
| `episodeId` | 64% | int | 关卡所属章节 ID |
| `qa` | 99% | bool | QA 测试标志，正式关卡均为 `false` |
| `disablePreLevelBoosters` | 36% | bool | 是否禁止进关前使用 Booster |
| `portals` | 52% | array | 传送门配置列表 |

### 2.3 目标相关字段

| 字段 | 说明 |
|---|---|
| `_itemsToOrder` | 收集目标列表，每项含 `item`（物品 ID）和 `quantity`（数量） |
| `ingredients` | 食材目标（掉落收集关卡） |
| `ingredientSpawnDensity` | 食材生成密度 |
| `maxNumIngredientsOnScreen` | 同屏最多食材数 |
| `rainbowRapidsTargets` | 彩虹急流目标配置 |

### 2.4 棋子生成相关字段

| 字段 | 说明 |
|---|---|
| `stripedCandySpawn` | 条纹糖果每步生成概率 |
| `stripedRowCandySpawn` | 横向条纹糖生成概率 |
| `stripedColumnCandySpawn` | 纵向条纹糖生成概率 |
| `wrappedCandySpawn` | 包装糖生成概率 |
| `colorBombSpawn` | 彩色炸弹生成概率 |
| `fishSpawn` | 鱼糖生成概率 |
| `licoriceSpawn` | 甘草生成速率 |
| `luckyCandySpawn` | 幸运糖生成概率 |
| `pepperCandySpawn` | 辣椒糖生成概率 |
| `mulockCandySpawn` | Mulock 糖生成概率 |
| `mysteryCandySpawn` | 神秘糖生成概率 |
| `chameleonCandySpawn` | 变色龙糖生成概率 |
| `fallingIcingSpawn` | 坠落糖霜生成概率 |
| `shieldSpawn` | 盾牌生成概率 |

### 2.5 特殊机制字段

| 字段 | 说明 |
|---|---|
| `cannons` | 糖果炮列配置（列索引数组） |
| `ammoCannons` | 弹药炮配置 |
| `evilSpawnerCount` | 邪恶生成器数量 |
| `evilSpawnerElements` | 邪恶生成器元素类型 |
| `evilSpawnerAmount` | 每次生成数量 |
| `evilSpawnerInterval` | 生成间隔（步数） |
| `tileGroups` | 格子分组（用于同步动画/机制） |
| `gates` | 门的配置 |
| `orlocks` | Orlock 怪物配置 |
| `skulls` | 骷髅障碍配置 |
| `wonderfulWrappers` | 奇妙包装配置 |
| `candyCobras` | 糖果眼镜蛇配置 |
| `frogStomachSize` | 青蛙胃容量（青蛙关卡） |
| `isOwlModeEnabled` | 是否启用猫头鹰模式 |
| `randomConfig` | 随机模式配置（`mode`/`modeModifier`/`seedPool`） |

---

## 三、tileMap 编码规则

`tileMap` 是 9×9（或其他尺寸）的字符串二维数组，每个格子的值是若干**3 位数字片段**的拼接。

### 解码方式

```
"001002057005026"
 ↓
[001][002][057][005][026]
  ↓    ↓    ↓    ↓    ↓
底层  糖果 红色 生成 ??
底面  单元 固定  点
```

顺序从左到右代表从**底层到顶层**堆叠的游戏元素。

### 3-位段 ID 对照表

| ID | 元素 | 说明 |
|---|---|---|
| `000` | 空格（不可用） | 不参与游戏的空白区域（棋盘边界/洞） |
| `001` | 果冻（单层） | 单层果冻，消除一次清除 |
| `002` | 普通格（有糖果） | 可放置/移动糖果的标准格 |
| `003` | 果冻（单层，旧版） | 与 001 类似的单层果冻 |
| `004` | 果冻（双层） | 双层果冻，需消除两次 |
| `005` | 生成点（Spawner） | 糖果从顶部生成的入口 |
| `006` | 果酱（Marmalade） | 圆形果酱障碍，消除周围糖果清除 |
| `007` | 糖霜（1层） | 单层白色冰霜 |
| `008` | 甘草锁（Liquorice Lock） | 锁住糖果，需相邻消除解锁 |
| `009` | 糖霜（2层） | 双层糖霜 |
| `010` | 食材出口 | 食材（樱桃/榛子）的落出点（绿色箭头） |
| `011` | 传送门（通用） | 传送对 |
| `012` | 传送门入口 | 传送对的起点 |
| `013` | 传送门出口 | 传送对的终点 |
| `017` | 甘草漩涡（Liquorice Swirl） | 旋转甘草障碍 |
| `019` | 糖霜（1层，变体） | 单层糖霜（与 007 同类） |
| `020` | 糖霜（2层） | 需两次消除 |
| `021` | 糖霜（3层） | 需三次消除 |
| `022` | 糖霜（4层） | 需四次消除 |
| `023` | 糖霜（5层） | 最厚糖霜，需五次消除 |
| `024` | 巧克力生成器 | 每步生成扩散的巧克力 |
| `025` | 果酱（Marmalade，覆盖型） | 覆盖糖果的果酱 |
| `026` | 生成点（Spawner，变体） | 另一种糖果生成入口 |
| `027` | 蛋糕炸弹 | 达到步数后爆炸的蛋糕障碍 |
| `028` | 糖键锁（Sugar Key Lock） | 需要糖键解开的锁 |
| `035` | 蛋糕障碍 | 多层蛋糕型障碍 |
| `038` | 糖键（Sugar Key） | 钥匙，与 `028` 配对使用 |
| `039` | 神秘糖（Mystery Candy） | 打开后随机效果 |
| `040` | 变色龙糖 | 变色糖果 |
| `041` | ??? | 未确认 |
| `044` | 青蛙（Frog） | 青蛙元素（收集关使用） |
| `045` | 横向条纹糖 | 预置的横向条纹特殊糖果 |
| `046` | 纵向条纹糖 | 预置的纵向条纹特殊糖果 |
| `047` | 包装糖（Wrapped Candy） | 预置的包装糖 |
| `051` | 胡椒糖（Pepper Candy） | 辣椒糖 |
| `054` | 彩虹炸弹（Color Bomb） | 预置的彩色炸弹 |
| `055` | 颜色固定（颜色0，紫色） | 固定该格生成颜色0的糖果 |
| `056` | 颜色固定（颜色1，黄色） | 固定该格生成颜色1的糖果 |
| `057` | 颜色固定（颜色2，红色） | 固定该格生成颜色2的糖果 |
| `058` | 颜色固定（颜色3，橙色） | 固定该格生成颜色3的糖果 |
| `059` | 颜色固定（颜色4，蓝色） | 固定该格生成颜色4的糖果 |
| `060` | 颜色固定（颜色5，绿色） | 固定该格生成颜色5的糖果 |
| `061` | 颜色固定（颜色6） | 固定该格生成颜色6的糖果 |
| `079` | 幸运糖（Lucky Candy） | 奖励糖果，消除可获随机奖励 |
| `080` | Mulock 糖 | Mulock 障碍糖果 |
| `081` | 盾牌（Shield） | 保护格不被障碍侵入 |
| `082` | 坠落糖霜（Falling Icing） | 从顶部下落的糖霜障碍 |
| `107`–`120` | 食材类型 | 各种食材（樱桃/榛子等）编号 |
| `122`–`135` | 章鱼/特殊障碍 | 高层关卡特殊障碍 |
| `140`–`181` | 高级障碍 | 各类后期关卡障碍物 |
| `159`–`163` | 可收集方块（多层） | 粉色心形/特殊收集物，对应 `_itemsToOrder` 中 `item 32`；共5层，逐层消除 |
| `228` | Orlock 怪物 | 吸取糖果的怪物 |
| `230` | 骷髅障碍 | 骷髅类障碍，对应 `_itemsToOrder` 中 `item 39` |

> **注意**：ID 在 `082` 以上的元素在早期关卡（ordinal < 1000）中几乎不出现，属于中后期新增机制。

---

## 四、收集目标 item ID ↔ tileMap 段 ID 对照

`_itemsToOrder` 字段中每个目标的 `item` 数值，与 tileMap 中的段 ID 存在对应关系。以下对照表通过对 22,205 关进行统计共现分析得出（仅取单目标关卡，排除 `001`/`002`/`003`/`004`/`005`/`010`/`026` 等公共段，取共现频率最高的非公共段）。

| item ID | 最相关段 ID | 元素名称 | 说明 |
|---|---|---|---|
| `17` | `017` | 甘草漩涡（Liquorice Swirl） | 共现频率极高；收集甘草漩涡 |
| `19` | `017` | 甘草漩涡（Liquorice Swirl） | 与 item 17 指向同一段，可能区分颜色变体 |
| `22` | `035` | 蛋糕炸弹（Cake Bomb） | 与蛋糕障碍段强相关 |
| `25` | `079`/`080`/`081`/`082`/`083` | 幸运糖系列（Lucky Candy） | 多段对应同族元素（不同层或变体） |
| `32` | `159`–`163` | 可收集方块（多层） | 粉色心形/收集物；5个段 ID 对应5层 |
| `39` | `230` | 骷髅障碍（Skull） | 与段 `230` 强唯一对应 |

> **方法说明**：从 22,205 关中筛选 `_itemsToOrder` 仅含单个 item 的关卡，统计这些关卡 tileMap 中出现的非公共段 ID 频率，取排名最高者。置信度取决于该 item 的专属关卡数量。

> **已知局限**：item ID `01`–`16` 对应食材（樱桃/榛子等），段 ID 见 `107`–`120` 范围，具体一一映射尚未逐个验证。

---

## 五、游戏模式（gameModeName）

| 模式名 | 关卡数 | 说明 |
|---|---|---|
| `Light up` | 4,663 | 点亮关：点亮所有果冻格 |
| `Order` | 3,930 | 收集关：收集指定数量物品 |
| `Jelly Order` | 3,422 | 果冻+收集混合 |
| `Jelly Drop down` | 3,047 | 果冻+食材掉落混合 |
| `Drop down` | 2,431 | 食材掉落关：让食材从出口落出 |
| `Order Drop Down` | 2,345 | 收集+食材掉落混合 |
| `Rainbow Rapids Jelly` | 711 | 彩虹急流+果冻 |
| `Rainbow Rapids Order` | 693 | 彩虹急流+收集 |
| `Rainbow Rapids` | 692 | 彩虹急流模式 |
| `Rainbow Rapids Drop Down` | 271 | 彩虹急流+食材掉落 |

---

## 六、关卡修饰标签（levelType）

| 标签 | 说明 |
|---|---|
| `Excavation` | 挖掘模式：需先清除覆盖物才能操作底层糖果 |
| `Explosive` | 爆炸性：关卡含有大量炸弹/爆炸机制 |
| `Sniping` | 狙击模式：操作区域受限，需精确消除 |
| `LimitedPlaySpace` | 受限棋盘：大量不可用格，有效格较少 |
| `Endurance` | 耐力模式：步数多，持久战 |
| `Puzzle` | 谜题模式：固定布局，有唯一解法 |

---

## 七、快速查询示例

```bash
# 进入 SQLite
sqlite3 ccsm_levels/levels_batched.db

# 查询第 1 关（ordinal=0）
SELECT level_data FROM batched_levels WHERE ordinal=0;

# 查询游戏内 id 为 100 的关卡
SELECT level_data FROM batched_levels WHERE json_extract(level_data, '$.id_meta') = 100;

# 查询所有 "Drop down" 模式且步数 <= 20 的困难关
SELECT ordinal, json_extract(level_data, '$.id_meta') as id,
       json_extract(level_data, '$.moveLimit') as moves
FROM batched_levels
WHERE json_extract(level_data, '$.gameModeName') = 'Drop down'
  AND json_extract(level_data, '$.moveLimit') <= 20
ORDER BY moves ASC LIMIT 10;

# 统计各模式关卡数
SELECT json_extract(level_data, '$.gameModeName') as mode, COUNT(*) as cnt
FROM batched_levels GROUP BY mode ORDER BY cnt DESC;

# 导出所有关卡为 JSON Lines 文件
sqlite3 -separator '' ccsm_levels/levels_batched.db \
  "SELECT level_data FROM batched_levels ORDER BY ordinal;" \
  > all_levels.jsonl
```

---

## 八、Python 读取示例

```python
# import sqlite3, json
#
# db = sqlite3.connect("ccsm_levels/levels_batched.db")
# cursor = db.execute("SELECT ordinal, level_data FROM batched_levels ORDER BY ordinal")
#
# for ordinal, raw in cursor:
#     level = json.loads(raw)
#     print(f"Level {level['id_meta']}: {level['gameModeName']}, "
#           f"{level['moveLimit']} moves, "
#           f"board {level.get('boardRows', 9)}x{level.get('boardColumns', 9)}")
#
# db.close()
```

---

## 九、已知局限

1. **OTA 关卡**：`levels_batched.db` 仅含 APK 内嵌的 22205 关。King 持续通过 OTA 推送新关卡，这些不在 APK 中（需方案 C 流量拦截）。

2. **tileMap 高 ID 映射**：ID `082` 以上的部分元素含义已通过统计共现分析部分确认（见第四节），但 `107`–`120`（食材）、`122`–`135`（章鱼/特殊障碍）、`140`–`158`/`164`–`181` 等范围仍需逐个截图验证。

3. **`levels.xml` 索引**：该文件为 King 私有二进制格式（非标准 XML），尚未完全解析。

4. **Split APK**：本次拉取的是 `base.apk`（156 MB），没有 split APK，全量数据已在其中。
