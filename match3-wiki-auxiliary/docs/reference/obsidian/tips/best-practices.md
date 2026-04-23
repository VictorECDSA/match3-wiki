# Obsidian Best Practices

针对 match3-wiki 项目的最佳实践指南。

## 笔记编写原则

### 1. 原子化原则

**每篇笔记应该只关注一个主题**。

**✅ 好的做法**：
```
candy-crush-core-mechanics.md     # 只讲核心机制
candy-crush-monetization.md       # 只讲变现策略
candy-crush-market-performance.md # 只讲市场表现
```

**❌ 不好的做法**：
```
candy-crush-everything.md         # 所有内容混在一起
```

**好处**：
- 易于链接和引用
- 方便更新维护
- 适合模块化组合

### 2. 链接优先原则

**用链接而非复制粘贴内容**。

**✅ 好的做法**：
```markdown
Royal Match 使用了类似 [[candy-crush-saga#Core Mechanics|Candy Crush 的核心机制]]，
但增加了区域修复系统。详见 [[area-restoration-mechanics]]。
```

**❌ 不好的做法**：
```markdown
Royal Match 使用了消除匹配系统，玩家通过匹配 3 个或更多相同颜色的宝石...
（把 Candy Crush 的内容完整复制一遍）
```

**好处**：
- 避免内容重复
- 信息更新只需改一处
- 构建知识网络

### 3. 元数据丰富原则

**为每篇笔记添加结构化的 frontmatter**。

**最小化模板**：
```yaml
---
title: Candy Crush Saga
date_created: 2026-04-22
tags: [game, match3, king]
---
```

**完整模板**（推荐）：
```yaml
---
title: Candy Crush Saga
date_created: 2026-04-22
date_updated: 2026-04-22
status: published
category: games
developer: King
release_date: 2012-04-12
tags: [game, match3, king, puzzle, casual]
raw_sources:
  - [[2026-04-20-appmagic-candy-crush]]
  - [[2026-04-21-sensor-tower-candy-crush]]
---
```

**好处**：
- 便于 Dataview 查询和统计
- 明确笔记状态和来源
- 追踪更新历史

## 内容组织策略

### 1. 双向链接网络

**不要只有单向链接**。

当你在 A 笔记链接到 B 时，考虑在 B 中也链接回 A（如果有意义）。

**示例**：
```markdown
【在 candy-crush.md 中】
这款游戏由 [[King]] 开发...

【在 king.md 中】
代表作品：[[Candy Crush Saga]], [[Farm Heroes Saga]]
```

**形成网络**而非树状结构。

### 2. MOC（Map of Content）模式

创建"地图笔记"作为主题的入口。

**示例：Match-3 机制大全**：
```markdown
# Match-3 Core Mechanics

这是 Match-3 游戏核心机制的索引页。

## 基础机制

- [[match-detection]] - 匹配检测算法
- [[cascade-system]] - 级联消除系统
- [[tile-generation]] - 方块生成规则

## 进阶机制

- [[power-ups]] - 道具系统
- [[combo-system]] - 连击系统
- [[board-constraints]] - 棋盘限制

## 特殊机制

- [[area-restoration]] - 区域修复（Royal Match）
- [[merge-mechanic]] - 合并机制
- [[blast-mechanic]] - 爆破机制

## 相关游戏

- [[candy-crush-saga]]
- [[royal-match]]
- [[homescapes]]
```

### 3. 标签层次

使用一致的标签体系。

**推荐层次**：

```
第一层：内容类型
#game, #studio, #mechanic, #report

第二层：细分主题
#market, #ua, #monetization, #mechanics

第三层：状态标记
#draft, #review, #published, #archived

时间标签（独立）
#2026, #q1, #april
```

**示例应用**：
```yaml
---
tags: [game, match3, market, published, 2026]
---
```

## 工作流设计

### 工作流 1：原始素材 → Wiki 条目

```
1. 采集
   Web Clipper 剪藏 → raw/
   ↓ 自动应用模板，填充元数据
   
2. 清洗
   打开 raw 笔记 → Claudian 清洗
   ↓ 移除杂项，保留关键信息
   
3. 提取
   Claudian: "Extract Game Mechanics"
   ↓ 提取结构化信息
   
4. 创建 Wiki
   templates/wiki-game.md
   ↓ 自动查找相关 raw materials
   
5. 编写内容
   参考 raw materials 编写
   ↓ 手动审核和补充
   
6. 发布
   status: draft → review → published
   ↓ 更新 frontmatter
   
7. 归档
   已处理的 raw → _archive/
```

### 工作流 2：多来源信息综合

```
1. 收集相关笔记
   搜索 → 标星 → 打开多个标签页
   
2. 创建综合笔记
   templates/synthesis.md
   
3. 列出来源
   - [[source-1]]
   - [[source-2]]
   
4. AI 辅助综合
   Claudian: "Based on linked notes, create comprehensive analysis"
   
5. 人工审核
   验证信息准确性，补充分析
   
6. 链接更新
   在原始笔记中链接到综合笔记
```

### 工作流 3：定期维护

**每日**（5 分钟）：
```
1. 打开 [[_dashboard]]
2. 查看昨日采集的 raw materials
3. 快速浏览，标记优先级
4. 更新今日待办事项
```

**每周**（30 分钟）：
```
1. 检查 Dataview 查询：
   - Draft 条目进度
   - 孤立页面（需要链接）
   - 过时的 raw materials

2. 处理积压：
   - 清洗至少 5 个 raw materials
   - 完成 1-2 个 draft 条目

3. 更新 MOC 页面

4. 归档已处理内容
```

**每月**（2 小时）：
```
1. 生成月度统计报告
2. 更新游戏排行榜
3. 检查标签一致性
4. 清理重复内容
5. 备份 vault
6. 回顾和优化工作流
```

## 数据质量标准

### 原始素材质量标准

**必须包含**：
```yaml
---
source: [URL]         # 来源链接
date_clipped: [日期]  # 采集日期
type: [类型]          # market-data/ua-creative/mechanics
domain: [域名]        # 来源网站
---
```

**内容要求**：
- 保留原始信息（不要过度编辑）
- 标注关键数据点
- 添加简短摘要
- 标记数据可信度

### Wiki 条目质量标准

**结构完整**：
- Overview（概览）
- Core Mechanics（核心机制）
- Market Performance（市场表现）
- Analysis（分析）
- References（参考资料）

**信息准确**：
- 所有数据注明来源
- 链接到 raw materials
- 区分事实和观点
- 标注数据时效性

**可维护性**：
- 明确的 frontmatter
- 适度的链接密度（每 100 字 2-3 个链接）
- 清晰的章节结构
- 定期更新日期

## 协作规范

### 多人协作

**文件命名约定**：
```
统一使用小写和连字符
candy-crush.md         ✅
Candy Crush.md         ❌
candy_crush.md         ❌
```

**编辑冲突预防**：
1. 编辑前先同步
2. 大改动创建新分支（如果用 Git）
3. 及时提交更改
4. 使用 Obsidian Sync 或 Git 自动同步

**审核流程**：
```yaml
---
status: draft     # 作者撰写中
        ↓
status: review    # 提交审核
        ↓
status: published # 审核通过
```

**评论规范**：
```markdown
> [!note] @reviewer-name 2026-04-22
> 建议补充市场数据来源

回复：
> [!note] @author-name 2026-04-23
> 已添加：[[2026-04-20-appmagic-candy-crush]]
```

## 备份策略

### 推荐备份方案

**方案 1：云同步（自动）**
- iCloud/Dropbox/OneDrive
- Obsidian Sync
- 优点：自动、实时
- 缺点：可能同步冲突

**方案 2：Git 版本控制（推荐）**
```bash
# 初始化仓库
git init
git add .
git commit -m "Initial commit"

# 每日自动提交（用 cron 或 Automator）
git add .
git commit -m "Daily backup $(date)"
git push origin main
```

**方案 3：定期导出**
```
每周导出 vault 为 ZIP
存储到外部硬盘或 NAS
```

**推荐组合**：
Git（版本控制） + Obsidian Sync（实时同步） + 月度完整备份

## 安全和隐私

### 敏感信息处理

**不要在笔记中直接存储**：
- API Keys
- 密码
- 个人隐私信息
- 付费数据的完整副本

**替代方案**：
- API Keys → 环境变量或密钥管理工具
- 数据 → 链接到原始来源，摘要引用
- 隐私信息 → 加密笔记插件（如 Meld Encrypt）

### Git 忽略规则

`.gitignore`：
```
# Obsidian 配置（包含 API Keys）
.obsidian/plugins/*/data.json

# 工作区缓存
.obsidian/workspace
.obsidian/workspace.json
.obsidian/cache

# 临时文件
.trash/
.DS_Store
```

## 常见陷阱

### ❌ 陷阱 1：过度组织

**问题**：花太多时间在文件夹结构、标签体系上，而不是写内容。

**解决**：
- 先写内容，后整理
- 简单的分类就够了（raw、wiki、templates）
- 用搜索和链接而非复杂文件夹

### ❌ 陷阱 2：孤立笔记

**问题**：创建了很多笔记，但互相没有链接。

**解决**：
- 每篇笔记至少有 2-3 个链接
- 用 Graph View 检查孤立节点
- 创建 MOC 页面连接相关笔记

### ❌ 陷阱 3：笔记过长

**问题**：一篇笔记写了几千字，难以维护和引用。

**解决**：
- 拆分为多个原子笔记
- 每个主题独立成篇
- 用链接而非大段复制

### ❌ 陷阱 4：忽略元数据

**问题**：没有 frontmatter，无法用 Dataview 查询。

**解决**：
- 使用 Templater 自动生成 frontmatter
- 强制要求所有笔记有基础元数据
- 用 Linter 自动格式化

### ❌ 陷阱 5：过度依赖插件

**问题**：装了 30+ 插件，Obsidian 又慢又不稳定。

**解决**：
- 保留核心插件（5-10 个）
- 定期审查插件使用频率
- 禁用不常用的插件

## 评估指标

### 项目健康度指标

**用 Dataview 监控**：

```dataview
TABLE 
  length(rows) as "数量"
FROM ""
GROUP BY type
```

**健康指标**：
- Raw materials / Wiki entries 比例：**3:1 到 5:1**
  - 太低：素材积压未处理
  - 太高：wiki 内容不足

- Draft entries 百分比：**< 20%**
  - 太高：内容积压未完成

- 孤立页面数量：**< 5%**
  - 太高：知识网络稀疏

- 每周新增 wiki 条目：**3-5 个**
  - 稳定输出

**月度报告模板**：
```markdown
# Match3 Wiki - 月度报告

**报告期**：2026-04

## 数据统计

- Raw materials 总数：150（+30）
- Wiki 条目总数：45（+8）
- Draft 条目：9（20%）
- 孤立页面：2（4.4%）

## 本月亮点

- 完成 Candy Crush 完整条目
- 新增 5 个竞品分析
- 建立 Match-3 机制词汇表

## 改进空间

- [ ] 清洗积压的 raw materials
- [ ] 完善 draft 条目
- [ ] 增加游戏间的链接

## 下月计划

- 完成 Royal Match 深度分析
- 建立变现策略对比表
- 优化 MOC 页面结构
```

## 进阶技巧

### 1. 使用别名（Aliases）

```yaml
---
title: Candy Crush Saga
aliases: [CCS, Candy Crush, 糖果传奇]
---
```

好处：
- `[[Candy Crush]]` 也能链接到这篇笔记
- 搜索别名也能找到
- 适合缩写、多语言、变体名称

### 2. 数据驱动的笔记

**在笔记中嵌入实时数据**：
```markdown
# Dashboard

本月采集：`= length(dv.pages('"raw"').where(p => p.date_clipped >= date(2026-04-01)))`
待处理：`= length(dv.pages('"raw"').where(p => p.status == "raw"))`
```

### 3. 模板继承

创建基础模板 `_base-template.md`：
```yaml
---
date_created: <% tp.date.now() %>
date_updated: <% tp.date.now() %>
---
```

其他模板引用：
```markdown
<%* tR += await tp.file.include("[[_base-template]]") %>

# 具体模板内容...
```

### 4. 使用 CSS Snippets 自定义样式

创建 `.obsidian/snippets/custom.css`：
```css
/* 高亮草稿状态 */
.frontmatter[data-status="draft"] {
  background-color: #fff3cd;
}

/* 已发布条目加绿色标记 */
.frontmatter[data-status="published"] {
  border-left: 3px solid #28a745;
}
```

Settings → Appearance → CSS snippets → 启用 `custom.css`

## 总结

遵循这些最佳实践，你的 match3-wiki 项目将：

✅ **结构清晰**：易于导航和维护
✅ **内容丰富**：知识网络完善
✅ **高效协作**：规范统一，减少冲突
✅ **持续进化**：定期评估和优化

**核心原则总结**：
1. 原子化笔记（一篇一主题）
2. 链接优先（构建网络）
3. 元数据丰富（便于查询）
4. 定期维护（保持健康）
5. 工具服务内容（不本末倒置）

记住：**最好的笔记系统是你实际会用的系统**。不要追求完美，先开始写，边用边优化！
