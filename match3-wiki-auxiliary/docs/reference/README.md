# match3-wiki 参考工具文档

本目录包含 match3-wiki 项目使用的所有工具的详细文档。

## 知识管理工具

### [Obsidian](./obsidian/main.md)
本地优先的个人知识管理应用，用于素材收集和 wiki 浏览。

**子文档：**
- [安装与配置](./obsidian/setup/installation.md)
- [Web Clipper 配置](./obsidian/web-clipper/configuration.md)
- [推荐插件](./obsidian/plugins/recommended.md)

### [nvk/llm-wiki](./nvk-llm-wiki/main.md)
核心编译引擎，将原始素材编译为结构化 wiki 页面。

### [Karpathy LLM Wiki Gist](./karpathy-llm-wiki-gist/main.md)
Andrej Karpathy 的 LLM Wiki 设计模式，整个架构的思想基础。

## 市场情报工具

### [AppMagic](./appmagic/main.md)
主力市场情报平台，提供下载量、收入、留存等数据（$299–499/月）。

### [Sensor Tower](./sensor-tower/main.md)
企业级市场情报平台，数据精度最高（$2,000+/月）。

## 买量素材工具

### [Facebook Ad Library](./facebook-ad-library/main.md)
Meta 免费广告库，三消游戏主要买量渠道之一。

### [TikTok Creative Center](./tiktok-creative-center/main.md)
TikTok 免费创意情报平台，三消游戏另一主要买量渠道。

## 辅助工具

### [Graphify](./graphify/main.md)
AI 驱动的知识图谱生成工具，用于可视化和查询 wiki 结构。

### [Repomix](./repomix/main.md)
将整个代码库/wiki 打包成单文件供 LLM 分析。

### [Docusaurus](./docusaurus/main.md)
Phase 3 发布层，将 wiki 转换为公开网站。

## 工具对比

### 市场情报工具选择

| 维度 | AppMagic | Sensor Tower |
|---|---|---|
| 定价 | $299–499/月 | $2,000+/月 |
| 品类收入基准 | ✓ 够用 | ✓ 精度更高 |
| 留存曲线 | ✓ 有 | ✓ 有（企业版） |
| IAP vs. 广告收入 | ✓ 独有特性 | 有限 |
| 广告素材情报 | 有限 | ✓ 强 |
| **建议用法** | **主力** | **验证** |

### 买量素材工具选择

| 维度 | Facebook Ad Library | TikTok Creative Center |
|---|---|---|
| 成本 | 免费 | 免费 |
| 覆盖渠道 | FB + IG | TikTok |
| 按广告主筛选 | ✓ 支持 | 不支持 |
| 效果数据 | 无 | CTR/CVR 档位 |
| 三消游戏预算占比 | 40–60% | 20–35% |
| **建议用法** | **竞品追踪** | **品类趋势** |

## 工作流集成

```
原始素材采集：
浏览器 → Web Clipper → raw/ → /wiki:ingest

Wiki 编译：
raw/ → nvk/llm-wiki → wiki/

知识图谱：
wiki/ → Graphify → graph.json

浏览与分析：
wiki/ + graph.json → Obsidian → Graph View

公开发布（Phase 3）：
wiki/ → Docusaurus → https://match3.wiki
```

## 更新日志

- 2026-04-22：重构文档结构，将单文件拆分为目录层次
- 之前：所有工具文档均为单个 .md 文件
