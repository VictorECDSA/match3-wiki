# Candy Crush Saga 游戏基础概念

本文面向没有玩过或很少玩过 Candy Crush Saga 的读者，解释游戏的核心机制，以及 `level-format.md` 和 `all_levels.jsonl` 中出现的各类术语。

> **证据等级图例**：
> - ✅ **源码确认**（`libcandycrushsaga.so` 的 RTTI 类名 / 调试符号 / 字符串字面量）
> - 🟡 **数据推测**（22,205 关 tileMap 统计共现的高置信度结论）
> - ⚠️ **未确认**（仅有间接线索）

---

## 一、游戏是什么

Candy Crush Saga 是一款**三消（Match-3）益智游戏**。玩家在一块棋盘上，通过**交换相邻的两颗糖果**，让三颗或更多同色糖果排成一行或一列，触发"消除"。消除糖果会使上方糖果下落填补空缺，新糖果从顶部进入棋盘，形成连续的连锁反应。

每一关有一个或多个**目标**（比如"消除 25 个甘草漩涡"或"点亮所有果冻格"），玩家需要在**步数限制**内完成目标才算通关。

---

## 二、棋盘基本元素

### 格子（Tile）

棋盘由若干格子组成，默认 9 行 × 9 列。每个格子有一个 `tileMap` 编码（见 `level-format.md` 第二节）。格子分两种：

- **可用格**：可以放糖果、可以操作。tileMap 编码中**几乎所有可玩格的第一段都是 `001`**——它是「该格存在/可见」的基础地形标记（**不是果冻**）。后续 `002` 表示「可放糖果」、`004` 表示「该格上覆盖一层果冻」。详见 `level-format.md` § 2.1。
- **空格（`000`）**：棋盘边界或不规则形状挖去的空洞，不参与游戏。棋盘形状各异（如菱形、十字形、梯形）正是通过设置 `000` 格实现的。

### 糖果（Candy）

棋盘上的基本移动单元，有 4–6 种颜色（由 `numberOfColours` 决定）。糖果本身不在 `tileMap` 中编码——因为普通糖果是游戏运行时随机生成的；`tileMap` 里只记录**地形和障碍物**，不记录具体糖果颜色。

### 生成点（Spawner，段 ID `005` + `026`）

棋盘顶部的**糖果入口**。每一步消除后，新糖果从生成点"落入"棋盘填补空缺。

🟡 **数据观察**：在 22,205 关中，**`005` 与 `026` 极少单独出现**——`005` 共 218,870 次，其中 174,368 次（≈80%）后面紧跟 `026`。它们是一对**配对出现的顶行 spawner 标记**：

- **`005`** 推测为 spawner 的逻辑锚点
- **`026`** 推测为 spawner 的视觉标记或资源 ID

⚠️ `libcandycrushsaga.so` 中的 RTTI 揭示 spawner 体系包含 `IItemSpawner`、`IBoardItemSpawner`、`IChocolateSpawner`、`CTorpedoSpawner`、`CDropDownSpawner` 等多种类型，对应到段 ID 的具体方式仍需确认。

> **影响难度**：含 spawner 的关卡，障碍物可以在游戏中途由代码持续"生产"（见 `evilSpawnerCount` / `evilSpawnerInterval` 字段），玩家需要在补充速度大于消除速度时挣扎完成目标，难度更高。这也是为什么这类关卡的 `qty` 目标值往往大于棋盘上静态放置的数量。

---

## 三、障碍物

障碍物是妨碍玩家操作的特殊元素，叠加在格子上。大多数障碍物需要通过消除**相邻**糖果来减少层数或清除。

### 果冻（Jelly，段 `004` 为主，配合 `001`/`003`）🟡

格子上的蓝色果冻层，需要在该格完成消除才能清除。"Light up（点亮）"模式的目标就是清除棋盘上所有果冻格。

> **关键事实**（来自 22,205 关数据）：
>
> - **`001` 不是果冻**——它在 Order、Drop down 等无果冻关里也几乎每格都有，是「基础地形」标记。
> - **`004` 才是果冻 layer**——仅在 Light up / Jelly Order / Jelly Drop down / RR Jelly 模式中铺满可玩格，其他模式不出现。
> - **`003` 是某种果冻特殊变体**——只在 Jelly 系模式出现（占该模式约 35%–37% 关卡），具体是「双倍分果冻」「装饰果冻」还是「双层果冻」，⚠️ 未确认。
>
> **多层果冻的编码**：数据中 `004` 在每格至多出现 1 次（不存在 `004004`）；少数关卡里 `001` 在同一格重复 2–8 次（共约 1700 cells），疑似用于多层果冻编码，⚠️ 待源码确认。

### 糖霜 / 冰霜（Icing，段 `019`–`023`）🟡

白色冰霜层覆盖格子，阻止玩家直接操作该格的糖果。需要消除**相邻**格子的糖果来"敲碎"冰霜，每次减少一层：

| 段 ID | 推测层数 | 出现次数 |
|---|---|---|
| `019` | 1 层 | 60,935 |
| `020` | 2 层 | 65,487 |
| `021` | 3 层 | 63,821 |
| `022` | 4 层 | 48,458 |
| `023` | 5 层 | 40,063 |

> 段 `007` (6 次) / `009` (3,627 次) 是已弃用的糖霜编码，被 `019`–`023` 取代。
> 「层数」语义是基于"段 ID 递增 + 出现次数递减"的合理推测，**也可能是 5 种独立糖霜变体**而非线性层数 ⚠️。

### 甘草漩涡（Liquorice Swirl，段 `017`）✅

黑色旋涡状障碍，占据一个格子，阻止该格糖果被移动。消除相邻糖果可以清除它。

"Order（收集）"模式中，收集目标 `item 17` 就是清除这些漩涡。**经数据验证 `count(017)` 与 `_itemsToOrder.item=17` 的 qty 高度相关**。

### 甘草锁（Liquorice Lock，段 `008`）✅

锁住一颗糖果，使其无法被交换移动。需消除相邻糖果将锁解开。源码：`LicoriceLockSceneObject.cpp`。

### 果酱（Marmalade，段 `006` / `025`）🟡

果酱类障碍包覆在格子或糖果上，需要消除该格糖果或相邻糖果来清除：

- **段 `006`**：圆形果酱障碍（出现 2,483 次，相对少）。C++ 代码中 `MarmaladeLockSceneObject` 是「果酱锁」类型——可能就是 `006`。
- **段 `025`**：覆盖型果酱（出现 64,219 次，常与 `004` 共现）。覆盖在已有元素上，消除底下元素时一并清除。

⚠️ `006` 与 `025` 的具体语义差别（哪个是"果酱锁"，哪个是"覆盖果酱"）尚未严格区分，待源码进一步确认。

### 巧克力生成器（段 `024`）✅

每走一步，就会向相邻格子扩散一格巧克力，蔓延覆盖格子。玩家必须不断消除周围糖果阻止其扩散，同时完成关卡目标——压力很大。源码：`IChocolateSpawner` 接口。

### 蛋糕炸弹（段 `027`）✅

源码：`CCakeBomb` 类。计时炸弹型障碍。倒计时归零时爆炸，通常造成大范围破坏或直接结束游戏。玩家必须在计时耗尽前消除它周围的糖果使其爆炸，或直接消除它。

> 注意 § 五 的 **蛋糕障碍（段 `035`）** 是另一种独立元素（不是炸弹，是**收集目标**），见下文 5.1。

### 蛋糕障碍（段 `035`）✅

✅ **数据 100% 确认**：与 `_itemsToOrder.item=22` 完全共现（310/310 关）。多层蛋糕收集型目标，每次消除相邻糖果使蛋糕减少一层，直至清除。

### 糖键锁与糖键（段 `028` / `038`）🟡

成对出现：糖键（`038`）是钥匙，糖键锁（`028`）是上了锁的格子。玩家消除糖键后，对应的糖键锁才会解开。

> ⚠️ 数据中 `028` 出现 7,984 次、`038` 出现 13,442 次，比例不严格 1:1，未必每个 `028` 都对应单一 `038`。

### 多层障碍（段 `109`–`163`）🟡

中后期关卡出现的复合障碍，每个格子有多层"血量"，每次相邻消除减一层（**层数 vs 变体的语义未严格确认**，见 `level-format.md` § 2.4）：

| 障碍名 | 段 ID | 段数 | 对应收集目标 | 证据 |
|---|---|---|---|---|
| 颜色簇（Color Cluster / Party Booster） | `109`–`120` | 12 | `item 27` | 🟡 段范围与食材 `107`-`108` 重叠待区分 |
| 糖衣（Sugarcoat） | `122`–`124` | 3 | `item 28` | 🟡 |
| 重型分层（Heavy Layered） | `129`–`133` | 5 | `item 29` | 🟡 |
| 瑞典鱼/糖绳（GummyRope） | `134`–`137` | 4 | `item 31` | ✅ C++: `GummyRopeGroupLogic` |
| UFO 方块 | `159`–`163` | 5 | `item 32` | 🟡 |

`qty` 的语义是**所有格子层数（或变体计数）的加权总和**，不是格子数。例如有 3 个段为 `130` 的障碍（若 `130` = 第 2 层），`qty` 贡献 `3×2 = 6`。

### 骷髅（Skull，段 `230`）✅

源码：`SkullLogic.cpp`、`SkullSceneObject.cpp`。会**重生**的障碍——清除后过几步又会出现在棋盘上。`item 39` 的 `qty` 是整关需要清除的总次数（含重生），所以 `qty` 通常远大于棋盘上最初放置的数量，无法从 `tileMap` 静态格子直接算出。

### 蛇障碍（段 `234`）✅

✅ **数据 100% 确认**：`item 42` 的目标，89/89 关共现。

### Orlock 怪物（段 `228`）✅

源码：`OrlockSceneObject.cpp`。✅ **数据 100% 确认**：`item 38` 的目标，125/125 关共现。是一种会"吸取"棋盘元素的怪物，对应 `orlocks` 字段配置。

---

## 四、特殊糖果

特殊糖果是消除 4 颗或更多糖果时产生的，威力更大：

| 特殊糖果 | 触发条件 | 效果 | tileMap 预置段 |
|---|---|---|---|
| 横向条纹糖 | 横向消除 4 颗 | 消除整行 | `045` |
| 纵向条纹糖 | 纵向消除 4 颗 | 消除整列 | `046` |
| 包装糖 | 消除 2×2 或 T/L 形 5 颗 | 3×3 范围爆炸两次 | `047` |
| 彩色炸弹 | 消除直线 5 颗 | 消除棋盘上所有同色糖果 | `054` |

"**预置**"的意思是：该格子在关卡开始时已经放置了这颗特殊糖果，不需要玩家自己触发生成。

### 辣椒糖（Pepper Candy，段 `051`）

消除时向特定方向冲击，打碎路径上的障碍物。

### 幸运糖（Lucky Candy，段 `079`–`083`）

消除后随机触发一种奖励效果（生成特殊糖果等），有 5 层强度，层数越高奖励越好。

### 青蛙（Frog，段 `044`）

一颗会移动的特殊糖果。玩家点击青蛙并选择目标格，青蛙跳过去消除周围糖果。`frogStomachSize` 字段控制青蛙每次跳跃需要先"吞下"多少颗同色糖果才能激活。

### 颜色固定（段 `055`–`061`）🟡

强制该格只生成指定颜色的糖果。`055`–`060` 共 6 段，**对应 6 种糖果颜色**。

⚠️ 6 段对应的具体颜色（紫/黄/红/橙/蓝/绿）暂无源码佐证。从数据看，6 种段在 `numberOfColours=2`–`6` 的关卡中都有出现，且与 `_itemsToOrder.item=1`–`6` 各自有 30%–50% 的关联（item 2 ↔ `057`、item 3 ↔ `056` 等），强烈说明：
- `055`–`060` 各自固定一种颜色 ✅
- `_itemsToOrder.item=1`–`6` 大概率是「按颜色收集糖果」目标 🟡

具体哪个段对应哪个 RGB 颜色，**需要 PlayBot 截图视觉识别后才能确定**。

`061` 出现极少（783 cells），可能是「第 7 色」或保留段，⚠️ 未确认。

### 椰子轮（Coconut Wheel，段 `062`）✅

✅ **数据 100% 确认**：与 `_itemsToOrder.item=24` 完全共现（342/342 关）。一种棋盘静态目标，名称来自 SEMIDURABLE 枚举的 `COCONUT_WHEEL = 24`。具体外观与机制需截图确认。

---

## 五、游戏模式

每一关属于一种游戏模式（`gameModeName`），决定了通关条件。22,205 关数据中实际出现 10 种模式，C++ 代码中还有 1 种线上未启用模式：

| 模式 | 通关条件 | C++ 类 |
|---|---|---|
| **Light up（点亮）** | 消除棋盘上所有果冻格 | `CGameModeJelly` ✅ |
| **Order（收集）** | 收集 `_itemsToOrder` 中指定数量的物品 | `CGameModeOrder` ✅ |
| **Jelly Order** | 同时完成点亮果冻 + 收集物品 | `CGameModeJellyOrder` ✅ |
| **Drop down（食材掉落）** | 让食材（`ingredients`）从出口（段 `010`）落出棋盘 | `CGameModeIngredients` ✅ |
| **Jelly Drop down** | 同时完成点亮果冻 + 食材掉落 | `CGameModeJellyIngredients` ✅ |
| **Order Drop Down** | 同时完成收集物品 + 食材掉落 | `CGameModeOrderIngredients` ✅ |
| **Rainbow Rapids** | 在彩虹急流轨道上引导糖果流向目标 | `CGameModeRainbowRapids` ✅ |
| **Rainbow Rapids Jelly/Order/Drop Down** | 彩虹急流 + 其他目标组合 | `CGameModeRainbowRapids*` ✅ |
| **Classic（经典）** ⚠️ | 仅靠分数，无果冻/收集目标 | `CGameModeClassic` —— 数据集中 0 关，疑似线上未启用 |

---

## 六、关卡序号与数据连续性

**结论：所有 22,205 关是单一连续关线，行号即关卡号，不存在多条独立关线混杂。**

验证依据：
- `all_levels.jsonl` 第 N 行的 `id_meta` 恒等于 N（1–22205），无间隙，无重复
- 游戏内 10 种游戏模式**混合分布**在同一条关线上（从第 1 关到第 22205 关），而不是各模式各自有一套编号
- 同一个 2000 关的区间内同时包含 6–10 种模式

Candy Crush Saga 的关卡设计思路是：用不同模式交替出现，保持玩家新鲜感，而不是"通关 Order 全部关卡后才解锁 Light up 关卡"——所有模式都在同一条进度线上。

---

## 七、哪些字段影响关卡难度

以下字段是评估关卡难度的主要维度：

### 7.1 步数（`moveLimit`）

**最直接的难度控制手段**。步数越少，留给玩家操作的空间越小。典型值：

- 简单关：30–50 步
- 中等关：20–30 步
- 困难关：10–20 步
- 极难关：≤10 步（通常配合简单棋盘保持可通关性）

### 7.2 棋盘形状（`tileMap` 中 `000` 分布）

`000` 空格越多，可用格越少，操作空间越受限。不规则形状（如两侧大面积 `000`）迫使玩家在狭窄区域内精确操作。`levelType` 中的 `LimitedPlaySpace` 和 `Sniping` 标签即反映此类关卡。

### 7.3 目标数量和类型（`_itemsToOrder`）

- **目标物品总量（`quantity` 之和）大**：需要消除更多次数。
- **目标为多层障碍**（如 `item 29` 重型分层 5 层）：每个格子要"打"多次，消耗更多步数。
- **目标为可重生障碍**（如 `item 39` 骷髅）：无法一次性清场，被迫持续消耗步数。
- **多个目标同时存在**：需要在有限步数内兼顾，协调难度倍增。

### 7.4 障碍物密度和层数

`tileMap` 中高层数障碍格子越多，需要消除的总"层数"越多。例如全场铺满 5 层糖霜（`023`）的关卡，每格至少要间接消除 5 次，步数消耗极高。

### 7.5 颜色数（`numberOfColours`）

颜色越多，凑齐三消的概率越低，关卡越难。`numberOfColours: 6` 比 `numberOfColours: 4` 明显更难匹配。

### 7.6 生成点与动态障碍（`005` + `026` 配对，配合 `evilSpawner*` 字段）

含 spawner（顶行 `005`+`026` 配对）的关卡里，障碍物可以被源源不断地"刷新"进棋盘——玩家无论怎么清除都追不上生成速度，必须在正确的节奏下高效消除。
更激进的"邪恶生成器"由 `evilSpawnerCount` / `evilSpawnerInterval` / `evilSpawnerAmount` 字段配置（C++ 类 `CViewEvilSpawnerComponent`）。

### 7.7 巧克力生成器（`024`）

每一步都会扩散，不管理就会吞噬整个棋盘，迫使玩家分心处理，是强制提升难度的设计。

### 7.8 特殊糖果预置（`045`–`047` / `054`）

**反向降低难度**：预置特殊糖果意味着玩家一开局就有强力工具，关卡整体难度通常偏低或设计为教学关。

### 7.9 `levelType` 标签

| 标签 | 难度含义 |
|---|---|
| `Explosive` | 含大量炸弹/爆炸机制，节奏紧张 |
| `Excavation` | 需先挖开覆盖物才能操作，步数消耗倍增 |
| `Sniping` | 操作空间极小，对精准度要求高 |
| `LimitedPlaySpace` | 可用格极少，连锁难度大 |
| `Endurance` | 步数多但目标量大，拼持久 |
| `Puzzle` | 唯一解谜题，容错率极低 |

### 7.10 随机种子（`randomSeed`）

- `randomSeed: 0`（绝大多数关卡）：完全随机生成糖果，每次玩结果不同。
- `randomSeed: 非0`：固定初始糖果布局，关卡每次开始时棋盘一样，可重现。这类关卡通常是 `Puzzle` 谜题关，设计者精心布置了唯一解。

---

## 八、中后期高级机制（C++ 类名 ✅，棋盘段映射多数 ⚠️）

下列机制在反编译的 `libcandycrushsaga.so` 中有独立 C++ 类（源码路径 `packages/ccsm_switcher/source/common/...`），但**对应的 tileMap 段 ID 大多未确认**。它们多出现在中后期高难度关卡。

### 8.1 邪恶生成器（Evil Spawner）✅

源码：`ViewEvilSpawnerComponent.cpp`、`CEvilSpawnerBehaviorFactory`、`CBehaviorEvilSpawnerDamageComponent`。

不同于 `005`+`026` 的"被动" spawner，邪恶生成器是**主动周期性生产 blocker** 的元素：每隔 `evilSpawnerInterval` 步、产生 `evilSpawnerAmount` 个 `evilSpawnerElements` 类型的元素，最多 `evilSpawnerCount` 个。是中后期关卡难度爆表的来源。

字段（顶层）：
- `evilSpawnerCount`：场上 spawner 数量
- `evilSpawnerElements`：生产元素类型
- `evilSpawnerAmount`：每次生产数
- `evilSpawnerInterval`：生产间隔（步数）

### 8.2 鱼雷生成器（Torpedo Spawner）✅

源码：`CTorpedoSpawner` / `ITorpedoSpawner`。⚠️ 具体机制和段 ID 待截图确认，疑似从 spawner 处发射"鱼雷"清除路径上的 blocker。

### 8.3 巧克力生成器（Chocolate Spawner，段 `024`）✅

已在 § 三介绍。源码：`IChocolateSpawner`、`IChocolateSpawnerProvider`。

### 8.4 蛋奶饼障碍（Waffle）✅

源码：`SpawnerTargetHandlerWaffle.cpp`、`CBoardItemWaffleBehavior`、`CBoardItemWafflePropertiesV1`，纹理 `block_waffle1.png`–`block_waffle5.png`。

✅ **5 个层级或变体**（来自字符串 `waffle1 | waffle2 | waffle3 | waffle4 | waffle5 | doublecolorbomb`）。注意末尾的 `doublecolorbomb` 暗示蛋奶饼**消除完成时可能合成双重彩色炸弹**。

⚠️ tileMap 段 ID 未确认，疑似在 `140`–`158` 或 `164`–`181` 高频未知段范围内。

### 8.5 奇妙包装糖（Wonderful Wrapper）✅

源码：`WonderfulWrapperSceneObject.cpp`、`CBoardItemWonderfulWrapperBehavior`、`CWonderfulWrapperGroupLogic`。

带"丝带"装饰的特殊包装糖，消除时会**释放预设的礼物（gifts）**——`SetGifts(SBoardItemGift &, SBoardItemGift &)` 表明每个奇妙包装糖能放 2 份礼物，礼物本身是其他 board item（特殊糖、booster 等）。

字段：`wonderfulWrappers`（顶层）

### 8.6 邦邦闪电（Bonbon Blitz）✅

源码：`BonbonBlitzLogic.cpp`、`CBehaviorBonbonBlitzComponent`。

5 种子类型：`BonbonBlitzBomb`、`BonbonBlitzColumn`、`BonbonBlitzRow`、`BonbonBlitzWrap`、`BonbonBlitzFish` —— 即"色色相消时按颜色产生不同特殊糖果"的高级合成机制。`TryAttackBlocker(CBlocker &, ECandyColor, ...)` 表明该糖果攻击 blocker 时会按颜色触发不同效果。

### 8.7 糖果眼镜蛇（Candy Cobra）✅

源码：`CandyCobraSceneObject.cpp`、`CandyCobraBasketSceneObject.cpp`、`CBoardItemCandyCobraBehavior`、`CDestructionPlanCandyCobra`。

是一种**爬行的多段糖果**：有「蛇本体（CandyCobraSceneObject）」+「蛇篮（CandyCobraBasketSceneObject，蛇的"巢穴"）」。

字段：`candyCobras`（顶层）

⚠️ 与段 `234`（Snake / item 42）是不同的两个机制。Snake 是简单的蛇障碍；CandyCobra 是更复杂的爬行糖果系统。

### 8.8 鱼罐头（Fish Pod）✅

源码：`BehaviorFishPodAttackComponent.cpp`、`CFishPodViewFactory`、`CFishPodBehaviorFactory`。

`TryAttackBlockerByBooster(CBlocker &, EBooster)` —— 推测是当玩家使用 booster 时被触发的"鱼罐头"反击型 blocker。⚠️ 段 ID 未确认。

### 8.9 彩虹扭转（Rainbow Twist）✅

源码：`BehaviorRainbowTwistComponent.cpp`、`CRainbowTwistBehaviorFactory`、`CRainbowTwistViewFactory`、字符串 `HasRainbowTwistConnector`、`Invalid RainbowTwist position!`。

彩虹急流（Rainbow Rapids）模式中的特殊"扭转/连接器"，会改变彩虹路径方向。

### 8.10 Orlock 怪物 ✅

源码：`OrlockSceneObject.cpp`、`OrlockView.cpp`、`GameLogicOrlock.cpp`、`OrlockRemovalLogic.cpp`。

✅ **段 `228` 100% 关联**（item 38，125/125 关）。是大型多格怪物（`orlock_multitile_border.xml` 等资源），会"吸取"或"破坏"棋盘元素。

字段：`orlocks`（顶层），还存在 `OrlockDisableLollipopHammerLogic` 表明该怪物会**免疫棒棒糖锤 booster**。

### 8.11 糖果炮（Candy Cannon）✅

源码：`CandyCannon.cpp`、`CandyCannonShuffler.cpp`、`CannonView.cpp`。

字段：
- `cannons`：糖果炮所在列索引数组
- `ammoCannons`：弹药炮配置

会从特定列发射糖果，是一种特殊 spawner。

### 8.12 传送门 / 门（Portal / Gate）✅

- **Portal（段 `011`/`012`/`013`）**：传送对，糖果掉到入口会从出口出来。`portals` 字段配置。
- **Gate（顶层 `gates` 字段）**：从真实关卡数据看是 `[[fromRow, fromCol], [toRow, toCol], [direction], [extra]]` 四元组数组，是单向通道（与 portal 不同，gate 是棋盘上"邻居关系"的重新连接）。

### 8.13 食材类型分级 ✅

源码字符串：
- `CandyIngredientCommon01` / `02` / `03`（常见食材，如樱桃 cherry）
- `CandyIngredientRare01` / `02`（稀有食材，如榛子 hazelnut）
- `CandyIngredientSpecial01` / `02`（特殊食材）

`ingredients` 字段配置具体食材类型；`ingredientSpawnDensity` / `maxNumIngredientsOnScreen` 控制生成节奏。

