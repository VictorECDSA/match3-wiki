# Templater - Template Automation for Obsidian

> 官方地址：https://github.com/SilentVoid13/Templater

## 工具定位

Templater 是 Obsidian 的强大模板插件，支持：
- **动态变量**：日期、时间、文件元数据
- **JavaScript 执行**：自定义逻辑、API 调用、文件操作
- **用户输入**：创建笔记时交互式输入参数
- **自动化触发**：新建文件时自动应用模板

在 match3-wiki 项目中的用途：
- **标准化笔记结构**：确保所有 wiki 条目使用统一格式
- **自动填充元数据**：创建时自动生成日期、文件名等
- **快速创建笔记**：一键创建带结构的 wiki 条目或剪藏笔记
- **批量处理**：用模板批量生成系列笔记

## 安装配置

### 1. 安装插件

1. Settings → Community plugins → Browse
2. 搜索 "Templater"
3. Install → Enable

### 2. 基础配置

**Settings → Templater**：

```yaml
【Template folder location】
templates/         # 模板存放目录

【Trigger Templater on new file creation】
✓ 启用             # 新建文件时自动应用模板

【Enable folder templates】
✓ 启用             # 为特定文件夹设置默认模板

【Enable system commands】
✓ 启用             # 启用系统命令（日期、文件等）

【Enable user functions】
✓ 启用             # 启用自定义 JavaScript 函数
```

## 基础语法

### 1. 内置变量

```markdown
文件名：<% tp.file.title %>
创建日期：<% tp.date.now("YYYY-MM-DD") %>
当前时间：<% tp.date.now("HH:mm") %>
```

### 2. 用户输入

```markdown
游戏名称：<% tp.system.prompt("Game Name") %>
```

### 3. 文件操作

```markdown
<%* await tp.file.move("/wiki/games/" + tp.file.title) %>
```

## match3-wiki 模板库

### 模板 1：原始素材笔记

`templates/raw-material.md`：
```markdown
---
source: <% tp.system.prompt("Source URL") %>
date_clipped: <% tp.date.now("YYYY-MM-DD") %>
type: <% tp.system.suggester(["market-data", "ua-creative", "mechanics", "article"], ["market-data", "ua-creative", "mechanics", "article"]) %>
domain: <% tp.system.prompt("Domain (e.g., appmagic.rocks)") %>
game: <% tp.system.prompt("Game Name (lowercase-with-dashes)", "unknown") %>
status: raw
tags: []
---

# <% tp.file.title %>

## Source
[Link](<% tp.system.prompt("Source URL") %>)

## Content

<% tp.file.cursor(1) %>

## Notes

- 

## Todo

- [ ] Clean up formatting
- [ ] Extract key points
- [ ] Create wiki entry
```

**使用方式**：
1. 创建新笔记
2. Cmd/Ctrl + P → "Templater: Insert Template"
3. 选择 "raw-material"
4. 依次输入：URL、类型、域名、游戏名
5. 光标自动定位到 Content 区域

### 模板 2：Wiki 游戏条目

`templates/wiki-game.md`：
```markdown
---
title: <% tp.file.title %>
date_created: <% tp.date.now("YYYY-MM-DD") %>
date_updated: <% tp.date.now("YYYY-MM-DD") %>
status: draft
category: games
developer: <% tp.system.prompt("Developer") %>
publisher: <% tp.system.prompt("Publisher") %>
release_date: <% tp.system.prompt("Release Date (YYYY-MM-DD)") %>
tags: [match3]
raw_sources: []
---

# <% tp.file.title %>

> Developer: [[<% tp.system.prompt("Developer") %>]]
> Publisher: [[<% tp.system.prompt("Publisher") %>]]
> Release: <% tp.system.prompt("Release Date (YYYY-MM-DD)") %>

## Overview

<% tp.file.cursor(1) %>

## Core Mechanics

### Match System
- 

### Progression
- 

### Monetization
- 

## Market Performance

### Revenue
- 

### Downloads
- 

### Key Markets
- 

## Analysis

### Strengths
- 

### Innovations
- 

### Target Audience
- 

## Raw Materials

<%* 
// 自动查找相关原始素材
const gameName = tp.file.title.toLowerCase().replace(/\s+/g, '-')
const rawFiles = app.vault.getMarkdownFiles()
  .filter(f => f.path.startsWith('raw/') && f.basename.toLowerCase().includes(gameName))
  .slice(0, 10)

if (rawFiles.length > 0) {
  tR += "### Related Raw Materials\n\n"
  for (let file of rawFiles) {
    tR += `- [[${file.basename}]]\n`
  }
} else {
  tR += "*No raw materials found. Add links manually.*\n"
}
%>

## References

- 

---
*Created: <% tp.date.now("YYYY-MM-DD HH:mm") %>*
```

### 模板 3：市场数据报告

`templates/market-report.md`：
```markdown
---
title: <% tp.file.title %>
date: <% tp.date.now("YYYY-MM-DD") %>
type: market-report
games: []
metrics: [revenue, downloads, dau]
tags: [market, report]
---

# <% tp.file.title %>

**Report Date**: <% tp.date.now("YYYY-MM-DD") %>
**Period**: <% tp.system.prompt("Period (e.g., Q1 2026, March 2026)") %>

## Executive Summary

<% tp.file.cursor(1) %>

## Top Performers

| Rank | Game | Revenue | Downloads | Notes |
|------|------|---------|-----------|-------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

## Key Insights

### Revenue Trends
- 

### Market Share
- 

### Emerging Patterns
- 

## Data Sources

<%* 
// 列出本月的市场数据原始素材
const thisMonth = tp.date.now("YYYY-MM")
const marketFiles = app.vault.getMarkdownFiles()
  .filter(f => f.path.startsWith('raw/market/') && f.basename.includes(thisMonth))
  .slice(0, 20)

for (let file of marketFiles) {
  tR += `- [[${file.basename}]]\n`
}
%>

---
*Generated: <% tp.date.now("YYYY-MM-DD HH:mm") %>*
```

### 模板 4：每日工作笔记

`templates/daily-note.md`：
```markdown
---
date: <% tp.date.now("YYYY-MM-DD") %>
type: daily-note
tags: [daily]
---

# <% tp.date.now("YYYY年MM月DD日 dddd") %>

## 📥 Today's Raw Materials

```dataview
TABLE 
  type as "Type",
  domain as "Source"
FROM "raw"
WHERE date_clipped = date(<% tp.date.now("YYYY-MM-DD") %>)
```

## ✍️ Wiki Work

### Created
- 

### Updated
- 

### Todo
- [ ] 

## 📊 Quick Stats

- Raw materials collected: `<%= dv.pages('"raw"').where(p => p.date_clipped == "<% tp.date.now("YYYY-MM-DD") %>").length %>`
- Wiki entries updated: 

## 💡 Insights

- 

## 📝 Notes

<% tp.file.cursor(1) %>

---
[[<% tp.date.now("YYYY-MM-DD", -1) %>|← Previous]] | [[<% tp.date.now("YYYY-MM-DD", 1) %>|Next →]]
```

## 高级技巧

### 1. 文件夹自动模板

**配置文件夹默认模板**：
1. Settings → Templater → Folder Templates
2. 添加规则：
   - `raw/` → `templates/raw-material.md`
   - `wiki/games/` → `templates/wiki-game.md`
   - `wiki/reports/` → `templates/market-report.md`

现在在这些文件夹创建新文件时，自动应用对应模板！

### 2. 自定义用户函数

**创建 `templates/scripts/user-functions.js`**：
```javascript
// 提取游戏名（从文件名或用户输入）
function getGameName(tp) {
  const fileName = tp.file.title
  // 尝试从文件名提取（格式：YYYY-MM-DD-game-name-xxx）
  const match = fileName.match(/^\d{4}-\d{2}-\d{2}-(.+?)-/)
  if (match) {
    return match[1]
  }
  // 否则提示用户输入
  return tp.system.prompt("Game Name (lowercase-with-dashes)")
}

// 查找相关 raw materials
async function findRawMaterials(tp, gameName) {
  const files = app.vault.getMarkdownFiles()
    .filter(f => f.path.startsWith('raw/') && 
                 f.basename.toLowerCase().includes(gameName.toLowerCase()))
  return files.map(f => `- [[${f.basename}]]`).join('\n')
}

// 生成 wiki 条目 ID
function generateWikiId(tp) {
  const title = tp.file.title.toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
  return title
}

module.exports = {
  getGameName,
  findRawMaterials,
  generateWikiId
}
```

**在模板中使用**：
```markdown
游戏名：<% tp.user.getGameName(tp) %>

原始素材：
<%* tR += await tp.user.findRawMaterials(tp, "candy-crush") %>
```

### 3. 批量创建笔记

**创建系列游戏条目**：

`templates/batch-create-games.md`：
```markdown
<%*
const games = [
  {name: "Candy Crush Saga", dev: "King", year: "2012"},
  {name: "Royal Match", dev: "Dream Games", year: "2020"},
  {name: "Homescapes", dev: "Playrix", year: "2017"},
  // ... 更多游戏
]

for (let game of games) {
  const fileName = game.name.toLowerCase().replace(/\s+/g, '-')
  const filePath = `wiki/games/${fileName}.md`
  
  // 检查文件是否已存在
  if (await tp.file.exists(filePath)) {
    console.log(`Skipped: ${fileName} (already exists)`)
    continue
  }
  
  // 创建文件内容
  const content = `---
title: ${game.name}
developer: ${game.dev}
release_date: ${game.year}
status: draft
category: games
tags: [match3]
---

# ${game.name}

> Developer: [[${game.dev}]]
> Release: ${game.year}

## Overview

[To be filled]

## Core Mechanics

[To be filled]
`
  
  // 创建文件
  await tp.file.create_new(content, fileName, false, tp.file.folder(true))
  console.log(`Created: ${fileName}`)
}

tR += "Batch creation complete!"
%>
```

运行此模板，一次性创建多个游戏条目！

### 4. 动态目录生成

**自动生成 README 索引**：

`templates/generate-readme.md`：
```markdown
# Wiki Games Index

> Auto-generated: <% tp.date.now("YYYY-MM-DD HH:mm") %>

<%*
const games = app.vault.getMarkdownFiles()
  .filter(f => f.path.startsWith('wiki/games/'))
  .sort((a, b) => a.basename.localeCompare(b.basename))

// 按首字母分组
const groups = {}
for (let file of games) {
  const first = file.basename[0].toUpperCase()
  if (!groups[first]) groups[first] = []
  groups[first].push(file)
}

// 生成索引
for (let letter of Object.keys(groups).sort()) {
  tR += `\n## ${letter}\n\n`
  for (let file of groups[letter]) {
    tR += `- [[${file.basename}]]\n`
  }
}
%>

---
Total games: <% tp.config.target_file.parent.children.filter(f => f.extension === 'md').length %>
```

### 5. Web Clipper 后处理模板

**清洗剪藏内容**：

`templates/clean-clipper.md`：
```markdown
<%*
// 读取当前笔记内容
const content = await tp.file.content

// 清理常见杂项
let cleaned = content
  .replace(/^---[\s\S]*?---\n/, '')  // 移除 frontmatter
  .replace(/\n{3,}/g, '\n\n')         // 压缩多余空行
  .replace(/<!--[\s\S]*?-->/g, '')    // 移除 HTML 注释
  .replace(/<script[\s\S]*?<\/script>/gi, '')  // 移除脚本
  .trim()

// 添加新的 frontmatter
const newFrontmatter = `---
source: <% tp.system.clipboard() %>
date_clipped: <% tp.date.now("YYYY-MM-DD") %>
type: <% tp.system.suggester(["market-data", "ua-creative", "mechanics"], ["market-data", "ua-creative", "mechanics"]) %>
status: cleaned
---

`

tR = newFrontmatter + cleaned
%>
```

使用：
1. Web Clipper 剪藏内容
2. 在 Obsidian 打开剪藏笔记
3. Cmd/Ctrl + P → "Templater: Replace templates in the active file"
4. 选择 "clean-clipper"
5. 内容自动清洗并添加标准 frontmatter

## 常见问题

### Q: 模板变量不生效？
A: 检查 Templater 语法：
- 正确：`<% tp.date.now() %>`
- 错误：`{{date}}` （这是 Web Clipper 语法）

### Q: JavaScript 报错？
A: 
1. 打开 Developer Console（Cmd/Ctrl + Shift + I）
2. 查看错误信息
3. 检查语法：`<%* ... %>` 用于执行代码，`<% ... %>` 用于输出

### Q: 如何调试复杂模板？
A: 使用 `console.log()` 输出调试信息：
```markdown
<%* 
console.log("Debug:", tp.file.title)
console.log("Files found:", files.length)
%>
```

### Q: 模板执行慢？
A: 
1. 避免扫描整个 vault（用 `filter` 限制范围）
2. 缓存查询结果，不要重复扫描
3. 大批量操作用独立脚本而非模板

## 完整工作流示例

### 场景：从剪藏到 Wiki 条目

**步骤 1：Web Clipper 剪藏原始内容**
- 自动使用 `templates/raw-material.md` 模板
- 自动填充 source、date_clipped 等字段

**步骤 2：清洗内容**
- 打开剪藏笔记
- 应用 `templates/clean-clipper.md` 模板
- 内容自动清理、重新格式化

**步骤 3：创建 Wiki 条目**
- 在 `wiki/games/` 创建新笔记
- 自动应用 `templates/wiki-game.md` 模板
- 模板自动查找相关 raw materials 并链接

**步骤 4：生成月度报告**
- 创建笔记使用 `templates/market-report.md`
- 模板自动聚合本月的市场数据

整个流程标准化、自动化，效率提升 10 倍！
