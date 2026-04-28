# safishamsi/graphify

> 仓库：https://github.com/safishamsi/graphify

## 工具定位

Graphify 是一个 AI 驱动的知识图谱生成工具。它通过三阶段流水线对代码库或文档语料进行处理，提取实体和关系，用社区检测算法聚类，最终输出可交互的可视化 HTML 文件和可查询的 JSON 图谱。核心价值：把大型语料压缩（最高 71.5 倍）成可导航的知识结构，同时保留语义关系。

## 工作原理

### 三阶段流水线

**第一阶段——AST 提取（本地运行，无需 LLM）**
- 用 tree-sitter 解析源代码文件
- 提取：函数、类、引用、调用图、数据结构
- 对非代码文件（Markdown、纯文本）：提取标题、命名实体、交叉引用
- 完全本地运行——没有 API 调用，没有成本，速度快

**第二阶段——转录（本地运行，无需 LLM）**
- 用 faster-whisper（本地 Whisper 模型）转录音频/视频文件
- 将转录结果转为结构化文本供第三阶段使用
- 完全离线——不依赖云端转录服务

**第三阶段——语义分析（Claude 子智能体，需要 LLM）**
- 并行启动 Claude 子智能体分析提取出的实体和文本
- 每个子智能体处理语料的一个子集
- 识别：语义关系、概念聚类、AST 未能捕捉到的隐式链接
- 输出：带置信度分数的增强实体列表 + 关系边

### 社区检测

第三阶段结束后，Graphify 使用 **Leiden 算法**（通过 NetworkX）对实体聚类。Leiden 是 Louvain 算法的改进版——保证社区内部良好连通，对大型图谱处理高效。结果：相关主题自动归组，无需手动定义分类体系。

### 输出格式

| 输出 | 格式 | 用途 |
|---|---|---|
| 交互式可视化 | HTML（vis.js） | 用浏览器直接打开，无需安装 |
| 可查询图谱 | JSON | 程序化访问、过滤 |
| 摘要报告 | Markdown | 社区概览，人可读 |

HTML 可视化支持：
- 点击节点展开关系
- 社区颜色编码
- 按实体类型搜索/过滤
- 导出选中子图

### 压缩率

Graphify 实现最高 **71.5 倍 token 压缩**（相对于直接把原始文件喂给 LLM）。原理：将图谱 JSON（实体 + 边）发给 LLM，而不是完整文件内容——以极少的 token 编码了相同的结构性知识。

### MCP Server 模式

```bash
graphify serve
```

启动一个 Model Context Protocol 服务端。任何兼容 MCP 的客户端（Claude Desktop、Claude Code）都可以查询图谱：
- `graph.search("mechanic")` — 找到所有匹配某个词的实体
- `graph.neighbors("candy-crush")` — 获取相关实体
- `graph.community("ua-creatives")` — 获取某个聚类中的所有节点

### Git Post-Commit Hook

Graphify 可以安装 git post-commit hook，每次提交后自动重建图谱。确保知识图谱随 wiki 语料更新而更新，无需手动重跑。

## 使用方法

### 安装

```bash
pip install graphify
# 或者
git clone https://github.com/safishamsi/graphify
pip install -r requirements.txt
```

### 基本用法

```bash
# 分析一个目录
graphify analyze ./wiki/

# 指定输出目录
graphify analyze ./wiki/ --output ./graph/

# 启动 MCP 服务端
graphify serve --graph ./graph/graph.json
```

### 配置文件

创建 `graphify.config.json`：
```json
{
  "include": ["*.md", "*.txt"],
  "exclude": ["raw/", "history/"],
  "llm_model": "claude-3-5-sonnet",
  "agents": 8,
  "community_resolution": 1.0
}
```

关键配置项：
- `agents`：第三阶段并行 Claude 子智能体数量（越多越快，成本越高）
- `community_resolution`：Leiden 分辨率参数（越高 = 社区越多越小）
- `include`/`exclude`：文件选择的 glob 模式

### 与 Claude Code 集成（MCP）

在 `.claude/settings.json` 中添加：
```json
{
  "mcpServers": {
    "graphify": {
      "command": "graphify",
      "args": ["serve", "--graph", "./graph/graph.json"]
    }
  }
}
```

Claude Code 会话中即可直接调用 `mcp__graphify__search` 和 `mcp__graphify__neighbors`。

### 安装 Git Hook

```bash
graphify install-hook --watch ./wiki/
```

每次 `wiki/` 目录有提交时自动重跑 `graphify analyze`。

## 在 match3-wiki 项目中的作用

### 知识图谱层

在 match3-wiki 工具链中，Graphify 是 wiki 页面和浏览/发现体验之间的**结构层**：

```
wiki/（nvk/llm-wiki 产出的 Markdown 页面）
  ↓  graphify analyze
graph/graph.json + graph/index.html
  ↓
Obsidian（通过 wikilink + Graph View 浏览）
Claude Code（通过 MCP Server 查询）
```

### 具体使用场景

**跨 wiki 关系发现**：nvk/llm-wiki 产出 50+ 页面后，很难直观看到 `wiki/mechanics/booster-system.md` 和 `wiki/market/top-grossing-2024.md` 之间的关联。Graphify 让这些连接变得显式——"Candy Crush" 这个实体同时出现在两页中，自动产生图谱边。

**主题聚类验证**：Leiden 算法会自然地将 match3-wiki 聚类成与 PRD 分类体系吻合的社区（机制聚类、UA 聚类、市场数据聚类、制作聚类）。瘦小的社区意味着覆盖不足。

**Token 高效的全局分析**：把整个知识库（100+ 页）的 Markdown 直接喂给 Claude 会超出上下文窗口。改为喂 `graph/graph.json`：71.5 倍压缩后，500 页 wiki 能装进单个 Claude 上下文窗口。

**MCP Server 支持交互式研究**：`graphify serve` 运行时，Claude Code 会话可以在研究过程中随时查询知识图谱，无需翻页。

**Phase 2 激活（第 9–16 周）**：PRD 将 Phase 2 定为扩展 + 图谱化阶段。Phase 1 建立初始 50 页语料后，Graphify 跑第一次全量分析，揭示结构性盲点并生成交互式知识地图。

### 持续更新

在 wiki 仓库上安装 post-commit hook，每次 nvk/llm-wiki 写入新页面时图谱自动重建，无需手动执行 `graphify analyze`。

## 局限性

- 第三阶段（语义分析）会产生 Claude API 费用，与语料大小 × 智能体数量成正比
- 大型语料（1000+ 文件）即使并行也会较慢
- 交互式 HTML 可视化只读——无法从界面编辑图谱
- MCP Server 需要 graphify 进程持续运行，不适合 Serverless 环境
- 第三阶段语义分析对非英文语料的支持有限
