# Dataview - Query and Display Your Notes

> 官方地址：https://github.com/blacksmithgu/obsidian-dataview

## 工具定位

Dataview 将 Obsidian vault 转换为数据库，允许使用类 SQL 查询语言提取、过滤、聚合笔记信息。核心能力：
- **自动索引**：扫描所有笔记的 frontmatter、标签、链接
- **动态查询**：在笔记中嵌入查询，结果自动更新
- **数据聚合**：统计、分组、排序笔记
- **表格/列表视图**：将查询结果展示为表格或列表

在 match3-wiki 项目中的用途：
- **原始素材盘点**：查询 `raw/` 目录有多少剪藏、按来源分类
- **Wiki 覆盖度检查**：统计各游戏的 wiki 条目数量
- **待处理任务**：列出所有 `status: draft` 的笔记
- **数据趋势分析**：按时间聚合市场数据

## 安装

1. Settings → Community plugins → Browse
2. 搜索 "Dataview"
3. Install → Enable
4. Settings → Dataview → 启用 "Enable JavaScript Queries"（高级功能）

## 基础语法

### 1. LIST 查询（列表）

**语法**：
```dataview
LIST
FROM "folder-path"
WHERE condition
SORT field
```

**示例 1：列出所有原始素材**
```dataview
LIST
FROM "raw"
WHERE file.ctime >= date(2026-04-01)
SORT file.ctime DESC
LIMIT 20
```

**示例 2：按标签筛选**
```dataview
LIST
WHERE contains(tags, "market-data")
SORT file.name
```

### 2. TABLE 查询（表格）

**语法**：
```dataview
TABLE field1, field2, field3
FROM "folder"
WHERE condition
```

**示例：市场数据汇总表**
```dataview
TABLE 
  source as "来源",
  date_clipped as "采集日期",
  domain as "网站"
FROM "raw/market"
WHERE date_clipped >= date(2026-04-01)
SORT date_clipped DESC
```

### 3. TASK 查询（任务）

列出笔记中的所有待办事项：
```dataview
TASK
FROM "raw"
WHERE !completed
```

### 4. CALENDAR 查询（日历）

按日期显示笔记：
```dataview
CALENDAR file.ctime
FROM "raw"
```

## match3-wiki 实用查询

### 查询 1：原始素材统计

在 `raw/README.md` 中创建汇总：
```markdown
# Raw Materials Dashboard

## 本月采集统计

```dataview
TABLE 
  length(rows) as "数量"
FROM "raw"
WHERE date_clipped >= date(2026-04-01)
GROUP BY type
```

## 最近采集（最新 10 条）

```dataview
TABLE 
  title as "标题",
  domain as "来源",
  date_clipped as "日期"
FROM "raw"
SORT date_clipped DESC
LIMIT 10
```
```

### 查询 2：Wiki 覆盖度检查

在 `wiki/README.md` 中：
```markdown
# Wiki Coverage Dashboard

## 各分类条目数

```dataview
TABLE 
  length(rows) as "条目数"
FROM "wiki"
GROUP BY file.folder
```

## 待完善条目（状态为 draft）

```dataview
LIST
FROM "wiki"
WHERE status = "draft"
SORT file.mtime DESC
```

## 孤立页面（无链接）

```dataview
LIST
FROM "wiki"
WHERE length(file.inlinks) = 0 AND length(file.outlinks) = 0
```
```

### 查询 3：按游戏分类的原始素材

```markdown
# Candy Crush - Raw Materials

```dataview
TABLE 
  file.name as "文件",
  type as "类型",
  date_clipped as "采集日期"
FROM "raw"
WHERE contains(file.name, "candy-crush") OR contains(file.name, "Candy Crush")
SORT date_clipped DESC
```
```

### 查询 4：市场数据趋势

```markdown
# Market Data Trends

## 按月统计采集数量

```dataview
TABLE 
  length(rows) as "数量"
FROM "raw/market"
GROUP BY dateformat(date_clipped, "yyyy-MM")
SORT rows[0].date_clipped DESC
```

## Top 数据来源

```dataview
TABLE 
  length(rows) as "采集次数"
FROM "raw/market"
GROUP BY domain
SORT length(rows) DESC
LIMIT 10
```
```

### 查询 5：工作流监控

```markdown
# Workflow Status

## 待清洗的剪藏（超过 7 天）

```dataview
LIST
FROM "raw"
WHERE status = "raw" AND date_clipped < date(today) - dur(7 days)
SORT date_clipped
```

## 本周新增 Wiki 条目

```dataview
LIST
FROM "wiki"
WHERE file.ctime >= date(today) - dur(7 days)
SORT file.ctime DESC
```
```

## 高级用法：JavaScript 查询

启用后可以用 JavaScript 操作数据。

**示例：复杂数据聚合**
````markdown
```dataviewjs
// 统计每个游戏的原始素材数量
const pages = dv.pages('"raw"')
const games = {}

for (let page of pages) {
  // 从文件名提取游戏名（假设格式：2026-04-22-game-name-xxx）
  const match = page.file.name.match(/-([a-z-]+)-/)
  if (match) {
    const game = match[1]
    games[game] = (games[game] || 0) + 1
  }
}

// 转换为表格
const rows = Object.entries(games)
  .sort((a, b) => b[1] - a[1])
  .map(([game, count]) => [game, count])

dv.table(["Game", "Raw Materials"], rows)
```
````

## Frontmatter 字段设计

为了让 Dataview 查询更有效，原始素材和 wiki 条目应该有结构化的 frontmatter：

**原始素材模板**：
```yaml
---
source: https://example.com
date_clipped: 2026-04-22
type: market-data  # 或 ua-creative, mechanics, article
domain: appmagic.rocks
game: candy-crush  # 关联的游戏
status: raw        # raw → cleaned → processed
tags: [market, revenue, 2026]
---
```

**Wiki 条目模板**：
```yaml
---
title: Candy Crush Saga
date_created: 2026-04-22
date_updated: 2026-04-22
status: published  # draft → review → published
category: games
tags: [match3, king, puzzle]
raw_sources:
  - [[2026-04-20-appmagic-candy-crush]]
  - [[2026-04-21-sensor-tower-candy-crush]]
---
```

## 常见问题

### Q: 查询结果不更新？
A: Dataview 每 2 秒自动刷新。如果没更新，尝试关闭再打开笔记，或重启 Obsidian。

### Q: 如何调试查询？
A: 打开 Settings → Dataview → "Enable Debug Logging"，查看控制台（Cmd/Ctrl + Shift + I）

### Q: 性能问题（大量笔记时查询慢）？
A: 
1. 缩小查询范围（用 `FROM "specific-folder"`）
2. 避免复杂的 JavaScript 查询
3. 使用 `LIMIT` 限制结果数

### Q: 日期格式问题？
A: Dataview 支持 ISO 8601 格式（`YYYY-MM-DD`）。使用 `date()` 函数转换。

## 完整示例：Dashboard 笔记

创建 `_dashboard.md` 作为项目总览：

````markdown
---
title: Match3 Wiki Dashboard
date: 2026-04-22
---

# Match3 Wiki Dashboard

> 最后更新：2026-04-22 14:53

## 📊 统计概览

| 指标 | 数量 |
|------|------|
| Raw Materials | `= length(dv.pages('"raw"'))` |
| Wiki Entries | `= length(dv.pages('"wiki"'))` |
| Draft Entries | `= length(dv.pages('"wiki"').where(p => p.status == "draft"))` |

## 📥 最近采集（最新 10 条）

```dataview
TABLE 
  file.link as "文件",
  type as "类型",
  domain as "来源",
  date_clipped as "日期"
FROM "raw"
SORT date_clipped DESC
LIMIT 10
```

## ✍️ 待完善 Wiki 条目

```dataview
TABLE 
  file.link as "条目",
  status as "状态",
  file.mtime as "最后修改"
FROM "wiki"
WHERE status = "draft"
SORT file.mtime DESC
```

## 🎮 游戏覆盖度

```dataview
TABLE 
  length(rows) as "Wiki 条目数",
  length(rows.raw_sources) as "原始素材数"
FROM "wiki/games"
GROUP BY file.name
SORT length(rows) DESC
```

## 📈 采集趋势（按月）

```dataview
TABLE 
  length(rows) as "数量"
FROM "raw"
GROUP BY dateformat(date_clipped, "yyyy-MM") as Month
SORT Month DESC
LIMIT 6
```

## 🔍 孤立条目（需要链接）

```dataview
LIST
FROM "wiki"
WHERE length(file.inlinks) = 0 AND length(file.outlinks) < 2
SORT file.ctime DESC
LIMIT 10
```

## 📝 最近更新的 Wiki 条目

```dataview
TABLE 
  file.link as "条目",
  file.mtime as "更新时间"
FROM "wiki"
SORT file.mtime DESC
LIMIT 10
```
````

这个 Dashboard 可以实时监控项目进度！
