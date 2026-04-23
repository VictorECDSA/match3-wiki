# Other Useful Plugins

除了 Claudian、Dataview、Templater 三大核心插件，以下插件也能显著提升 match3-wiki 项目的效率。

## 1. PDF++

> https://github.com/RyotaUshio/obsidian-pdf-plus

### 功能
- **PDF 标注**：直接在 Obsidian 中打开、阅读、标注 PDF
- **双向链接**：PDF 标注 ↔ Markdown 笔记互链
- **提取标注**：一键提取所有高亮和批注到笔记
- **搜索跳转**：在 PDF 中搜索并直接跳转到位置

### 在项目中的用途
- 处理剪藏的 PDF 报告（如 App Annie 年度报告）
- 标注市场研究 PDF，提取数据到 wiki
- 保留原始 PDF 的引用和页码

### 使用示例

**场景：处理 Sensor Tower 的 PDF 报告**

1. 将 PDF 放入 `raw/market/pdfs/`
2. 在 Obsidian 中打开 PDF
3. 高亮关键数据（收入、下载量）
4. 右键 → "Copy link to selection"
5. 在 wiki 条目中粘贴链接：
   ```markdown
   Revenue data: [[sensor-tower-q1-2026.pdf#page=12|See page 12]]
   ```

## 2. Excalidraw

> https://github.com/zsviczian/obsidian-excalidraw-plugin

### 功能
- **手绘风格图表**：流程图、架构图、思维导图
- **嵌入笔记**：在画布上放置笔记链接，双击打开
- **无限画布**：与 Canvas 类似但功能更强
- **导出 PNG/SVG**：生成高质量图片

### 在项目中的用途
- 绘制游戏机制流程图
- 竞品格局关系图
- 用户旅程图（onboarding → retention → monetization）
- Wiki 结构规划

### 使用示例

**绘制 Match-3 核心循环**：
1. 创建新 Excalidraw 文件：`match3-core-loop.excalidraw.md`
2. 绘制流程图：
   ```
   [Match tiles] → [Clear] → [Tiles fall] → [New tiles spawn] → [Check for matches]
        ↑                                                              ↓
        └──────────────────── [Continue] ←──────────────────────────┘
   ```
3. 在 wiki 中嵌入：
   ```markdown
   ![[match3-core-loop.excalidraw]]
   ```

## 3. QuickAdd

> https://github.com/chhoumann/quickadd

### 功能
- **快速捕获**：一键创建预定义结构的笔记
- **宏命令**：组合多个操作（创建文件 + 打开 + 插入模板）
- **自定义菜单**：创建专属快捷操作面板

### 在项目中的用途
- 快速创建游戏条目（一键输入游戏名 → 创建文件 → 应用模板）
- 快速添加待办事项到特定笔记
- 快速剪藏链接或想法到收集箱

### 配置示例

**宏：快速创建游戏 Wiki 条目**

1. Settings → QuickAdd → Add Macro
2. 命名：`New Game Entry`
3. 添加步骤：
   - Capture: 输入游戏名
   - Template: 应用 `wiki-game.md` 模板
   - Move: 移动到 `wiki/games/`
   - Open: 打开新创建的文件
4. 设置快捷键：`Cmd/Ctrl + Shift + G`

现在按快捷键即可快速创建游戏条目！

## 4. Kanban

> https://github.com/mgmeyers/obsidian-kanban

### 功能
- **看板视图**：Trello 风格的任务管理
- **拖拽操作**：拖动卡片在列之间移动
- **笔记链接**：每张卡片可链接到实际笔记
- **标签过滤**：按标签、日期过滤卡片

### 在项目中的用途
- 管理 wiki 条目状态（Backlog → In Progress → Review → Published）
- 跟踪原始素材处理进度（Raw → Cleaned → Processed）
- 项目任务管理

### 使用示例

**创建 Wiki 工作流看板**：

1. 创建 `_wiki-workflow.kanban.md`
2. 设置列：
   - Backlog：待创建的 wiki 条目
   - Drafting：正在撰写
   - Review：待审核
   - Published：已发布
3. 添加卡片：
   ```markdown
   - [ ] [[candy-crush-saga]]
   - [ ] [[royal-match]]
   - [ ] [[homescapes]]
   ```
4. 拖拽卡片跟踪进度

## 5. Calendar

> https://github.com/liamcain/obsidian-calendar-plugin

### 功能
- **日历视图**：按日期显示笔记
- **日记导航**：快速创建和访问每日笔记
- **可视化时间线**：看到哪些日期有笔记

### 在项目中的用途
- 管理每日工作笔记
- 查看原始素材的采集时间分布
- 回顾历史工作记录

## 6. Bartender

> https://github.com/nothingislost/obsidian-bartender

### 功能
- **文件夹排序**：自定义文件夹显示顺序
- **隐藏文件**：隐藏不常用的文件/文件夹
- **分组规则**：按规则自动分组文件

### 在项目中的用途
- 固定常用文件夹顺序（`wiki/` 在顶部，`raw/` 在下方）
- 隐藏 `.obsidian/` 等系统文件夹
- 保持侧边栏整洁

## 7. Image Toolkit

> https://github.com/sissilab/obsidian-image-toolkit

### 功能
- **图片放大**：点击图片全屏查看
- **缩放平移**：鼠标滚轮缩放、拖动平移
- **图片预览**：悬停查看大图

### 在项目中的用途
- 查看剪藏的游戏截图
- 查看买量素材（广告创意图）
- 查看市场数据图表

## 8. Table Editor

> https://github.com/ganesshkumar/obsidian-table-editor

### 功能
- **表格编辑**：像 Excel 一样编辑 Markdown 表格
- **快速格式化**：自动对齐表格列
- **行列操作**：插入、删除行列

### 在项目中的用途
- 整理市场数据表格
- 编辑游戏对比表
- 维护竞品列表

### 使用示例

**快速创建游戏对比表**：

```markdown
| Game | Developer | Revenue (2025) | Key Feature |
|------|-----------|----------------|-------------|
| Candy Crush | King | $1.2B | Cascading matches |
| Royal Match | Dream Games | $800M | Area restoration |
```

启用 Table Editor 后，可以：
- Tab 键跳转到下一格
- 点击列头排序
- 右键插入行列

## 9. Advanced Tables

> https://github.com/tgrosinger/advanced-tables-obsidian

### 功能
- **自动格式化**：输入时自动对齐表格
- **Excel 公式**：在表格中使用简单公式
- **CSV 导入**：从 CSV 粘贴自动生成表格

### 在项目中的用途
- 从 AppMagic/Sensor Tower 导出 CSV 数据
- 自动计算汇总数据
- 快速生成格式化表格

## 10. Linter

> https://github.com/platers/obsidian-linter

### 功能
- **格式规范**：自动修正 Markdown 格式问题
- **YAML 整理**：规范 frontmatter 格式
- **规则自定义**：定义团队编码规范

### 在项目中的用途
- 统一所有 wiki 条目的格式
- 自动修正 Web Clipper 剪藏的格式问题
- 保持项目代码风格一致

### 配置示例

**Settings → Linter → Rules**：
```yaml
【YAML】
✓ Sort YAML keys alphabetically
✓ Remove trailing spaces in YAML
✓ Format YAML timestamps (YYYY-MM-DD)

【Headings】
✓ Heading blank lines (before: 1, after: 0)
✓ Header increment (no skipping levels)

【Lists】
✓ Proper list indent (2 spaces)
✓ Remove empty list items

【Links】
✓ Convert relative links to absolute
✓ Remove broken links
```

保存后，每次编辑笔记都会自动格式化！

## 推荐插件组合

### 最小化配置（新手）
1. **Claudian** - AI 辅助
2. **Web Clipper** - 内容采集
3. **Templater** - 模板自动化

### 标准配置（日常使用）
1. Claudian + Web Clipper + Templater
2. **Dataview** - 数据查询
3. **PDF++** - PDF 处理
4. **Calendar** - 日记管理

### 完整配置（进阶）
以上所有 + 
- Excalidraw（可视化）
- Kanban（任务管理）
- QuickAdd（快速捕获）
- Linter（格式规范）

## 安装建议

**不要一次性安装太多插件！**

推荐顺序：
1. 先装核心三件套（Claudian、Templater、Dataview）
2. 使用 2-4 周，熟悉基本工作流
3. 根据实际需求逐个添加其他插件
4. 每次添加新插件后配置好再添加下一个

过多插件会：
- 拖慢 Obsidian 启动速度
- 增加学习成本
- 造成功能冗余
- 可能产生冲突

## 插件冲突排查

如果 Obsidian 变慢或崩溃：

1. **Safe Mode 启动**：
   - Settings → Community plugins → Restricted mode（临时禁用所有插件）
   - 逐个启用插件，找出问题插件

2. **检查插件日志**：
   - Cmd/Ctrl + Shift + I → Console
   - 查看错误信息

3. **清理缓存**：
   - 关闭 Obsidian
   - 删除 `.obsidian/workspace` 和 `.obsidian/cache`
   - 重新启动

## 总结

| 插件 | 用途 | 优先级 | 学习曲线 |
|------|------|--------|---------|
| Claudian | AI 内容处理 | ⭐⭐⭐ | 低 |
| Dataview | 数据查询 | ⭐⭐⭐ | 中 |
| Templater | 模板自动化 | ⭐⭐⭐ | 中 |
| PDF++ | PDF 标注 | ⭐⭐ | 低 |
| Excalidraw | 可视化图表 | ⭐⭐ | 中 |
| QuickAdd | 快速捕获 | ⭐⭐ | 中 |
| Kanban | 任务管理 | ⭐⭐ | 低 |
| Calendar | 日记管理 | ⭐ | 低 |
| Bartender | 界面整理 | ⭐ | 低 |
| Linter | 格式规范 | ⭐ | 低 |

根据自己的需求和经验选择合适的插件组合！
