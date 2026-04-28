# GBrain

> 开源仓库：https://github.com/garrytan/gbrain
> 作者：Garry Tan（Y Combinator 总裁兼 CEO）
> 许可证：MIT

## 工具定位

GBrain 是 Garry Tan 开源的**个人生产级 AI 记忆系统**，为 OpenClaw / Hermes / Claude Code / Cursor 等 AI Agent 提供长期记忆与知识检索层。它的核心主张是：

> "你的 AI Agent 很聪明但健忘。GBrain 给它一个大脑。"

技术形态上，GBrain 是一个 **TypeScript CLI + MCP 服务器**，把一个 Git 管理的 Markdown 仓库编译进 Postgres + pgvector，同时附带自动抽取的类型化知识图谱、混合检索管道、后台任务队列（Minions）和 29 个 Agent 技能（Skills）。

作者自用版本规模：17,888 页面 / 4,383 人物 / 723 公司 / 21 个自主定时任务，公开基准测试中 P@5 = 49.1%、R@5 = 97.9%，优于 ripgrep-BM25 和纯向量 RAG。

在 match3-wiki 工具链中，GBrain 可作为**"wiki 之上的 Agent 记忆层"**——让 AI 助手基于持续积累的 wiki 内容做研究、写作、定时摘要，而不是每次都从零开始。

## 原理介绍

### 核心理念：Compiled Truth × Timeline × Compound Daily

GBrain 的知识模型只有三条原则：

1. **Repo 是真相之源（source of truth）**：所有知识都是 Markdown 文件，人类可编辑，Git 可版本化。GBrain 本身只是**检索层**。
2. **Compiled Truth + Timeline 双层结构**：每个页面上半部分是"当前最佳理解"，可被覆盖重写；下半部分是"时间线"，只追加不修改。
3. **Compound Daily（每日复利）**：每一次 Agent 交互都应让大脑更聪明——要么修复引用、要么抽取实体、要么连上新关系。

### 架构与核心模块

```
┌──────────────┐    ┌───────────────────┐    ┌──────────────┐
│  Brain Repo  │    │      GBrain       │    │   AI Agent   │
│   (git)      │    │    (检索层)       │    │              │
│              │    │                   │    │  29 个 Skills│
│ markdown 文件│───▶│ Postgres+pgvector │◀──▶│   + MCP      │
│ = 真相之源   │    │  ┌─────────────┐  │    │              │
│              │◀───│  │ 混合检索管道 │  │    │ 读/写/富化   │
│              │    │  ├─────────────┤  │    │              │
│ 人类可读可写 │    │  │ 知识图谱    │  │    │ HOW 使用大脑 │
│              │    │  ├─────────────┤  │    │              │
│              │    │  │ Minions 队列 │  │    │              │
│              │    │  └─────────────┘  │    │              │
└──────────────┘    └───────────────────┘    └──────────────┘
```

**分层原则**：Repo 存真相，GBrain 做检索和自动化，Agent 通过 skills 决定"策略"。三层解耦，任何一层坏掉都能单独修。

#### 核心模块详解

**1. 引擎层（可插拔）**

```
CLI / MCP Server
       │
  BrainEngine interface
       │
   ┌───┴────┐
PGLiteEngine   PostgresEngine
(默认本地)      (Supabase)
   │              │
~/.gbrain/      Supabase Pro
brain.pglite    $25/月
内嵌 PG 17.5
```

开箱即用是 PGLite（内嵌 Postgres），`gbrain init` 两秒就绪；需要多端协作或规模放大时，`gbrain migrate --to supabase` 一键切换到云端，反向亦然。

**2. 知识模型：Compiled Truth + Timeline**

```markdown
---
type: concept
title: Do Things That Don't Scale
tags: [startups, growth]
---

# Compiled Truth（编译后的真相）
当前最佳理解。随证据更新而重写。

---

# Timeline（时间线）
- 2013-07-01: Paul Graham 发表原文
- 2024-11-15: W25 kickoff 演讲引用
- 2026-02-03: Meeting with founders, 讨论 pivot
（仅追加，永不修改）
```

这种结构让大脑**既保留了事实演进轨迹，又维护了一个随时可用的"当前结论"**，避免 Agent 读到过时信息。

**3. 知识图谱（零 LLM 自动布线）**

每次写入页面时，GBrain 用正则 + 模式匹配抽取类型化关系：

- `attended`（某人 / 某会议）
- `works_at`（"X 的 CEO"、"CTO of Y"）
- `invested_in` / `founded` / `advises`

代码块会被剥离避免伪阳性，陈旧链接自动回收。**全程零 LLM 调用**，成本 $0、速度毫秒级。

**4. 混合检索管道**

```
Query
 ├─▶ 意图分类（entity / temporal / event / general）
 ├─▶ 多查询扩展（Claude Haiku 改写 3 次）
 ├─▶ 并行：向量检索（HNSW cosine）+ 关键词检索（tsvector）
 ├─▶ RRF 融合：score = Σ 1/(60+rank)
 ├─▶ 余弦重打分 + Compiled Truth 加权
 ├─▶ 反向链接加权（被引多的页面权重高）
 └─▶ 4 层去重 → 结果
```

这条管道是 GBrain 能跑到 R@5 = 97.9% 的关键——单靠向量或单靠 BM25 都不够。

**5. Minions（持久化后台任务队列）**

基于 Postgres 的 cron + 任务队列。关键对比：

| 指标 | Minions | 子 Agent 派发 |
|---|---|---|
| 耗时 | **753ms** | >10000ms（经常超时） |
| Token 成本 | **$0.00** | ~$0.03/次 |
| 成功率 | **100%** | **0%** |
| 内存/任务 | ~2 MB | ~80 MB |

**路由规则**：确定性任务（同输入→同输出）交 Minions；需要 LLM 判断的交子 Agent。这条规则让 GBrain 能稳定跑 21 个定时任务。

**6. 29 个 Skills（Agent 行动手册）**

| 类别 | 关键技能 |
|---|---|
| Always-on | signal-detector、brain-ops |
| 摄取 | ingest、idea-ingest、media-ingest、meeting-ingestion |
| 大脑操作 | enrich、query、maintain、citation-fixer、publish、data-research |
| 运营 | daily-task-manager、cron-scheduler、reports、minion-orchestrator |
| 身份/安装 | soul-audit、setup、migrate、briefing |
| 骨架/测试 | skill-creator、skillify、skillpack-check、smoke-test |

技能即 Markdown 文件（`skills/*.md`），通过 `skills/RESOLVER.md` 分派。Agent 不需要改代码，读技能文件就能知道"下一步该干嘛"。

### 数据流

```
信号到达（会议 / 邮件 / 推文 / 语音 / 链接）
        │
        ▼
Signal detector 并行捕获想法 + 实体（不阻塞主流程）
        │
        ▼
Brain-ops：先查大脑（gbrain search / get）
        │
        ▼
携带完整上下文响应用户 / 下游 Agent
        │
        ▼
写入：更新大脑页面 + 添加引用
        │
        ▼
自动链接：抽取类型化关系（零 LLM）
        │
        ▼
同步：gbrain 索引变更，供下次查询
```

**实体分层富化**（避免对低频实体过度花钱）：

- 提及 1 次 → Tier 3 存根页（仅记录链接）
- 跨源 3 次 → Tier 2（web + 社交富化）
- 会议或 8+ 次提及 → Tier 1（完整管道，含 LLM 摘要、背景调研）

## 详细用法

### 安装方式

**前置依赖：Bun**

GBrain 用 Bun（不是 Node）作为运行时，必须先装 Bun，否则 `bun install / bun link` 会报 `command not found: bun`。

```bash
# macOS / Linux 官方脚本（推荐）
curl -fsSL https://bun.sh/install | bash
# 装完把下面两行加到 ~/.zshrc 或 ~/.bashrc（脚本通常会自动加）
#   export BUN_INSTALL="$HOME/.bun"
#   export PATH="$BUN_INSTALL/bin:$PATH"
source ~/.zshrc
bun --version

# 或用 Homebrew
brew install oven-sh/bun/bun

# 或用 npm（已有 Node 时）
npm install -g bun
```

**方式 1：Agent 平台一键安装（推荐）**

把下面这行粘贴到你的 OpenClaw / Hermes / Claude Code 对话：

```
Retrieve and follow the instructions at:
https://raw.githubusercontent.com/garrytan/gbrain/master/INSTALL_FOR_AGENTS.md
```

约 30 分钟完成：克隆仓库、装依赖、建库、加载 29 个技能、配置定时任务。

**方式 2：独立 CLI**

```bash
git clone https://github.com/garrytan/gbrain.git
cd gbrain && bun install && bun link
gbrain init                        # 本地 PGLite 大脑，2 秒就绪
gbrain import ~/notes/             # 索引已有的 markdown
gbrain query "我的笔记里有哪些主题？"
```

> ⚠️ 官方提示：**不要用** `bun install -g github:garrytan/gbrain`，Bun 全局安装会阻塞 postinstall，迁移脚本不会运行。

### 核心命令速查

**设置与迁移**

```bash
gbrain init                               # 创建大脑（PGLite 默认）
gbrain migrate --to supabase|pglite       # 引擎迁移
gbrain upgrade                            # 自升级
```

**页面操作**

```bash
gbrain get <slug>                         # 读取（支持模糊匹配）
gbrain put <slug> < file.md               # 写入（自动版本化）
gbrain list [--type T] [--tag T]          # 列表
```

**检索**

```bash
gbrain search <query>                     # 纯关键词
gbrain query <question>                   # 混合检索（主力命令）
```

**导入与同步**

```bash
gbrain import <dir>                       # 导入整个 markdown 目录（幂等）
gbrain sync                               # git → brain 增量同步
```

**图谱**

```bash
gbrain extract links --source db          # 一次性回填类型化链接
gbrain graph-query <slug> --type attended --depth 2
```

**Minions 后台任务**

```bash
gbrain jobs submit <name>                 # 提交任务
gbrain jobs supervisor --concurrency 4    # 带自动重启的 worker
gbrain jobs smoke                         # 一键健康检查
```

**技能开发（v0.19+）**

```bash
gbrain skillify scaffold <name>           # 生成 5 个技能存根 + 解析器
gbrain skillify check <path>              # 10 项审计
gbrain skillpack install --all            # 安装全部 25 个精选技能
gbrain check-resolvable --strict          # 解析器审计
```

**GStack 代码查询（配套组件）**

```bash
gbrain code-callers <symbol>              # 谁调用
gbrain code-callees <symbol>              # 调用了什么
gbrain code-def <symbol>                  # 定义在哪里
```

### MCP 集成

**本地 stdio**（Claude Code / Cursor / Windsurf）：

```json
{
  "mcpServers": {
    "gbrain": {
      "command": "gbrain",
      "args": ["serve"]
    }
  }
}
```

**远程 MCP**（Claude Desktop / Cowork 等需公网 URL 的客户端）：

```bash
# 1. 暴露本地服务
ngrok http 8787 --url your-brain.ngrok.app

# 2. 创建认证 Token
bun run src/commands/auth.ts create "claude-desktop"

# 3. 在客户端登记
claude mcp add gbrain -t http https://your-brain.ngrok.app/mcp \
  -H "Authorization: Bearer TOKEN"
```

### 数据源接入菜谱（Recipes）

GBrain 提供开箱即用的摄取菜谱：

| 菜谱 | 作用 |
|---|---|
| `ngrok-tunnel` | MCP + 语音固定 URL |
| `credential-gateway` | Gmail + Calendar 访问凭证 |
| `twilio-voice-brain` | 电话 → 大脑页面 |
| `email-to-brain` | Gmail → 实体页面 |
| `x-to-brain` | Twitter 时间线 + 提及 |
| `calendar-to-brain` | Google 日历 → 可搜索日页 |
| `meeting-sync` | Circleback 转录 → 会议页 |

### 关键入口文件（Agent 读这些就知道怎么用）

- `AGENTS.md` — 非 Claude Agent 的操作协议（安装、阅读顺序、信任边界）
- `CLAUDE.md` — Claude Code 专用指南
- `llms.txt` / `llms-full.txt` — 文档地图 / 地图+内联核心文档
- `skills/RESOLVER.md` — 技能分派器

## 在 match3-wiki 项目中的作用

### 适用场景

GBrain 与 match3-wiki 的契合点不在"写 wiki"，而在**"让 AI 基于 wiki 持续工作"**：

- **长期记忆层**：Obsidian 管 wiki 文件；GBrain 把这些文件编译成 Agent 可用的检索库 + 知识图谱。
- **竞品人物关系图谱**：`attended`、`works_at`、`founded` 这些自动抽取的关系非常适合做"谁在 King/Supercell 工作过、后来去了哪家"这类竞品追踪。
- **定时研究任务**：21 个 Minions 可以跑"每天抓一次 Sensor Tower 新榜 / 每周汇总 Facebook Ad Library 变动 / 每月更新合成三消头部产品变现模型"。
- **会议与访谈沉淀**：meeting-sync 把播客、开发者访谈、GDC 演讲字幕录进大脑，自动链接到对应产品/人物页面。
- **跨源富化**：一条推特提到某游戏 → 实体分层自动升级 → 抓取更多上下文 → 最终凝结成 wiki 页面。

### 与其他工具的协作

```
 Obsidian Vault (wiki/)          ← 人类编辑
        │ git push
        ▼
   Brain Repo (git)              ← 真相之源
        │ gbrain sync
        ▼
   GBrain (Postgres + pgvector)  ← 检索 + 图谱 + Minions
        │ MCP
        ▼
  Agent (Claude Code / OpenClaw) ← 调用 29 个 Skills
        │ 写回 markdown
        ▼
   Brain Repo → Obsidian         ← 人类下次看到更新
```

- 与 **Obsidian**：Obsidian 是编辑与浏览 UI，GBrain 是 Agent 侧的检索大脑。同一仓库，两种视角。
- 与 **PageIndex**：PageIndex 擅长"单个长 PDF 精读"；GBrain 擅长"海量短笔记的混合检索与图谱"。适合联合使用——PDF 用 PageIndex 检索，笔记用 GBrain 检索。
- 与 **Graphify / nvk-llm-wiki**：它们负责把原始素材编排成 wiki，GBrain 负责让 Agent 持续使用和扩展这份 wiki。

## 局限性

- **强依赖 Bun + TypeScript + Postgres 栈**：不能混进 Python 项目；对非 TS 技术栈团队门槛高。
- **Agent-first 设计**：命令语义偏向"给 Agent 看"，初次上手人类用户需要一些适应。
- **自动抽取基于规则**：关系抽取用正则 + 模式匹配，对非英语语境（中文人名/公司名）准确率会下降，需要自行扩展规则。
- **ChatGPT 暂不支持**：OAuth 2.1 未实现，只能接 Claude 系和 Cursor 系。
- **规模化需 Supabase**：PGLite 适合个人（万级页面），企业/团队场景需上 Supabase Pro（$25/月起）。
- **维护心智负担**：21 个定时任务 + 29 个技能 + 图谱 + Minions，配置与调试面不小，作者本人花了 12 天才稳定下来。
- **项目年轻**：2026 年初才开源，API/schema 在快速演进，生产使用需锁版本。
