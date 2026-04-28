# Obsidian

> 官网：https://obsidian.md

## 工具定位

Obsidian 是一款本地优先的个人知识管理（PKM）应用，基于纯文本 Markdown 文件构建。所有内容存储在本地"vault"（一个普通文件夹）中，没有专有格式锁定。核心承诺：你的笔记就是文件——任何文本编辑器都能读，数据永远属于你。

在 match3-wiki 工具链中，Obsidian 承担两个角色：**原始素材的入口**（通过 Web Clipper 浏览器插件）和**wiki 内容的浏览界面**（通过 Graph View 和反向链接）。

## 核心功能

### Vault 结构

Vault 就是一个目录。Obsidian 读取目录内所有 `.md` 文件并建立索引。没有数据库，没有同步锁，没有专有存储格式。可以：
- 用任何文本编辑器在 Obsidian 打开时同时编辑文件
- 用 git 对 vault 做版本控制
- 用任何文件同步工具备份

### 编辑模式与阅读模式

Obsidian 对笔记提供两种查看方式：

**编辑模式**：显示原始 Markdown 语法（`[[wikilink]]`、`**粗体**`、`# 标题` 等），用于编写和修改内容。点击文档顶部的铅笔图标或按 `Cmd/Ctrl + E` 进入。

**阅读模式**：渲染后的视图，Markdown 语法转换为格式化内容，链接可点击，图片显示。点击文档顶部的书本图标或按 `Cmd/Ctrl + E` 切换。

**实时预览模式**（推荐）：编辑时即时渲染，输入 `[[link]]` 后按空格或回车即变为可点击链接，无需切换模式。在 Settings → Editor → "Live Preview" 启用。

### Wikilink 与反向链接

Obsidian 使用 `[[页面名]]` wikilink 语法在笔记之间建立连接。在任意笔记的编辑模式下输入 `[[candy-crush]]`，Obsidian 创建一个指向 `candy-crush.md` 的可导航链接。

反向链接：每个页面都有面板显示所有链接到它的其他页面。

打开反向链接面板的方法：
1. 使用快捷键 `Cmd/Ctrl + Shift + B`（最简单）
2. 点击窗口右上角的**侧边栏切换按钮**（竖向三条线图标），显示右侧边栏
3. 在右侧边栏顶部有多个标签页图标，找到并点击**"Backlinks"**标签（可能显示为链条图标或文字）

反向链接面板会显示两类内容：
- **Linked mentions**：使用 `[[当前页面]]` 链接的位置
- **Unlinked mentions**：纯文本提到当前页面的位置

知识图谱由此自然涌现——不需要提前定义分类体系，边写边链，结构自己显现。

详见 [Wikilink 详细指南](./tips/wikilinks-guide.md)

### Graph View（图谱视图）

实时渲染的力导向图，展示所有笔记及其连接关系。功能：
- 按文件夹、标签或属性给节点着色
- 过滤只显示匹配查询的笔记
- 点击节点打开对应笔记
- 缩放到聚类查看局部结构
- "本地图谱"模式只显示当前打开笔记的邻域

### Canvas（画布）

无限白板，可以放置笔记、图片、网页剪藏，并在它们之间画连线。适合：
- 绘制竞品格局图（放置竞品卡片，画关系箭头，每张卡链接到实际 wiki 页面）
- 在开始写作前规划 wiki 结构
- 视觉化头脑风暴，直接连接到真实笔记

### Obsidian Sync

可选付费服务（约 $4/月）。端对端加密的跨设备同步，冲突感知——两台设备同时编辑同一笔记时，两个版本都会保留。

### Obsidian Publish

可选付费服务（约 $8/月）。将 vault（或其子集）一键发布为公开网站，支持搜索、交互式 Graph View、自定义域名和访问控制。

## 详细内容

- [安装与配置](./setup/installation.md)
- [Web Clipper 配置](./web-clipper/configuration.md)
- [插件配置](./plugins/recommended.md)
  - [Claudian](./plugins/claudian.md)
  - [Dataview](./plugins/dataview.md)
  - [Templater](./plugins/templater.md)
  - [其他实用插件](./plugins/others.md)
- [实战技巧](./tips/usage-tips.md)
- [最佳实践](./tips/best-practices.md)

## 在 match3-wiki 项目中的作用

### 双重角色：收集 + 浏览

**角色一——原始素材收集（输入端）**
```
浏览器 → Web Clipper → raw/ 文件夹 → /wiki:ingest
```

**角色二——wiki 浏览（输出端）**
```
wiki/ 编译产出 + graph.json → Obsidian → Graph View + 反向链接
```

### 具体使用场景

- **收集买量素材**：Web Clipper 剪藏 Facebook Ad Library 素材到 `raw/ua/`
- **收集市场数据**：剪藏 AppMagic/Sensor Tower 图表到 `raw/market/`
- **发现覆盖盲点**：Graph View 过滤 `path:wiki/`，孤立节点 = 覆盖盲点
- **绘制竞品地图**：Canvas 创建可视化地图，链接 wiki 页面
- **临时公开分享**：Obsidian Publish 作为 Phase 3 过渡方案

## 局限性

- 桌面应用为主，iOS/Android 端功能有限
- 500+ 笔记时 Graph View 视觉密集，必须使用过滤
- Web Clipper 对复杂排版页面转换质量较差
- Obsidian Publish 定制能力不如 Docusaurus
- 没有内置协同编辑，多用户需 Sync 或 git 工作流
