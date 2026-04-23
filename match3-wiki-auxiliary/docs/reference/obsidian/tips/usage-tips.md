# Obsidian Usage Tips

Obsidian 的实战技巧和最佳实践，专为 match3-wiki 项目优化。

## 快捷键速查

### 必备快捷键

| 功能 | macOS | Windows/Linux |
|------|-------|---------------|
| 快速切换文件 | `Cmd + O` | `Ctrl + O` |
| 命令面板 | `Cmd + P` | `Ctrl + P` |
| 全局搜索 | `Cmd + Shift + F` | `Ctrl + Shift + F` |
| 打开图谱视图 | `Cmd + G` | `Ctrl + G` |
| 新建笔记 | `Cmd + N` | `Ctrl + N` |
| 拆分窗口 | `Cmd + Click` | `Ctrl + Click` |
| 切换编辑/预览 | `Cmd + E` | `Ctrl + E` |
| 今日笔记 | `Cmd + D` | `Ctrl + D` |

### 编辑快捷键

| 功能 | 快捷键 |
|------|--------|
| 加粗 | `Cmd/Ctrl + B` |
| 斜体 | `Cmd/Ctrl + I` |
| 插入链接 | `Cmd/Ctrl + K` |
| 插入内部链接 | `[[` 然后开始输入 |
| 插入标签 | `#` 然后开始输入 |
| 插入代码块 | ` ``` ` |
| 切换待办 | `Cmd/Ctrl + L` |

### 自定义快捷键推荐

**Settings → Hotkeys** 中设置：

| 功能 | 推荐快捷键 |
|------|-----------|
| Templater: Insert Template | `Cmd/Ctrl + Shift + T` |
| Claudian: Process Selection | `Cmd/Ctrl + Shift + A` |
| QuickAdd: New Game Entry | `Cmd/Ctrl + Shift + G` |
| Toggle Kanban | `Cmd/Ctrl + Shift + K` |
| Open Daily Note | `Cmd/Ctrl + Shift + D` |

## 搜索技巧

### 基础搜索

```
游戏名         # 全文搜索
tag:#market    # 按标签搜索
path:raw/      # 按路径搜索
file:candy     # 按文件名搜索
```

### 高级搜索

```
# 布尔运算
candy OR royal                    # 或
candy AND mechanics               # 与
candy -crush                      # 排除

# 正则表达式
/revenue.*\d+M/                   # 匹配收入数据

# 组合查询
path:raw/ tag:#market candy       # 多条件组合

# 属性查询
[type:market-data]                # frontmatter 字段
```

### 搜索替换

1. `Cmd/Ctrl + Shift + F` 打开全局搜索
2. 点击右侧 "Replace" 按钮
3. 输入替换内容
4. "Replace" 单个替换，"Replace all" 批量替换

**实用场景**：
```
旧标签：#match3-game
新标签：#game

搜索：#match3-game
替换：#game
批量替换所有笔记
```

## 链接技巧

### 内部链接变体

```markdown
[[candy-crush]]                    # 基础链接
[[candy-crush|Candy Crush Saga]]   # 自定义显示文字
[[candy-crush#Core Mechanics]]     # 链接到标题
[[2026-04-22-report#^block-id]]    # 链接到块
```

### 创建块引用

1. 在目标段落末尾添加 `^block-id`
2. 在其他笔记引用：`![[note-name#^block-id]]`

**示例**：
```markdown
【在 candy-crush.md 中】
Revenue in 2025: $1.2B ^revenue-2025

【在其他笔记中引用】
Candy Crush's performance: ![[candy-crush#^revenue-2025]]
```

### 嵌入笔记

```markdown
![[candy-crush]]                   # 嵌入整个笔记
![[candy-crush#Overview]]          # 嵌入特定章节
![[image.png]]                     # 嵌入图片
![[report.pdf#page=5]]             # 嵌入 PDF 页面
```

## 标签策略

### 推荐标签结构

```yaml
# 内容类型
#raw           # 原始素材
#wiki          # wiki 条目
#report        # 报告
#note          # 临时笔记

# 主题分类
#market        # 市场数据
#ua            # 买量素材
#mechanics     # 游戏机制
#monetization  # 变现策略

# 状态标签
#draft         # 草稿
#review        # 待审核
#published     # 已发布
#archived      # 已归档

# 时间标签
#2026          # 年份
#q1            # 季度
```

### 标签使用原则

1. **扁平化**：避免嵌套标签（用 `#market-revenue` 而非 `#market/revenue`）
2. **一致性**：统一命名风格（全小写、连字符）
3. **适度性**：每篇笔记 2-5 个标签即可
4. **可检索**：标签应便于搜索和过滤

## 图谱视图技巧

### 基础操作

- **滚轮缩放**：查看全局或局部
- **拖动节点**：手动调整布局
- **点击节点**：打开对应笔记
- **右键节点**：
  - "Open in new pane" - 在新窗口打开
  - "Open local graph" - 查看局部图谱

### 过滤器

**按路径过滤**：
```
path:wiki/games/
```
只显示游戏 wiki 条目及其连接。

**按标签过滤**：
```
tag:#mechanics
```
只显示带机制标签的笔记。

**组合过滤**：
```
path:wiki/ -tag:#draft
```
显示所有非草稿的 wiki 条目。

### 着色规则

**Settings → Graph view → Groups**：

```
Group 1: Wiki 条目
  Query: path:wiki/
  Color: Blue

Group 2: 原始素材
  Query: path:raw/
  Color: Gray

Group 3: 市场数据
  Query: tag:#market
  Color: Green

Group 4: 买量素材
  Query: tag:#ua
  Color: Orange
```

### 找到孤立节点

**在图谱中**：
- 应用过滤器：`path:wiki/`
- 查看单独的节点（无连接线）
- 这些是"孤立页面"，需要添加链接

**或用 Dataview 查询**：
```dataview
LIST
FROM "wiki"
WHERE length(file.inlinks) = 0 AND length(file.outlinks) = 0
```

## Markdown 高级技巧

### Callout（标注块）

```markdown
> [!note]
> 这是一个笔记标注

> [!warning]
> 这是警告信息

> [!tip]
> 这是提示信息

> [!example]
> 这是示例
```

**效果**：
> [!note]
> 渲染为带图标的彩色标注框

### 折叠内容

```markdown
<details>
<summary>点击展开详细内容</summary>

这里是折叠的内容...

</details>
```

### 表格对齐

```markdown
| Left | Center | Right |
|:-----|:------:|------:|
| 左对齐 | 居中 | 右对齐 |
```

### 脚注

```markdown
这是一段文字[^1]，需要补充说明。

[^1]: 这是脚注内容
```

### 高亮

```markdown
这是==高亮文本==
```

## 多窗口工作流

### 分屏技巧

1. **左右分屏**：
   - 按住 `Cmd/Ctrl` 点击链接
   - 或拖动标签页到左/右边缘

2. **上下分屏**：
   - 拖动标签页到上/下边缘

3. **固定窗口**：
   - 右键标签页 → "Pin"
   - 固定的窗口不会被其他文件替换

### 推荐布局

**工作流 1：处理原始素材**
```
┌────────────────┬────────────────┐
│ 左：原始素材    │ 右：Wiki 条目   │
│ (raw/xxx.md)   │ (wiki/xxx.md)  │
│                │                │
│ 阅读、标注      │ 编写、整理      │
└────────────────┴────────────────┘
```

**工作流 2：对比多个游戏**
```
┌─────────┬─────────┬─────────┐
│ Candy   │ Royal   │ Home    │
│ Crush   │ Match   │ scapes  │
│         │         │         │
│ 对比三个游戏的机制和数据 │
└─────────┴─────────┴─────────┘
```

**工作流 3：数据收集+分析**
```
┌────────────────────────────────┐
│ 上：数据源笔记（多个标签页）      │
│ [AppMagic] [Sensor Tower] ...  │
├────────────────────────────────┤
│ 下：汇总分析笔记                │
│ 编写综合报告                    │
└────────────────────────────────┘
```

## 文件组织技巧

### 文件命名规范

**原始素材**：
```
YYYY-MM-DD-source-topic.md
2026-04-22-appmagic-candy-crush-revenue.md
2026-04-22-facebook-ad-royal-match.md
```

**Wiki 条目**：
```
lowercase-with-dashes.md
candy-crush-saga.md
match3-core-mechanics.md
```

**报告**：
```
YYYY-MM-topic-report.md
2026-04-market-overview-report.md
2026-q1-revenue-analysis.md
```

### 文件夹结构

```
match3-wiki/
├── raw/                    # 原始素材
│   ├── market/            # 市场数据
│   │   └── 2026-04/      # 按月分类
│   ├── ua/               # 买量素材
│   └── mechanics/        # 机制分析
├── wiki/                  # Wiki 条目
│   ├── games/            # 游戏条目
│   ├── mechanics/        # 机制词条
│   ├── studios/          # 开发商
│   └── markets/          # 市场分析
├── templates/            # 模板
├── attachments/          # 附件（图片、PDF）
└── _archive/             # 归档（过时内容）
```

### 定期清理

**每周**：
- 移动已处理的 raw 素材到 `_archive/raw/`
- 更新 Dashboard 笔记
- 检查 `status: draft` 的条目进度

**每月**：
- 生成月度统计报告
- 归档过时的市场数据
- 清理重复或低质量素材

## 工作流自动化

### 晨间启动流程

创建 `_morning-routine.md`：
```markdown
# Morning Routine

## 1. 检查昨日采集

```dataview
LIST
FROM "raw"
WHERE date_clipped = date(<%= tp.date.now("YYYY-MM-DD", -1) %>)
```

## 2. 今日任务

- [ ] 清洗 3 个 raw materials
- [ ] 完成 1 篇 wiki 条目
- [ ] 更新市场数据

## 3. 打开常用笔记

- [[_dashboard]]
- [[_wiki-workflow]]
- [[_todo-list]]
```

### 快速捕获

使用 QuickAdd 创建"收集箱"：

1. 创建 `_inbox.md`
2. 设置 QuickAdd：
   - 触发词：`/capture`
   - 动作：在 `_inbox.md` 末尾追加新条目
3. 快捷键：`Cmd/Ctrl + Shift + I`

随时记录想法，定期整理到正式笔记。

### 批量重命名

使用 Templater 脚本批量处理文件名：

```markdown
<%*
const files = app.vault.getMarkdownFiles()
  .filter(f => f.path.startsWith('raw/') && !f.basename.match(/^\d{4}-\d{2}-\d{2}/))

for (let file of files) {
  const newName = `2026-04-22-${file.basename}`
  await tp.file.rename(newName)
}
%>
```

## 性能优化

### 大型 Vault 优化

**问题**：笔记超过 1000 个时，Obsidian 可能变慢

**解决**：
1. **关闭实时预览**：Settings → Editor → Disable "Live Preview"
2. **减少插件**：禁用不常用的插件
3. **限制图谱范围**：用过滤器缩小 Graph View 范围
4. **归档旧笔记**：移动过时内容到 `_archive/`
5. **分割 Vault**：将历史数据移到单独的 vault

### 搜索加速

- 使用 Dataview 而非全局搜索（Dataview 有索引）
- 缩小搜索范围（`path:wiki/` 而非全局）
- 避免复杂正则表达式

### 同步优化

**iCloud/Dropbox 同步冲突解决**：
1. 关闭 Obsidian
2. 等待同步完成
3. 检查 `_conflicts/` 文件夹
4. 手动合并冲突内容
5. 删除冲突文件
6. 重新启动 Obsidian

**推荐同步方案**：
- **个人使用**：iCloud/Dropbox（免费）
- **多设备无冲突**：Obsidian Sync（$4/月）
- **团队协作**：Git + 自动同步脚本

## 移动端技巧

### 移动端工作流

**iOS/Android Obsidian 限制**：
- 插件功能受限（Dataview、Templater 可用，但性能较差）
- Web Clipper 不可用
- 文件管理不便

**推荐移动端用途**：
1. **快速查阅**：查看 wiki 条目
2. **轻量编辑**：修正错别字、添加标签
3. **快速捕获**：记录灵感到 inbox
4. **离线阅读**：在通勤时阅读笔记

**不推荐**：
- 大段写作（键盘体验差）
- 复杂编辑（拆分窗口、图谱不好用）
- 处理原始素材（需要桌面端的插件功能）

### 移动端配置

**简化插件**：
- 只保留核心插件（Templater、Calendar）
- 禁用性能杀手（Excalidraw、大型主题）

**快捷操作**：
- 添加常用笔记到"Starred"（⭐）
- 使用"Quick Switcher"（搜索框）快速跳转

## 故障排查

### 常见问题

**Q: Obsidian 启动慢？**
A: 
1. 禁用一半插件，测试启动速度
2. 逐个启用，找出问题插件
3. 清理 `.obsidian/workspace` 缓存

**Q: 图谱不显示连接？**
A: 
1. 检查链接格式（`[[file]]` 而非 `[file](file.md)`）
2. 刷新图谱视图（关闭再打开）
3. 重建索引：关闭 Obsidian，删除 `.obsidian/cache`，重启

**Q: Dataview 查询无结果？**
A: 
1. 检查 frontmatter 格式（YAML 语法正确吗？）
2. 检查路径（`FROM "raw"` 而非 `FROM "/raw"`）
3. 启用 Debug：Settings → Dataview → Debug mode

**Q: 同步冲突？**
A: 
1. 关闭所有设备的 Obsidian
2. 等待云同步完成
3. 在主设备打开，解决冲突
4. 等待同步，再打开其他设备

## 键盘导航高手技巧

### 快速跳转

```
Cmd/Ctrl + O         # 打开文件（输入名称模糊匹配）
Cmd/Ctrl + P         # 命令面板（输入命令）
Cmd/Ctrl + Shift + F # 全局搜索
Cmd/Ctrl + Click     # 在新窗口打开链接
```

### 编辑技巧

```
Cmd/Ctrl + [         # 回退历史
Cmd/Ctrl + ]         # 前进历史
Cmd/Ctrl + /         # 切换注释
Cmd/Ctrl + D         # 删除当前行
Alt + Up/Down        # 移动当前行
```

### Vim 模式（高级）

启用 Vim 键绑定：Settings → Editor → Vim key bindings

熟悉 Vim 的用户可以大幅提升编辑效率！

## 总结

掌握这些技巧后，Obsidian 使用效率可以提升 **5-10 倍**！

**重点回顾**：
1. ⌨️ 熟记核心快捷键
2. 🔍 善用搜索和过滤
3. 🔗 构建笔记连接网络
4. 📊 用 Dataview 监控进度
5. ⚡ 自动化重复任务
6. 🗂️ 保持文件结构清晰
7. 🧹 定期清理和归档
