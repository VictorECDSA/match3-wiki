# nvk/llm-wiki

> 仓库：https://github.com/nvk/llm-wiki

## 工具定位

nvk/llm-wiki 是一个运行在 Claude Code 环境内的零依赖 wiki 编译器。它的核心机制是同时调度多个 LLM 子智能体并行研究同一主题，汇总结果后写出 Obsidian 原生 Markdown wiki 页面。与普通的单次 AI 问答不同，它产出的是一个可持续维护、有审计日志的知识库。

## 工作原理

### 三层架构

| 层级 | 目录 | 内容 |
|---|---|---|
| 原始素材层 | `raw/` | 网页剪藏、PDF、视频转录、笔记 — 只增不改 |
| Wiki 页面层 | `wiki/` | LLM 生成的 Markdown 文件，每个主题一页 |
| 配置/模式层 | `CLAUDE.md` | 定义研究范围、主题分类、质量标准、智能体指令 |

### 并行多智能体

研究一个主题时，系统同时启动多个子智能体（可配置为 5 / 8 / 10 个）。每个智能体：
- 从不同角度独立研究同一个主题
- 各自检索 `raw/` 中的源文件
- 输出一份独立草稿

主智能体最后合并所有草稿，处理矛盾，写出最终 wiki 页面。

**并行的价值**：
- 减少确认偏误——各智能体不共享中间状态
- 提高覆盖率——对素材库进行并行探索
- 缩短总用时——相比顺序研究快得多

### 反确认偏误设计

每个子智能体都会收到一个**需要反驳或压力测试的论点**，而不是去验证它。合并步骤明确要求主智能体暴露各草稿之间的分歧和边界案例。这是对 LLM 倾向于同意问题前提这一默认行为的刻意颠覆。

### 只增不改的审计日志

每次编译运行都会追加记录到 `history/` 目录，记录：时间戳、参考的源文件、启动的智能体、新增/更新的页面。任何一个 wiki 页面都能追溯到产生它的具体来源和运行记录。

## 核心命令

| 命令 | 作用 |
|---|---|
| `/wiki:ingest` | 处理 `raw/` 中的新文件——切片、建索引、注册到 schema |
| `/wiki:research <主题>` | 启动并行智能体研究某主题，写入/更新对应 wiki 页面 |
| `/wiki:compile` | 全量重建——对当前 raw 语料库重新研究所有页面 |
| `/wiki:query <问题>` | 检索 wiki 页面 + raw 源文件作答，不写入新页面 |
| `/wiki:lint` | 健康检查：断链、孤立页面、过时页面（源文件比页面新） |

## 使用方法

### 目录初始化

```
项目根目录/
  raw/          ← 把所有原始资料放这里
  wiki/         ← 编译器写到这里
  history/      ← 审计日志
  CLAUDE.md     ← schema / 配置文件
```

### 典型工作流

**场景：新增一批 AppMagic 收入数据，更新 Royal Match 的 wiki 页面**

```
1. 从 AppMagic 导出 CSV，保存到：
   raw/market/appmagic/2025-04/top-games.csv

2. 用 Web Clipper 剪藏 Royal Match 应用详情页，自动保存到：
   raw/market/appmagic/2025-04/royal-match-profile.md

3. 在 Claude Code 项目目录下运行：
   /wiki:ingest
   → 系统扫描 raw/ 下的新文件，注册到素材索引
   → 输出：Found 2 new files, linked to topics: [market/top-grossing, entities/royal-match]

4. 运行：
   /wiki:research entities/royal-match
   → 启动 8 个并行子智能体研究 Royal Match
   → 各智能体从不同角度（收入、UA策略、机制、竞品对比）独立研究
   → 主智能体合并结果，写入 wiki/entities/royal-match.md

5. 每月或大批新素材后运行：
   /wiki:lint
   → 检测哪些 wiki 页面的源文件比页面本身更新（说明页面已过时）
   → 检测断裂 wikilink 和孤立页面

6. 季度性全量重建：
   /wiki:compile
   → 重新研究所有 wiki 页面（耗时较长，token 消耗高）
```

### Obsidian 集成

输出页面使用 Obsidian wikilink 语法（`[[页面名]]`）和 YAML frontmatter。把 `wiki/` 文件夹放进 Obsidian vault，即可免费获得图谱视图、反向链接和全文搜索。

## 在 match3-wiki 项目中的作用

### 核心编译引擎

nvk/llm-wiki 是 match3-wiki 工具链的**主知识编译引擎**：

```
raw/（网页剪藏、市场报告、视频转录）
  ↓  /wiki:ingest
  ↓  /wiki:research
wiki/（每个主题一个 Markdown 页面）
  ↓  graphify
graph.json + Obsidian vault
```

### 具体使用场景

**买量素材数据处理**：从 Facebook Ad Library 和 TikTok Creative Center 下载的广告素材报告进入 `raw/ua/`，运行 `/wiki:ingest` + `/wiki:research` 后合成 `wiki/growth/ua-creative-trends-2025.md` 等页面。

**市场数据合成**：AppMagic 和 Sensor Tower 的导出文件（CSV、PDF 报告）进入 `raw/market/`，编译后产出 `wiki/market/match3-revenue-benchmarks.md`、`wiki/market/top-ua-spenders.md` 等页面。

**玩法机制文档化**：`raw/mechanics/` 中的游戏设计笔记和竞品分析，编译为 `wiki/mechanics/candy-crush-booster-system.md` 等页面。

**反偏见竞品分析**：并行智能体 + 论点反驳设计对竞品分析特别有价值——单智能体的答案容易强化对市场领导者的既有假设。

### Phase 1 重点（第 1–8 周）

PRD 将 Phase 1 定为纯内容阶段。nvk/llm-wiki 是这一阶段的主要工具：将 raw 素材入库，研究三消知识体系中的所有主题，产出初始 wiki 语料。目标：覆盖三消经典和解谜冒险子品类的 50+ 个 wiki 页面。

### CLAUDE.md 配置要点

`CLAUDE.md` 是整个 wiki 编译器的"大脑"——它告诉智能体研究什么、怎么研究、质量标准是什么。以下是 match3-wiki 的 `CLAUDE.md` 实际写法示例：

```markdown
# match3-wiki Schema

## 主题分类

wiki/ 目录按以下分类组织，每类有对应的质量要求：

### market/（市场数据）
必须包含：收入前 10 产品列表、地区分布、数据年份（数据不得超过 6 个月）
数据来源优先级：Sensor Tower > AppMagic > 行业博客

### mechanics/（玩法机制）
必须包含：至少 3 个游戏案例、玩家心理依据、已知实现变体
数据来源优先级：开发者事后复盘 > GDC 分享 > 玩家社区分析

### entities/（单款游戏档案）
必须包含：开发商、上线日期、收入层级（高/中/低）、核心机制标签、
          买量策略描述、D1/D7/D30 留存（如可查）
数据来源：AppMagic + Sensor Tower + Facebook Ad Library

### growth/（买量与增长）
必须包含：素材格式描述、平台（Meta/TikTok/Google）、首次出现时间
数据来源：Facebook Ad Library > TikTok Creative Center

## 智能体并发数

- market/ 和 entities/ 主题：8 个智能体（数据量大，需要多角度校验）
- mechanics/ 主题：5 个智能体（更多是定性分析）
- growth/ 主题：8 个智能体（竞品数量多）

## 质量门（所有页面）

- 禁止写"可能"、"也许"之类的模糊词，用"根据 AppMagic 2025-Q1 数据"这类归因表达
- 每个页面末尾必须有 ## 来源 section，列出引用的 raw/ 文件
- 页面长度：500–2000 字，超过 2000 字拆分为子页面
```

这份配置使编译器知道：研究一个 `entities/` 页面时启动 8 个智能体、从 AppMagic/Sensor Tower 优先取数、确保写上来源、长度不超过 2000 字。

## 局限性

- 需要 Claude Code 运行环境，不是独立 CLI 工具
- raw 素材稀少时质量下降——素材越多，页面越好
- 没有内置的 raw 去重——重复文件会膨胀 token 用量
- 如果 `raw/` 持续增长但不重新运行 `/wiki:compile`，wiki 页面会与素材逐渐偏离
