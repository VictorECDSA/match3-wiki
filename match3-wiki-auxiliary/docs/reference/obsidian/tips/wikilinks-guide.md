# Wikilink 详细指南

Obsidian 使用 `[[页面名]]` wikilink 语法在笔记之间建立连接。

## 如何使用

在 Obsidian 中打开任意笔记（`.md` 文件），在编辑模式下的正文中输入：

```markdown
[[candy-crush]]
```

输入 `[[` 后，Obsidian 会自动弹出文件名提示列表，继续输入可以过滤匹配的文件名，按 `Enter` 选择。

如果使用**实时预览模式**（推荐，Settings → Editor → "Live Preview"），输入 `[[candy-crush]]` 后按空格或回车，链接会立即渲染为可点击状态。

效果：
- 编辑模式：显示 `[[candy-crush]]`
- 阅读模式/实时预览：显示为可点击的链接
- 点击链接：打开 `candy-crush.md` 文件
- 目标文件不存在时，点击会创建该文件
- 在 `candy-crush.md` 的反向链接面板中，自动显示当前页面

关于编辑模式和阅读模式的详细说明，参见 [Obsidian 核心功能](../main.md#编辑模式与阅读模式)。

## 基本语法

```markdown
[[candy-crush]]
```

效果：
- 创建可点击链接，指向 `candy-crush.md`
- 在 `candy-crush.md` 的反向链接面板中自动显示当前页面
- 目标文件不存在时，点击会创建该文件

## 高级语法

### 自定义显示文本（别名）

使用 `|` 分隔链接目标和显示文本：

```markdown
[[candy-crush|糖果传奇]]
```

点击"糖果传奇"会跳转到 `candy-crush.md`。

应用场景：
- 英文文件名，中文显示：`[[match3-game|三消游戏]]`
- 简化显示：`[[games/puzzle/candy-crush|CC]]`
- 上下文适配：`[[level-design|关卡]]`、`[[level-design|设计]]`

### 链接到标题

```markdown
[[candy-crush#特殊道具]]
```

直接跳转到 `candy-crush.md` 中的"特殊道具"标题。

组合别名：
```markdown
[[candy-crush#特殊道具|CC 的道具系统]]
```

### 块引用（Block Reference）

给段落或列表项添加 `^block-id` 标识：

```markdown
三消游戏的核心乐趣在于消除的连锁反应。 ^core-fun
```

在其他笔记中引用：
```markdown
[[candy-crush#^core-fun]]
```

### 嵌入内容（Embed）

使用 `!` 前缀将其他笔记内容直接嵌入当前页面：

```markdown
![[candy-crush]]
```

嵌入部分内容：
```markdown
![[candy-crush#特殊道具]]      # 只嵌入"特殊道具"章节
![[candy-crush#^core-fun]]     # 只嵌入特定段落
```

应用场景：
- 在总览页面嵌入多个子页面的摘要
- 在对比分析文档中并排嵌入多个游戏的数据
- 创建可复用的"模板块"（如免责声明），多处嵌入引用

### 路径与子文件夹

多级目录结构示例：

```
vault/
├── games/
│   ├── puzzle/
│   │   ├── candy-crush.md
│   │   └── bejeweled.md
│   └── action/
│       └── angry-birds.md
└── concepts/
    └── match3.md
```

引用方式：
```markdown
[[games/puzzle/candy-crush]]    # 完整路径
[[puzzle/candy-crush]]          # 相对路径（如果唯一）
[[candy-crush]]                 # 文件名（如果 vault 中唯一）
```

Obsidian 智能识别规则：
- 文件名唯一时，只需写 `[[文件名]]`
- 有重名文件时，需要路径区分

## 反向链接（Backlinks）

反向链接自动追踪"哪些页面链接到了当前页面"。

打开方式：
- 点击右侧边栏的"Backlinks"面板
- 使用快捷键 `Cmd/Ctrl + Shift + B`

显示内容：
- **Linked mentions**（已链接提及）：所有使用 `[[当前页面]]` 语法的地方
- **Unlinked mentions**（未链接提及）：提到当前页面名称但未使用 `[[]]` 语法的地方（自动识别纯文本）

功能：
- 点击条目快速跳转到来源页面
- 查看上下文（显示链接前后的文本）
- 将"未链接提及"一键转换为 Wikilink

知识图谱自然涌现：不需要提前定义分类体系，边写边链，反向链接自动形成知识网络，通过 Graph View 可视化查看整个结构。

## 在 match3-wiki 项目中的应用

### 游戏关联

在 `candy-crush.md` 中：
```markdown
## 影响与衍生

Candy Crush 的成功催生了大量同类作品，如 [[cookie-jam]]、[[toon-blast]]。

其核心玩法继承自经典的 [[bejeweled]]，但加入了更多社交元素和关卡设计。
```

### 概念引用

在 `level-design.md` 中：
```markdown
## 难度曲线设计

三消游戏的难度曲线需要平衡挑战与成就感。以 [[candy-crush#关卡难度分布]] 为例，
每 15 关会出现一个"难关"，迫使玩家重复挑战或购买道具。
```

### 数据引用与自动更新

在 `match3-market-analysis.md` 中：
```markdown
## 头部产品对比

| 游戏 | 月收入 | DAU |
|------|--------|-----|
| ![[candy-crush#^revenue-data]] |
| ![[toon-blast#^revenue-data]] |
```

通过嵌入语法，子页面数据更新时，总览页面自动更新。

## 最佳实践

- **链接要自然**：写作时自然添加链接，不为了链接而链接
- **使用别名适配语境**：`[[match3|三消]]` 比裸露的 `match3` 更自然
- **定期查看反向链接**：发现意外的知识关联
- **利用未链接提及**：Obsidian 提示可补充的链接
- **命名规范**：使用 kebab-case（如 `candy-crush`），避免空格和特殊字符
- **适度使用嵌入**：嵌入过多会导致页面加载缓慢，优先使用普通链接

## 快捷键

- `[[`：触发 Wikilink 自动补全（开始输入文件名）
- `Cmd/Ctrl + Click`：在新窗格中打开链接
- `Cmd/Ctrl + Shift + B`：打开/关闭反向链接面板
- `Cmd/Ctrl + O`：快速打开文件（fuzzy search）
