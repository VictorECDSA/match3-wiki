# Match Game Mechanics: An Exhaustive Survey（消除类游戏机制：一次详尽的调查）

**原文标题**：Match Game Mechanics: An exhaustive survey
**作者**：Jonathan Bailey (Blogger)
**发布日期**：2015 年 2 月 27 日
**阅读时长**：14 分钟
**来源**：Game Developer (gamedeveloper.com) - Design / Commentary 专栏
**特色标签**：Featured Blog（精选社区博客）
**贡献者更新**：Christopher Floyd, Robert Wahler, Lars Bull, Kevin Ryan
**原文链接**：https://www.gamedeveloper.com/design/match-game-mechanics-an-exhaustive-survey

---

## 引言

在 Plinq 工作室，作者与同事 Herman Tulleken 几周前开始构建一个消除类游戏工具。他们玩并分析了大量消除游戏，以解构其机制。本文分享了这些研究发现，属于一个更大规模的研究与开发项目的一部分。

本文只涵盖：**在网格上进行、2D 的、单层的**消除游戏。

Jesper Juul 在论文《Swap Adjacent Gems to Make Sets of Three》中将消除类游戏定义为"玩家的目标是在网格上操纵方块以创建匹配的电子游戏"。

设计师面临的挑战是：休闲玩家希望立即上手这类游戏，必须有熟悉感而不要陡峭学习曲线；同时游戏又需要足够的独特性以在竞争中脱颖而出并留住玩家。这些差异常常很微妙——例如 Bejeweled 相比前作引入了无时限模式。因此，消除游戏的演化比其他类型更渐进，形成了大量相似游戏（常被贴上"克隆"标签），但也使其比许多其他类型更容易分析。

---

## 定义（Definitions）

- **Grid（网格）**：由单元格构成的结构化排列。常用正方形与六边形网格。
- **Cell（单元格）**：一个容器，可以是空的或被填充的。
- **Tile（方块/图块）**：填充单元格的对象。一个单元格最多容纳一个方块。
- **Block（块）**：作为一个单位被操作的一组相连方块。很多游戏中每个 block 只含一个 tile。
- **Matching tile game（消除类游戏）**：玩家目标是通过在网格上操作 block 以在 tile 之间创建匹配的游戏。
- **Match（匹配）**：满足游戏匹配规则的一组方块。最常见的规则是三个同色相连方块。
- **Color（颜色）**：区分方块的属性，可以是颜色、形状、花纹或数字。
- **Gravity（重力）**：将所有方块朝特定方向移动的力。
- **Clear（清除）**：方块从游戏中移除。
- **Line（线）**：正方形网格中是行或列；三角形/六边形网格中是首尾相连成一直线的一组单元格。
- **Combo（连击）**：同时产生的多次匹配。例如 Bejeweled 中交换两个方块后，两个方块都各自与别的方块形成了匹配。
- **Cascades（级联）**：连续发生的匹配。例如 Bejeweled Twist 中玩家操作触发自动匹配后，新方块掉入空格再次形成自动匹配。

---

## 游戏分类（Game classification）

将所有消除类游戏归为三大类，反映游戏循环和目标的模式：

1. **Elimination game（清空型）**：匹配方块以清空或部分清空一个不会补充的网格。网格开始可能是满的或部分满的（Chain Shot! / SameGame）。
2. **Avoidance game（避免型）**：匹配方块以防止网格被填满或方块达到网格边缘（Collapse!、Color Lines）。
3. **Farming game（养成型）**：在始终保持满格的网格上匹配。每次匹配并清除后就会添加新方块，目标是最大化或达到某一指标（Bejeweled）。

---

## 网格（Grid）

### 网格拓扑（Topology）
- 正方形（Bejeweled, Around the World in 80 Days）
- 六边形（Fractal, Same Hexagon）
- **一维特殊情况**：单线排列的单元格，可能弯曲（Zuma）

### 网格形状与尺寸
大小和形状多样。典型是 **8×8 矩形**（Bejeweled 3, Puzzle Quest）。也有网格尺寸在游戏过程中变化的例子（Uo Poko, Puzzle Bobble, Tetris Plus 2）。

---

## 块结构（Block structure）

四种结构，除第一种外均为多方块 block：

- **Single-tile（单方块）**：每个 block 只含一个方块（Bejeweled）
- **Monochromatic（单色）**：同类型方块组成不同形状的 block（Tetris）
- **Monomorphic（同形）**：相同形状的 block 使用不同类型方块（Columns）
- **Mixed（混合）**：不同形状 block 使用不同类型方块（Groovin' Blocks）

---

## 方块集结构（Tile set structure）

### 方块属性分类

1. **Clearing type（清除类型）** —— 每个方块有且只有一个清除属性：
   - **Color tile**：可用涉及颜色的规则匹配
   - **Wildcard（万能牌）**：涉及颜色的规则下可以替代任何颜色
   - **Sinker（下沉物）**：通过让它到达网格底部来清除
   - **Activator（激活物）**：通过点击清除
   - **Non-clearing tile（不可清除）**：无法被清除

2. **Gravity properties（重力属性）**：受重力 (Falling) / 不受重力 (Floating)；以及方向

3. **Game action（游戏行为）**（清除时触发）：生成新方块 / 给予奖励 / 结束游戏

#### 示例
- Bejeweled 中彩色方块是"受重力彩色 tile，无游戏行为"
- Candy Crush Saga 中的糖霜（Icing/Meringues）是"浮空 wildcard，无游戏行为"
- Bejeweled 3 中的 hypercube 是"受重力 wildcard，清除时给予奖励"
- Azkend 中的护符是"受重力 sinker，清除时结束游戏"
- Triple Town 中的宝箱是"浮空 activator，清除时给予奖励"
- Threes 中的数字方块是"浮空 color tile，清除时生成新方块"

### 方块集附加结构
- **Sequence（序列）**：按序列排列的彩色方块（Triple Town, Threes, Gems with Friends）
- **Multi-axis（多轴）**：存在多种匹配属性（如颜色与花纹），可按任一属性进行匹配（Passage 4 XL）

---

## 块生成（Block Spawning）

### 生成算法
- 随机（Tetris）
- 预定顺序
- 动态调整难度（Candy Crush Saga）
- 从最近清除的单元格中选取
- 从固定批次随机排序（Threes）
- 从游戏中剩余方块选取（Puzzle Bobble）

### 生成位置
- 在网格边缘：
  - 从被清除单元格的那一列（Bejeweled）
  - 从中央单元格（Tetris, Puyo Puyo）
  - 从随机单元格（Meteos）
  - 按顺序，比如总是从左到右（Tidalis）
  - 从每一个单元格（Tetris Attack, Collapse!）
- 在已被清除的单元格中
- 在任一空单元格（Color Lines）

### 生成数量
- 固定数量（Color Lines）
- 填满所有空单元格（Bejeweled）
- 足以保证某一列达到最低高度（Tidalis）

### 生成时机
- 按时间（Collapse!）
- 形成匹配时（Bejeweled）
- 未形成匹配时（Color Lines）
- 级联完成后（Tetris Attack）
- 每回合之后（Ultimate-4）
- 每 N 回合后
- 玩家主动添加时（Stickets）

---

## 玩家行为（Player actions）

### Click Match（点击匹配）
玩家点击一组匹配方块中的任意一个，清除整组（Collapse!, Same Hexagon）。

### Chain Match（连锁匹配）
玩家依次点击或拖拽一组匹配方块，清除它们（Azkend, Jelly Splash, 4 Elements）。

### Place（放置）
玩家将一个新 block 放到网格上。可以对下一个 block 无选择（Columns），或从若干可放 block 中选择（Stickets）。可以放在任何形状匹配的空单元格组（Color Lines, Stickets），或限定区域内（Might & Magic: Clash of Heroes, Columns）。

### Rotate（旋转）
- **方块旋转**：玩家旋转两个或更多单元格中的方块——常是交换两格（Bejeweled 3）、三格（Hexic）或四格（Bejeweled Twist）。
- **列旋转**：玩家旋转两列方块（Mario & Yoshi）。

### Line Swipe（整行滑动）
玩家整行滑动方块，线是环形的（Chuzzle, Metronous）。

### Grid Swipe（整个网格滑动）
玩家滑动整个网格，所有方块朝该方向移动直到没空间或形成匹配（Threes）。

### Manipulate Block（操作 block）
由两个维度定义：
- **如何操作**：旋转 block（Tetris）或改变 block 内部方块位置（Columns）
- **何时操作**：放置前（Tetris）或放置后（Chain Shot）

### Manipulate Gravity（操作重力）
- 玩家开关重力（Gravity Switch Puzzle Match）
- 玩家改变重力相对网格的方向，可能通过旋转网格（Vizati, Spinzizzle）

### Remove（移除）
玩家点击单个方块将其清除。

### Shuffle（洗牌）
玩家把部分或全部方块随机移到不同单元格（Candy Crush Saga）。

### Manipulate Spawning（操作生成）
玩家提高或降低 block 生成速率（Meteos, Tetris Attack, Tidalis）。

---

## 自动行为（Automatic Actions）

### Block Spawning（块生成）
已在前文讨论。

### Auto-match（自动匹配）
在匹配不是玩家行为的游戏中，每次玩家输入后会触发自动匹配。若玩家输入形成了匹配组，自动匹配将清除它们。自动匹配也能在无玩家输入时作为级联发生。

### Gravity（重力）
重力会影响进入网格的新 block，或让方块移入被清除后的空格中。重力可指向任何方向，包括朝向某条边（Bejeweled）或朝向网格中心（Fortex Zen）。

重力方向可在游戏中改变，取决于哪些方块被清除（Super Collapse!）或如何被清除（chain match 的方向，Puzzle Quest: Galactrix）。

### Repulsion（排斥）
放置一个 block 会推动所有相邻方块远离它。被推方块形成链式反应，使该线上所有方块向外移动一格（Fractal）。

### Attraction（吸引）
被清除的方块由相邻单元格中的方块填补（Trigon）。

---

## 匹配条件（Matching conditions）

### 构成匹配所需的方块数量
最常见是 3（Bejeweled），但也有：
- 2（Threes）
- 4（Lumines, Gem Huntz）
- 7（Fractal）
- 10（Tetris）

### 匹配所需的方向与形状
常见形状：
- 水平或垂直直线
- L 形 / T 形 / 十字形
- 方形 / 三角形 / 六边形

### 特殊情况
- 匹配方块之间可以被非匹配方块分隔：
  - 分隔格必须为空，且匹配方块须在同一轴上（Totemo, Color Tiles）
  - 分隔格可被非匹配方块填充，匹配方块须在同一轴，所有中间的非匹配方块也一起清除（Mario & Yoshi）
  - 分隔格可被非匹配方块填充，匹配方块不必在同一轴（Tidalis）
- 匹配方块形成一个闭合形状，清除所形成闭合区域内部的所有方块（Quarth）
- 按每个方块属性以任意形状匹配（Tidalis）

---

## 奖励（Rewards）

### 奖励类型
- 分数
- 特殊方块
- 特殊动作

特殊方块或特殊动作的效果可互换，例如：额外时间 / 时间重置 / 额外步数 / 清除一整行 / 清除邻近方块 / 清除所有某种颜色的方块

### 奖励触发条件
可以是单一条件，也可以是多条件组合。

---

## 游戏结束条件（Game-end conditions）

### 胜利条件
- 网格被清空（Puzznic）
- 玩家达到指定匹配数或指定分数（Bejeweled）
- 玩家完成指定的一组匹配（Jewel Fever）
- 玩家清除了某个特定方块（Azkend）

### 失败条件
- 网格被填满（Stickets）
- 方块触及网格边缘（Tetris, Collapse!）
- 玩家资源耗尽（Fractal）
- 玩家无可用移动（Threes）

---

## 价值与意义

这是一篇 **Match-3 机制的经典分类学（taxonomy）文献**。它把所有可能的设计维度（拓扑、玩家行为、匹配条件、重力、生成、自动匹配、奖励、结束条件）拆解为可枚举的选项，是设计新关卡或新机制时极佳的"组合工具表"。

---

**作者信息**：Jonathan Bailey，Game Developer 博主。本文由社区撰写，属于 Game Developer Blogs 精选内容。
