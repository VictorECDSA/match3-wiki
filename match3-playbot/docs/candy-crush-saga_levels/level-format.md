# Candy Crush Saga Level Format Reference

每一关的数据是一个 JSON 对象（`all_levels.jsonl` 每行一关）。本文说明各字段的含义。

---

## 一、顶层字段

### 必填字段（22,205 关全部存在）

| 字段 | 类型 | 含义 |
|---|---|---|
| `protocolVersion` | `"0.3"` | 数据格式版本，当前全部为 `"0.3"` |
| `numberOfColours` | int | 本关使用的糖果颜色数（通常 4–6） |
| `randomSeed` | int | 随机种子（`0` = 完全随机） |
| `scoreTargets` | `[int, int, int]` | 一星 / 二星 / 三星 对应分数阈值 |
| `moveLimit` | int | 最大步数（`0` 表示不限） |
| `gameModeName` | string | 游戏模式，见[游戏模式](#三游戏模式-gamemodename)表 |
| `tileMap` | `string[][]` | 棋盘布局二维数组，见 [tileMap 编码](#二tilemap-编码) |
| `levelDefinitionId_meta` | int | 关卡定义唯一 ID |
| `version_meta` | int | 关卡版本号 |
| `id_meta` | int | 游戏内显示的关卡编号（Level N） |

### 常见字段

| 字段 | 出现率 | 类型 | 含义 |
|---|---|---|---|
| `boardRows` | 56% | int | 棋盘行数（缺省为 9） |
| `boardColumns` | 56% | int | 棋盘列数（缺省为 9） |
| `preferredColors` | 50% | `int[]` | 优先生成的糖果颜色 ID 列表 |
| `levelType` | 97% | `string[]` | 关卡修饰标签，见[修饰标签](#四关卡修饰标签-leveltype)表 |
| `episodeId` | 64% | int | 所属章节 ID |
| `levelId` | 64% | string | 服务器端关卡 ID |
| `qa` | 99% | bool | QA 标志，正式关卡均为 `false` |
| `disablePreLevelBoosters` | 36% | bool | 进关前禁用 Booster |
| `portals` | 52% | array | 传送门配置列表 |

### 关卡目标字段

| 字段 | 含义 |
|---|---|
| `_itemsToOrder` | 收集目标列表，每项为 `{item: int, quantity: int}`；item ID 见[收集目标对照](#五收集目标-item-id--tilemap-段-id-对照)表 |
| `ingredients` | 食材目标列表（Drop down 模式） |
| `ingredientSpawnDensity` | 食材生成密度 |
| `maxNumIngredientsOnScreen` | 同屏最多食材数 |
| `rainbowRapidsTargets` | 彩虹急流目标配置 |

### 棋子生成概率字段

| 字段 | 含义 |
|---|---|
| `stripedCandySpawn` / `stripedRowCandySpawn` / `stripedColumnCandySpawn` | 条纹糖生成概率（全向 / 横 / 纵） |
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

（对应 `*Max` 字段为同屏上限数量）

### 特殊机制字段

| 字段 | 含义 |
|---|---|
| `cannons` | 糖果炮所在列索引数组 |
| `ammoCannons` | 弹药炮配置 |
| `evilSpawnerCount` / `evilSpawnerElements` / `evilSpawnerAmount` / `evilSpawnerInterval` | 邪恶生成器：数量 / 元素类型 / 每次生成数 / 生成间隔（步） |
| `tileGroups` | 格子分组（同步动画/联动机制） |
| `gates` | 门配置 |
| `orlocks` | Orlock 怪物配置 |
| `skulls` | 骷髅障碍配置 |
| `wonderfulWrappers` | 奇妙包装配置 |
| `candyCobras` | 糖果眼镜蛇配置 |
| `frogStomachSize` | 青蛙胃容量（青蛙关专用） |
| `isOwlModeEnabled` | 是否启用猫头鹰模式 |
| `randomConfig` | 随机模式配置（`mode` / `modeModifier` / `seedPool`） |

---

## 二、tileMap 编码

`tileMap` 是 `boardRows × boardColumns`（默认 9×9）的字符串二维数组。每个格子的值是若干 **3 位数字片段**的拼接，从左到右代表从底层到顶层叠加的游戏元素。

```
"001002057005026"
 ↓
[001][002][057][005][026]
  ↓    ↓    ↓    ↓    ↓
底面  糖果  红色  生成  生成
格   格   固定  点   点变体
```

### 段 ID 对照表

| ID | 元素 | 说明 |
|---|---|---|
| `000` | 空格（不可用） | 棋盘边界或空洞，不参与游戏 |
| `001` | 果冻（单层） | 消除一次清除 |
| `002` | 普通格 | 可放置/移动糖果的标准格 |
| `003` | 果冻（单层，旧版） | 与 `001` 同类 |
| `004` | 果冻（双层） | 需消除两次 |
| `005` | 生成点（Spawner） | 糖果从顶部落入的入口 |
| `006` | 果酱（Marmalade） | 圆形果酱障碍，消除周围糖果清除 |
| `007` | 糖霜（1层） | 单层白色冰霜 |
| `008` | 甘草锁（Liquorice Lock） | 锁住糖果，需相邻消除解锁 |
| `009` | 糖霜（2层） | 需消除两次 |
| `010` | 食材出口 | 食材落出点（绿色箭头） |
| `011` | 传送门（通用） | 传送对 |
| `012` | 传送门入口 | 传送对起点 |
| `013` | 传送门出口 | 传送对终点 |
| `017` | 甘草漩涡（Liquorice Swirl） | 旋转甘草障碍 |
| `019` | 糖霜（1层，变体） | 与 `007` 同类 |
| `020` | 糖霜（2层） | 需消除两次 |
| `021` | 糖霜（3层） | 需消除三次 |
| `022` | 糖霜（4层） | 需消除四次 |
| `023` | 糖霜（5层） | 最厚糖霜 |
| `024` | 巧克力生成器 | 每步向外扩散一格巧克力 |
| `025` | 果酱（覆盖型） | 覆盖在糖果上的果酱 |
| `026` | 生成点（变体） | 另一种糖果入口 |
| `027` | 蛋糕炸弹 | 到达指定步数后爆炸 |
| `028` | 糖键锁（Sugar Key Lock） | 需糖键解开 |
| `035` | 蛋糕障碍 | 多层蛋糕型障碍 |
| `038` | 糖键（Sugar Key） | 钥匙，与 `028` 配对 |
| `039` | 神秘糖（Mystery Candy） | 消除后随机效果 |
| `040` | 变色龙糖 | 随机变色糖果 |
| `041` | 未确认 | — |
| `044` | 青蛙（Frog） | 青蛙元素 |
| `045` | 横向条纹糖（预置） | 预置的横向条纹特殊糖果 |
| `046` | 纵向条纹糖（预置） | 预置的纵向条纹特殊糖果 |
| `047` | 包装糖（预置） | 预置的包装糖 |
| `051` | 辣椒糖（Pepper Candy） | — |
| `054` | 彩虹炸弹（预置） | 预置的彩色炸弹 |
| `055` | 颜色固定（颜色0，紫色） | 固定该格只生成颜色0的糖果 |
| `056` | 颜色固定（颜色1，黄色） | — |
| `057` | 颜色固定（颜色2，红色） | — |
| `058` | 颜色固定（颜色3，橙色） | — |
| `059` | 颜色固定（颜色4，蓝色） | — |
| `060` | 颜色固定（颜色5，绿色） | — |
| `061` | 颜色固定（颜色6） | — |
| `079` | 幸运糖（Lucky Candy） | 消除可获随机奖励 |
| `080` | Mulock 糖 | Mulock 障碍糖果 |
| `081` | 盾牌（Shield） | 保护格不被障碍侵入 |
| `082` | 坠落糖霜（Falling Icing） | 从顶部下落的糖霜障碍 |
| `107`–`108` | 食材类型（部分）⚠️ 待确认 | 食材 item 1–2 对应段，具体映射待截图验证 |
| `109`–`120` | 食材类型 / 颜色簇（⚠️ 存在冲突，待确认） | `item 1`–`16`（食材）的统计范围覆盖此区间；同时 `item 27`（SEMIDURABLE_PARTY_BOOSTER）的单目标关卡也 100% 包含这些段。两种用途是否共用同一段 ID、如何区分，**尚未确认** |
| `121` | 未知 ⚠️ 未确认 | 出现于高层关卡，含义不明 |
| `122` | 糖衣（Sugarcoat 1层） | 糖衣障碍第1层，对应 `item 28`（SEMIDURABLE_STRIPED） |
| `123` | 糖衣（Sugarcoat 2层） | 糖衣障碍第2层 |
| `124` | 糖衣（Sugarcoat 3层） | 糖衣障碍第3层 |
| `125`–`128` | 未知 ⚠️ 未确认 | 出现于高层关卡，含义不明，尚未通过截图或枚举验证 |
| `129` | 重型分层（Heavy Layered 1层） | 重型分层障碍第1层，对应 `item 29`（SEMIDURABLE_WRAPPED） |
| `130` | 重型分层（Heavy Layered 2层） | 第2层 |
| `131` | 重型分层（Heavy Layered 3层） | 第3层 |
| `132` | 重型分层（Heavy Layered 4层） | 第4层 |
| `133` | 重型分层（Heavy Layered 5层） | 第5层（最厚） |
| `134` | 瑞典鱼（Swedish Fish 1层） | 对应 `item 31`（SEMIDURABLE_SWEDISH_FISH / GummyRope）第1层 |
| `135` | 瑞典鱼（Swedish Fish 2层） | 第2层 |
| `136` | 瑞典鱼（Swedish Fish 3层） | 第3层 |
| `137` | 瑞典鱼（Swedish Fish 4层） | 第4层（最厚） |
| `138`–`158` | 未知 ⚠️ 未确认 | 出现于高层关卡，含义不明；推测包含 `item 30`（SEMIDURABLE_STRIPED_WRAPPED）及 items 33–35 的段，但尚未验证 |
| `159` | UFO 收集方块（1层） | 对应 `item 32`（SEMIDURABLE_UFO）第1层 |
| `160` | UFO 收集方块（2层） | 第2层 |
| `161` | UFO 收集方块（3层） | 第3层 |
| `162` | UFO 收集方块（4层） | 第4层 |
| `163` | UFO 收集方块（5层） | 第5层（最厚） |
| `164`–`227` | 未知 ⚠️ 未确认 | 出现于高层关卡，含义不明；`228` Orlock 除外 |
| `228` | Orlock 怪物 | 吸取糖果的怪物 |
| `229` | 未知 ⚠️ 未确认 | 出现于部分关卡，含义不明 |
| `230` | 骷髅障碍（Skull） | 对应 `item 39`；骷髅会重生，`qty` = 含重生在内的全生命周期击杀总数，不可从静态 tileMap 推算 |
| `231`–`233` | 未知 ⚠️ 未确认 | 出现于部分关卡，含义不明 |
| `234` | 蛇（Snake）障碍 | 对应 `item 42`；`count(234) = qty`，100% 匹配 |

> ID `082` 以上的元素在早期关卡（前 1000 关）中几乎不出现，属于中后期新增机制。段 ID `122`–`124`、`129`–`137`、`159`–`163`、`230`、`234` 已通过原生库字符串（SEMIDURABLE 枚举）与 22,205 关统计共现分析双重确认；其余高 ID 段（标注 ⚠️）均为**未确认**状态。

---

## 三、游戏模式（gameModeName）

| 模式名 | 关卡数 | 说明 |
|---|---|---|
| `Light up` | 4,663 | 点亮所有果冻格 |
| `Order` | 3,930 | 收集指定数量物品 |
| `Jelly Order` | 3,422 | 点亮果冻 + 收集物品 |
| `Jelly Drop down` | 3,047 | 点亮果冻 + 食材掉落 |
| `Drop down` | 2,431 | 让食材从出口落出 |
| `Order Drop Down` | 2,345 | 收集物品 + 食材掉落 |
| `Rainbow Rapids Jelly` | 711 | 彩虹急流 + 点亮果冻 |
| `Rainbow Rapids Order` | 693 | 彩虹急流 + 收集物品 |
| `Rainbow Rapids` | 692 | 彩虹急流 |
| `Rainbow Rapids Drop Down` | 271 | 彩虹急流 + 食材掉落 |

---

## 四、关卡修饰标签（levelType）

| 标签 | 说明 |
|---|---|
| `Excavation` | 挖掘：需先清除覆盖物才能操作底层糖果 |
| `Explosive` | 爆炸性：含大量炸弹/爆炸机制 |
| `Sniping` | 狙击：操作区域受限，需精确消除 |
| `LimitedPlaySpace` | 受限棋盘：有效格很少 |
| `Endurance` | 耐力：步数多，持久战 |
| `Puzzle` | 谜题：固定布局，有唯一解 |

---

## 五、收集目标 item ID ↔ tileMap 段 ID 对照

`_itemsToOrder[].item` 的数值对应 tileMap 中具体的游戏元素。下表综合原生库字符串分析（SEMIDURABLE 枚举）与 22,205 关统计共现分析得出。

### 5.1 食材类（item 1–16）

| item ID | 对应段 ID | 元素 |
|---|---|---|
| `1`–`16` | `107`–`120` | 各种食材（樱桃/榛子等）；逐一映射待验证 |

### 5.2 SEMIDURABLE 半持久元素（item 17–39，来自原生库枚举）

原生库 `libcandycrushsaga.so` 中包含完整枚举，命名为 `SEMIDURABLE_*`，item ID 与枚举值一一对应：

| item ID | SEMIDURABLE 枚举名 | 对应段 ID | 元素 | qty 含义 | 可从 tileMap 推算 |
|---|---|---|---|---|---|
| `17` | — | `017` | 甘草漩涡（Liquorice Swirl） | 收集数量 | ✅ `count(017) = qty` |
| `18` | — | ⚠️ 未确认 | 未知（统计发现段 `158` 与之相关，但 count(158)=qty 仅 11% 匹配，尚无可靠公式） | 收集数量 | ❓ 未确认 |
| `19` | — | `017` | 甘草漩涡（颜色变体） | 收集数量 | ✅ 同上 |
| `21` | `SEMIDURABLE_COLOR_BOMB` | 动态生成 | 彩色炸弹（Color Bomb） | 收集/使用次数 | ❌ 动态生成，无静态段 |
| `22` | `SEMIDURABLE_FREE_SWITCH` | 动态生成 | 自由切换（Free Switch） | 收集/使用次数 | ❌ 动态生成，无静态段 |
| `22`（蛋糕） | — | `035` | 蛋糕障碍（Cake Bomb） | 收集数量 | ✅ `count(035) = qty` |
| `23` | `SEMIDURABLE_LOLLIPOP` | 动态生成 | 棒棒糖（Lollipop Hammer） | 收集/使用次数 | ❌ 动态生成 |
| `24` | `SEMIDURABLE_COCONUT_WHEEL` | 动态生成 | 椰子轮（Coconut Wheel） | 收集/使用次数 | ❌ 动态生成 |
| `25` | `SEMIDURABLE_JOKER_CANDY` | `079`–`083` | 幸运糖（Lucky Candy） | 收集数量 | ⚠️ `1×079+2×080+3×081+4×082+5×083`，~78% 匹配（其余为生成点关卡） |
| `26` | `SEMIDURABLE_PAINT_BRUSH` | 动态生成 | 颜料刷（Paint Brush） | 收集/使用次数 | ❌ 动态生成 |
| `27` | `SEMIDURABLE_PARTY_BOOSTER` | `109`–`120` | 颜色簇（Color Cluster） | 收集数量 | ✅ 加权和（见下方公式），100% 出现率 |
| `28` | `SEMIDURABLE_STRIPED` | `122`–`124` | 糖衣（Sugarcoat，3层） | 收集数量 | ⚠️ `1×122+2×123+3×124`，~71% 匹配（其余为生成点关卡） |
| `29` | `SEMIDURABLE_WRAPPED` | `129`–`133` | 重型分层（Heavy Layered，5层） | 收集数量 | ⚠️ `1×129+2×130+3×131+4×132+5×133`，~77% 匹配（其余为生成点关卡） |
| `30` | `SEMIDURABLE_STRIPED_WRAPPED` | ⚠️ 未确认 | 条纹包装（Striped-Wrapped）；无单目标关卡可用，段 ID 无法通过统计定位 | 收集数量 | ❓ 未确认 |
| `31` | `SEMIDURABLE_SWEDISH_FISH` | `134`–`137` | 瑞典鱼/糖绳（GummyRope，4层） | 收集数量 | ⚠️ `1×134+2×135+3×136+4×137`，~48% 匹配（其余为生成点关卡） |
| `32` | `SEMIDURABLE_UFO` | `159`–`163` | UFO 收集方块（5层） | 收集数量 | ⚠️ `1×159+2×160+3×161+4×162+5×163`，~73% 匹配（其余为生成点关卡） |
| `33` | — | ⚠️ 未确认 | 未知；样本仅 16 关，段分布推测在 `140`–`181` 范围，尚未确认 | 收集数量 | ❓ 未确认 |
| `34` | — | ⚠️ 未确认 | 未知；样本仅 10 关，同上 | 收集数量 | ❓ 未确认 |
| `35` | — | ⚠️ 未确认 | 未知；样本仅 9 关，同上 | 收集数量 | ❓ 未确认 |
| `39` | — | `230` | 骷髅（Skull） | 含重生在内的击杀总数 | ❌ 骷髅会重生，静态段仅表示初始放置数 |
| `42` | — | `234` | 蛇（Snake）障碍 | 收集数量 | ✅ `count(234) = qty`，100% 匹配 |

> **注**：item ID `22` 在不同语境下有歧义——枚举 `SEMIDURABLE_FREE_SWITCH=22` 是动态生成的关卡内道具，而另一 `item 22` 对应 tileMap 段 `035`（蛋糕障碍）。两者在关卡数据中共存，请根据具体关卡的 `gameModeName` 与 tileMap 内容区分。

### 5.3 多层障碍加权公式

所有多层障碍的 `qty` 计算方式为**加权层数求和**（即每个格子按其层数计入，而非按格子数计入）：

```
qty = Σ_k  k × count(seg_base + k − 1)
```

例：
- item 29 重型分层 5层：`qty = 1×count(129) + 2×count(130) + 3×count(131) + 4×count(132) + 5×count(133)`
- item 32 UFO 5层：`qty = 1×count(159) + 2×count(160) + 3×count(161) + 4×count(162) + 5×count(163)`

### 5.4 生成点（Spawner）关卡的特殊性

含生成点（段 `005` 或 `026`）的关卡中，障碍物可在游戏运行时**动态生成**。动态生成的障碍不出现在 tileMap 静态格子中，导致上述公式的计算值小于实际 `qty`。**所有公式不匹配的关卡（items 27–32），经验证 100% 含有生成点段**。在剔除生成点关卡后，各公式匹配率接近 100%。

> `item 1`–`16` 对应食材（樱桃/榛子等），段 ID 在 `107`–`120` 范围，逐一映射待验证（与 `item 27` 颜色簇段范围重叠，关系尚未厘清）。items `18`、`30`、`33`、`34`、`35` 均为 ⚠️ **未确认** 状态——`item 18` 统计线索指向段 `158` 但匹配率极低；`item 30` 因无单目标关卡无法定位；items `33`–`35` 样本量不足（≤16 关）。
