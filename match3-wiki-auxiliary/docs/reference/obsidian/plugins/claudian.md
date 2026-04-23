# Claudian - 在 Obsidian 中使用 Claude Code

> 官方地址：https://github.com/chuangcaleb/obsidian-claudian

## 工具定位

Claudian 是一个将 **Claude Code CLI** 集成到 Obsidian 的插件，让你在笔记软件里直接使用 Claude Code 的强大能力，无需来回切换终端和编辑器。

### 与其他 AI 插件的区别

**传统 AI 插件（如 Text Generator）**：
- 需要配置 API Key
- 每次调用都消耗 API 额度
- 无法访问本地文件系统
- 只能处理当前笔记内容

**Claudian 的优势**：
- ✅ **使用本地 Claude Code**：不需要额外配置 API Key
- ✅ **完整的文件系统访问**：可以读写 vault 中的任何文件
- ✅ **多步骤工作流**：自动执行复杂任务（如批量处理、数据提取）
- ✅ **上下文理解**：理解笔记之间的链接关系
- ✅ **实时交互**：流式输出，即时查看 AI 生成内容

### 在 match3-wiki 中的应用

1. **原始素材清洗**：将 Web Clipper 剪藏的杂乱 HTML 转换为结构化 Markdown
2. **内容提取**：从长文中提取关键信息（游戏机制、数据要点）
3. **Wiki 初稿生成**：基于 `raw/` 文件夹的素材自动生成 wiki 条目
4. **批量处理**：一次性处理多个笔记（如统一格式、提取元数据）
5. **内容重组**：合并多个来源的信息，生成综合分析

## 前置要求

在安装 Claudian 之前，确保你已经：

### 1. ✅ 安装 Claude Code CLI

**检查是否已安装**：
```bash
claude --version
```

如果提示 "command not found"，参考 [Claude Code 安装文档](https://docs.anthropic.com/claude-code) 进行安装。

**macOS/Linux 安装**：
```bash
# 使用 Homebrew（macOS）
brew install anthropic-ai/tap/claude

# 或使用 npm（跨平台）
npm install -g @anthropic-ai/claude-code
```

**Windows 安装**：
```powershell
# 使用 npm
npm install -g @anthropic-ai/claude-code
```

### 2. ✅ 登录 Claude Code

```bash
claude auth login
```

按照提示完成登录，确保 `claude` 命令可以正常工作。

### 3. ✅ 获取 `claude` 可执行文件的完整路径

**macOS/Linux**：
```bash
which claude
```

**常见输出**：
- macOS Homebrew：`/opt/homebrew/bin/claude`
- macOS Intel：`/usr/local/bin/claude`
- npm 全局安装：`/usr/local/bin/claude` 或 `~/.npm-global/bin/claude`

**Windows**：
```powershell
where.exe claude
```

**常见输出**：
- `C:\Users\YourName\AppData\Roaming\npm\claude.cmd`

**⚠️ 重要**：记下这个完整路径，后面配置 Claudian 时需要用到。

## 安装 Claudian 插件

⚠️ **重要提示**：Claudian 目前**尚未上架 Obsidian 官方插件市场**，需要使用 BRAT 插件安装。

### 使用 BRAT 插件安装（推荐方式）

#### 第一步：安装 BRAT 插件

BRAT (Beta Reviewers Auto-update Tester) 是一个用于安装未上架插件的工具。

1. 打开 Obsidian → **Settings** → **Community plugins**
2. 如果是首次安装插件，先关闭 **"Restricted mode"**
3. 点击 **"Browse"** 搜索 **"BRAT"**
4. 找到 **"Obsidian42 - BRAT"** → 点击 **Install** → **Enable**

#### 第二步：使用 BRAT 安装 Claudian

1. **打开 Settings**：
   - 点击 Obsidian 左下角的 **齿轮图标 ⚙️**
   - 或使用快捷键 `Cmd + ,`（macOS）/ `Ctrl + ,`（Windows）

2. **找到 BRAT 设置页面**：
   - 在 Settings 窗口的**左侧菜单**中，向下滚动
   - 找到 **"Plugin Options"** 或 **"插件选项"** 这个分组（通常在菜单中下部）
   - 在这个分组下面会列出所有已启用插件的名字
   - 找到并点击 **"BRAT"**
   
   > 💡 **找不到 BRAT？** 
   > 可能是还没启用。先点击左侧的 "Community plugins"，在右侧插件列表中找到 BRAT，确保开关是打开状态（蓝色）。启用后，BRAT 就会出现在 "Plugin Options" 下。

3. **添加 Claudian**：
   - 点击右侧内容区的 **"Add Beta plugin"** 按钮
   - 在弹出的输入框中填入以下 GitHub 仓库地址（**二选一**）：
     ```
     YishenTu/claudian
     ```
     或
     ```
     nhaugaard/obsidian-claudian
     ```
   - 点击 **"Add Plugin"** 或 **"提交"**

4. **等待安装**：
   - BRAT 会自动从 GitHub 下载 Claudian
   - 通常需要 10-30 秒
   - 你会看到进度提示或完成通知

5. **启用 Claudian**：
   - 安装完成后，点击左侧菜单的 **"Community plugins"**
   - 在右侧插件列表中找到 **"Claudian"**
   - 点击右边的**开关**，确保变为蓝色（已启用状态）

✅ **完成！** Claudian 插件现在已安装并启用。

✅ **完成！** Claudian 插件已成功安装。

---

### 备选方案：手动安装（不推荐）

如果 BRAT 安装失败，可以尝试手动安装（较复杂）：

<details>
<summary>点击展开手动安装步骤</summary>

1. **下载插件文件**：
   - 访问 https://github.com/YishenTu/claudian
   - 点击绿色 **"Code"** 按钮 → **"Download ZIP"**
   - 解压下载的文件

2. **构建插件**（需要 Node.js 环境）：
   ```bash
   cd claudian-main
   npm install
   npm run build
   ```

3. **复制到 Obsidian**：
   - 在你的 vault 中找到 `.obsidian/plugins/` 文件夹
     - **macOS 显示隐藏文件**：`Cmd + Shift + .`
     - **Windows 显示隐藏文件**：文件管理器 → 查看 → 显示隐藏的文件
   - 创建文件夹 `.obsidian/plugins/claudian/`
   - 将构建生成的 `main.js`、`manifest.json`、`styles.css` 复制到该文件夹

4. **重启并启用**：
   - 重启 Obsidian
   - Settings → Community plugins → 启用 **Claudian**

⚠️ **手动安装的缺点**：
- 需要 Node.js 和构建工具
- 无法自动更新
- 步骤繁琐容易出错

**强烈推荐使用 BRAT 安装！**

</details>

## 配置 Claudian

### 1. 设置 Claude CLI 路径

这是最关键的一步！

1. **打开 Claudian 设置页面**：
   - 进入 Obsidian **Settings**（左下角齿轮图标 ⚙️）
   - 在左侧菜单的 **"Plugin Options"** 分组下，找到并点击 **"Claudian"**
   - 注意：Claudian 设置页面顶部有多个 **tab 标签**（如 "General"、"Claude"、"Advanced" 等）
   - **点击 "Claude" 标签**（这是配置 CLI 路径的地方）

2. **填入 Claude CLI 路径**：
   - 在 "Claude" 标签下，找到 **"Client Path"** 或 **"Claude CLI Path"** 设置项
   - 填入你之前获取的 `claude` 可执行文件的**完整绝对路径**

3. **获取 Claude CLI 路径**（如果还没获取）：
   ```bash
   # macOS/Linux
   which claude
   # 或
   which claude-internal
   
   # Windows
   where.exe claude
   ```

**示例路径**：
- ✅ 正确：`/opt/homebrew/bin/claude`
- ✅ 正确：`/usr/local/bin/claude`
- ✅ 正确：`/Users/fenghaoming/.nvm/versions/node/v23.10.0/bin/claude-internal`
- ✅ 正确（Windows）：`C:\Users\YourName\AppData\Roaming\npm\claude.cmd`
- ❌ 错误：`claude`（缺少完整路径）
- ❌ 错误：`~/bin/claude`（波浪号 `~` 可能无法识别，请用完整路径）

#### 🔍 特殊情况：使用 claude-internal（腾讯内部版本）

如果你使用的是 `@tencent/claude-code-internal`（通过 npm 安装的内部版本），路径通常是：

```bash
/Users/你的用户名/.nvm/versions/node/v版本号/bin/claude-internal
```

**查找方法**：
```bash
# 找到 claude-internal 的位置
whereis claude-internal

# 或
which claude-internal

# 验证路径是否正确
ls -al /Users/fenghaoming/.nvm/versions/node/v23.10.0/bin/claude-internal
```

**填入 Claudian**：
- 直接填入完整路径，例如：
  ```
  /Users/fenghaoming/.nvm/versions/node/v23.10.0/bin/claude-internal
  ```

**注意**：
- 不要填 symlink 指向的 `.js` 文件路径（如 `../lib/node_modules/.../claude-code-internal.js`）
- 直接填 `/bin/claude-internal` 这个可执行文件的完整路径即可
- Claudian 会自动处理 symlink

4. **测试连接**：
   - 点击 **"Test Connection"** 按钮（如果有）
   - 或直接尝试在侧边栏打开 Claudian 对话框测试

### 2. 其他推荐设置

```yaml
【基本设置】
Claude CLI Path:     [你的完整路径]
Enable Streaming:    ✓ 启用（实时显示生成过程）

【工作区设置】
Vault Root:          [自动检测，无需修改]
Max Context Files:   10（限制一次读取的文件数量）

【界面设置】
Show in Sidebar:     ✓ 启用（侧边栏显示对话面板）
Auto-scroll:         ✓ 启用（自动滚动到生成内容）
```

## 核心功能

### 1. 侧边栏对话（推荐方式）

**打开方式**：
- 点击 Obsidian 左侧边栏的 **机器人图标**
- 或使用命令面板：`Cmd/Ctrl + P` → 输入 "Claudian: Open Chat"
- 或设置快捷键（推荐 `Cmd/Ctrl + Shift + C`）

**使用场景**：
```
【场景 1：询问笔记内容】
你：这个笔记里提到的"cascading match"是什么机制？

Claude：根据当前笔记内容，"cascading match"（连锁消除）是指...
```

```
【场景 2：基于多个笔记生成内容】
你：根据 raw/market/ 文件夹下的所有笔记，生成一份 Royal Match 的市场表现报告

Claude：[自动读取相关文件] 好的，我将基于以下素材生成报告...
```

```
【场景 3：批量处理】
你：将 raw/2026-04/ 下所有笔记的 frontmatter 添加 tags 字段

Claude：[扫描文件夹] 我发现 15 个笔记需要处理，开始更新...
```

### 2. 选中文本处理

**使用方式**：
1. 在笔记中选中一段文字
2. 右键 → **"Claudian"** → 选择操作
3. 或使用快捷键（可自定义）

**常用操作**：
- **Summarize Selection**：总结选中内容
- **Improve Writing**：改进文本（修正语法、优化表达）
- **Translate**：翻译成其他语言
- **Explain**：解释专业术语或复杂概念
- **Extract Key Points**：提取关键信息

**实际示例**：
```markdown
【原始剪藏内容（选中这段）】
The game features a unique "cascading matches" mechanic where
cleared tiles fall and new ones appear from the top, potentially
creating chain reactions. Players can trigger "power-ups" by
matching 4+ tiles in specific patterns...

↓ 右键 → Claudian: Summarize Selection ↓

【生成总结（自动插入到下方）】
**Core Mechanics:**
- Cascading match system (falling tiles + chain reactions)
- Power-ups triggered by 4+ tile patterns
- Chain reaction potential for combo scores
```

### 3. 命令面板快捷操作

打开命令面板（`Cmd/Ctrl + P`）输入以下命令：

| 命令 | 功能 | 使用场景 |
|------|------|----------|
| `Claudian: Chat` | 打开对话面板 | 需要持续交互 |
| `Claudian: Ask About Current Note` | 询问当前笔记 | 快速理解笔记内容 |
| `Claudian: Generate Content` | 生成新内容 | 基于提示词创建新笔记 |
| `Claudian: Clean Up Note` | 清理笔记格式 | 处理 Web Clipper 剪藏的杂乱内容 |
| `Claudian: Extract Data` | 提取结构化数据 | 从长文中提取表格、列表 |
| `Claudian: Batch Process` | 批量处理 | 对多个笔记执行相同操作 |

### 4. 自动文件读取（核心优势）

Claude Code 可以**自动理解你的请求并读取相关文件**，无需手动指定：

**示例 1：智能文件查找**
```
你：Royal Match 的买量策略有哪些特点？

Claude 自动：
1. 扫描 vault 中包含 "Royal Match" 和 "user acquisition" 的笔记
2. 读取 raw/ua/ 文件夹下的相关素材
3. 整合信息并回答
```

**示例 2：链接笔记理解**
```
你：把这个笔记里提到的所有游戏的数据整理成表格

Claude 自动：
1. 识别笔记中的 [[Game Name]] 链接
2. 读取被链接的笔记
3. 提取数据并生成表格
```

**示例 3：文件夹批量操作**
```
你：将 raw/market/2026-04/ 下的所有报告合并成一个月度总结

Claude 自动：
1. 列出该文件夹下的所有 .md 文件
2. 逐个读取内容
3. 提取关键数据
4. 生成汇总报告并保存为新笔记
```
## match3-wiki 实战应用

### 场景 1：清洗 Web Clipper 剪藏的杂乱内容

**问题**：从 AppMagic、Sensor Tower 剪藏的页面包含大量无关内容（导航栏、广告、页脚等）

**解决流程**：
1. 打开 Web Clipper 剪藏的笔记（如 `raw/market/2026-04/2026-04-22-royal-match-report.md`）
2. 全选内容（`Cmd/Ctrl + A`）
3. 打开 Claudian 对话框（侧边栏机器人图标）
4. 输入提示：
   ```
   清洗这个剪藏内容：
   1. 删除导航菜单、广告、页脚等无关内容
   2. 修复表格格式
   3. 保留核心数据和关键引用
   4. 整理成清晰的 Markdown 结构
   ```
5. Claude 生成清洗后的内容
6. 复制替换原笔记内容

**进阶**：创建自定义快捷命令
- Settings → Claudian → 添加自定义提示词
- 名称：`Clean Clippings`
- 快捷键：`Cmd/Ctrl + Shift + L`
- 提示词：（同上）

### 场景 2：从长文中提取游戏机制

**问题**：一篇 5000 字的游戏分析文章，只想提取核心玩法机制部分

**解决流程**：
1. 打开长文笔记
2. 不需要手动选中任何内容
3. 打开 Claudian 对话框
4. 输入：
   ```
   从当前笔记中提取游戏机制信息，按以下结构整理：
   
   ## Core Gameplay Loop
   [描述]
   
   ## Progression System
   [描述]
   
   ## Monetization Mechanics
   [描述]
   
   ## Social Features
   [描述]
   
   ## Unique Innovations
   [描述]
   ```
5. Claude 自动读取笔记并生成结构化内容
6. 将生成的内容保存为新笔记 `wiki/mechanics/[game-name]-mechanics.md`

### 场景 3：基于多个来源生成 Wiki 条目

**问题**：收集了 Royal Match 的市场报告、玩法分析、买量素材等多个笔记，想综合生成一个完整的 wiki 条目

**解决流程**：
1. 在 `wiki/games/` 创建新笔记 `royal-match.md`
2. 打开 Claudian 对话框
3. 输入：
   ```
   请基于以下素材生成 Royal Match 的完整 wiki 条目：
   - raw/market/2026-04/2026-04-22-royal-match-revenue.md
   - raw/mechanics/royal-match-gameplay-analysis.md
   - raw/ua/2026-04/royal-match-ad-creative.md
   
   wiki 条目结构：
   1. Overview（游戏简介）
   2. Core Mechanics（核心机制）
   3. Market Performance（市场表现）
   4. UA Strategy（买量策略）
   5. Key Insights（关键洞察）
   ```
4. Claude 自动：
   - 读取这 3 个文件
   - 提取关键信息
   - 整合生成完整条目
5. 生成的内容直接插入到当前笔记

**关键点**：无需手动打开那些文件，Claude Code 会自动读取！

### 场景 4：批量添加 Frontmatter 标签

**问题**：`raw/2026-04/` 文件夹下有 20 个剪藏笔记，都缺少 `tags` 字段

**解决流程**：
1. 打开 Claudian 对话框
2. 输入：
   ```
   请处理 raw/2026-04/ 文件夹下的所有 Markdown 文件：
   1. 如果没有 frontmatter，添加一个
   2. 在 frontmatter 中添加 tags 字段
   3. 根据文件名和内容自动分类（market、mechanics、ua 等）
   4. 保持原有内容不变
   ```
3. Claude 会：
   - 扫描该文件夹
   - 列出所有文件
   - 逐个读取并更新
   - 报告处理结果

**注意**：Claude Code 可以直接修改文件！处理前建议备份或使用 git。

### 场景 5：生成月度报告

**问题**：每月需要汇总 `raw/market/2026-04/` 下的所有市场数据

**解决流程**：
1. 创建新笔记 `reports/2026-04-market-summary.md`
2. 打开 Claudian 对话框
3. 输入：
   ```
   请分析 raw/market/2026-04/ 下的所有报告，生成月度市场总结：
   
   ## Top Performers
   - 列出收入 Top 5 的游戏及数据
   
   ## Emerging Trends
   - 识别新出现的玩法模式
   - 识别买量策略变化
   
   ## Key Insights
   - 市场整体趋势
   - 值得关注的现象
   
   ## Data Table
   [生成对比表格]
   ```
4. Claude 自动：
   - 读取该月所有报告
   - 提取关键数据
   - 生成汇总分析

### 场景 6：理解笔记之间的链接关系

**问题**：`match3-mechanics.md` 里提到了多个游戏，想了解这些游戏的机制共同点

**解决流程**：
1. 打开 `match3-mechanics.md`
2. 打开 Claudian 对话框
3. 输入：
   ```
   当前笔记中提到了哪些游戏？
   请读取这些游戏的详细笔记，对比它们的核心机制，找出：
   1. 共同模式
   2. 差异化创新点
   3. 演化趋势
   ```
4. Claude 会：
   - 识别笔记中的游戏名称
   - 搜索对应的详细笔记（如 `wiki/games/candy-crush.md`）
   - 读取相关内容
   - 生成对比分析

**无需手动创建链接！** Claude Code 会智能查找相关文件。

## 推荐工作流

### 工作流 A：每日剪藏处理（10 分钟）

```
1. 早上用 Web Clipper 剪藏 5-10 个页面到 raw/
2. 在 Obsidian 打开 Claudian 侧边栏
3. 输入："清洗今天剪藏的所有笔记（raw/2026-04-22-*.md），删除无关内容，提取关键信息"
4. Claude 批量处理所有笔记
5. 快速浏览结果，标记重要内容
```

### 工作流 B：每周 Wiki 条目创建（30 分钟）

```
1. 查看本周收集的素材（Dataview 查询）
2. 选择 2-3 个有足够信息的游戏
3. 对每个游戏：
   - 创建 wiki/games/[game-name].md
   - 使用 Claudian："基于 raw/ 文件夹下所有关于 [game] 的素材，生成完整 wiki 条目"
   - Claude 自动整合信息
4. 人工审核编辑（补充个人见解、调整结构）
5. 标记为已完成
```

### 工作流 C：月度分析报告（1 小时）

```
1. 创建 reports/2026-04-analysis.md
2. 使用 Claudian：
   "基于本月收集的所有素材，生成综合分析报告：
    - 市场趋势（raw/market/2026-04/）
    - 新机制出现（raw/mechanics/2026-04/）
    - 买量策略变化（raw/ua/2026-04/）
    - Top insights"
3. Claude 生成初稿
4. 人工补充：
   - 个人分析和预测
   - 对项目的启示
   - 行动建议
5. 分享给团队
```


## 常见问题

### Q1: 插件提示 "Claude Code not found"？

**原因**：Claudian 找不到 `claude` 可执行文件

**解决步骤**：
```bash
# 1. 确认 claude 已安装
claude --version

# 2. 如果未安装，先安装
brew install anthropic-ai/tap/claude   # macOS
# 或
npm install -g @anthropic-ai/claude-code

# 3. 获取完整路径
which claude

# 4. 在 Claudian 设置中填入完整路径
# 例如：/opt/homebrew/bin/claude
```

### Q2: 提示 "Authentication failed"？

**原因**：Claude Code CLI 未登录或 session 过期

**解决**：
```bash
# 重新登录
claude auth login

# 验证登录状态
claude auth status
```

### Q3: 生成内容不准确或不完整？

**检查清单**：
1. **提示词是否清晰**：
   ```
   ❌ 模糊："帮我处理这个笔记"
   ✅ 清晰："提取这个笔记中的市场数据（收入、下载量、用户数），整理成表格"
   ```

2. **上下文是否足够**：
   - 如果 Claude 说"找不到相关信息"，明确指定文件路径
   - 例如："读取 raw/market/2026-04/royal-match-report.md"

3. **任务是否太复杂**：
   - 拆分成多个小任务，逐步完成

### Q4: 如何避免 Claude 误改重要文件？

**安全措施**：
1. **使用 git 版本控制**：
   ```bash
   cd /path/to/vault
   git init
   git add .
   git commit -m "backup before using Claudian"
   ```

2. **让 Claude 先生成预览**：
   ```
   你：请生成修改计划，但先不要执行
   Claude：[列出将要修改的文件和操作]
   你：（确认无误后）好的，执行
   ```

3. **重要笔记加锁**：
   - 设置文件为只读（macOS: `chmod 444 important-note.md`）

### Q5: 能否批量处理多个笔记？

**可以！** 这是 Claude Code 的核心优势之一。

**示例**：
```
你：将 raw/2026-04/ 下所有笔记的 frontmatter 添加 date_created 字段，
    值为文件名中的日期（YYYY-MM-DD 格式）

Claude：
[扫描文件夹] 我发现 18 个笔记需要处理：
- 2026-04-22-royal-match.md
- 2026-04-22-candy-crush.md
...

[逐个更新] 完成！所有 18 个笔记已更新。
```

### Q6: 与直接使用 Claude Code 终端相比，Claudian 的优势是什么？

**Claudian 的优势**：
- ✅ **无需切换**：在 Obsidian 里直接使用，不用开终端
- ✅ **可视化界面**：侧边栏对话，更直观
- ✅ **快速选择**：直接选中文本处理
- ✅ **自定义命令**：配置常用提示词，一键触发

**Claude Code 终端的优势**：
- ✅ **更强大的文件操作**：可以运行脚本、安装依赖
- ✅ **多项目支持**：不局限于当前 vault
- ✅ **更灵活**：可以执行任意系统命令

**推荐**：
- 日常笔记处理 → Claudian（方便快捷）
- 复杂工作流 / 批量脚本 → 终端 Claude Code

### Q7: 费用问题？

**好消息**：Claudian 使用的是你本地的 Claude Code 订阅，**不额外收费**！

- 如果你有 Claude Pro 订阅（$20/月），Claudian 使用的是同一个额度
- 如果你用的是免费版 Claude Code，Claudian 也遵循相同的限制

**与 API 插件的区别**：
- API 插件（如旧版 Text Generator）：按 token 计费，需要单独充值
- Claudian + Claude Code：订阅制，无需担心每次调用的费用

### Q8: Claudian 会上传我的 vault 内容吗？

**隐私说明**：
- Claudian 调用本地的 `claude` CLI 工具
- `claude` 会将你的提示词和上下文发送到 Anthropic 服务器
- 只有你明确要求 Claude 读取的文件才会被发送
- 与直接使用 Claude Code 终端的隐私级别完全相同

**建议**：
- 敏感内容（个人日记、密码）不要让 Claude 处理
- 或使用本地 LLM 插件（如 Local GPT）处理敏感笔记

### Q9: 生成内容的格式很乱，怎么改进？

**在提示词中明确要求格式**：
```
你：从这个报告中提取市场数据

要求：
1. 输出格式必须是 Markdown 表格
2. 表格列：游戏名 | 月收入 | 下载量 | 来源
3. 数据保留 2 位小数
4. 来源链接使用 [text](url) 格式
```

**或创建格式模板**：
```
你：按照以下模板格式提取数据：

## Market Data

| Game | Revenue | Downloads | Source |
|------|---------|-----------|--------|
| [name] | $X.XXM | X.XXM | [link] |

原始内容：
[粘贴内容]
```

### Q10: 如何设置快捷键？

**设置步骤**：
1. Settings → Hotkeys → 搜索 "Claudian"
2. 推荐快捷键设置：
   ```
   Claudian: Open Chat           → Cmd/Ctrl + Shift + C
   Claudian: Process Selection   → Cmd/Ctrl + Shift + P
   Claudian: Clean Clippings     → Cmd/Ctrl + Shift + L
   Claudian: Extract Data        → Cmd/Ctrl + Shift + E
   ```

## 完整配置示例

以下是适合 match3-wiki 项目的完整 Claudian 配置：

```yaml
【基本设置 - Settings → Claudian】
Claude CLI Path:     /opt/homebrew/bin/claude  # 你的实际路径
Enable Streaming:    ✓ 启用
Auto-scroll:         ✓ 启用
Show in Sidebar:     ✓ 启用

【快捷键 - Settings → Hotkeys】
Open Chat:           Cmd/Ctrl + Shift + C
Process Selection:   Cmd/Ctrl + Shift + P

【工作区设置（如有）】
Vault Root:          [自动检测]
Max Context Files:   10
```

**Settings → Claudian**：
```yaml
【API Settings】
API Key:           sk-ant-api03-xxxx
Model:             claude-3-5-sonnet-20241022
Max Tokens:        8192
Temperature:       0.7

【Output Settings】
Stream Response:   ✓
Insert at Cursor:  ✓
Add Separator:     ✓ (----)
Preserve Context:  ✓

【Context Settings】
Include Backlinks: ✓
Include Outlinks:  ✗ (避免过多上下文)
Max Context:       20000 chars
Context Format:    Markdown

【Custom Prompts】
1. Clean Clipper Output
2. Extract Game Mechanics
3. Extract Market Data
4. Generate Wiki Entry
5. Summarize Sources
6. Translate to Chinese
7. Compare Games
8. Identify Trends
```

**快捷键设置**（Settings → Hotkeys）：
```
Claudian: Open Chat               → Cmd/Ctrl + Shift + C
Claudian: Process Selection       → Cmd/Ctrl + Shift + P
Claudian: Clean Clippings         → Cmd/Ctrl + Shift + L
Claudian: Extract Data            → Cmd/Ctrl + Shift + E
```

这样配置后，处理原始素材的效率可以提升 5-10 倍！

## 最佳实践

### 1. 提示词编写技巧

**❌ 模糊的提示词**：
```
帮我整理一下这个笔记
```

**✅ 清晰的提示词**：
```
清洗这个 Web Clipper 剪藏内容：
1. 删除导航栏、广告、页脚
2. 修复 Markdown 表格格式
3. 提取核心数据点（收入、下载量、DAU）
4. 在顶部添加 3-5 句总结
5. 保留原始来源链接
```

**关键原则**：
- **明确任务**：说清楚要做什么
- **具体步骤**：列出操作顺序
- **格式要求**：指定输出格式（表格、列表、段落）
- **保留什么**：哪些信息必须保留
- **删除什么**：哪些内容需要移除

### 2. 文件路径指定

**相对路径（推荐）**：
```
从 raw/market/2026-04/ 读取所有报告
```

**完整文件名**：
```
读取 raw/market/2026-04/2026-04-22-royal-match-revenue.md
```

**模糊匹配（让 Claude 查找）**：
```
找到所有关于 Royal Match 买量策略的笔记并总结
```

### 3. 批量操作的安全原则

**先预览，再执行**：
```
你：将 raw/2026-04/ 下所有笔记添加 tags 字段，但先告诉我会修改哪些文件

Claude：我将修改以下 18 个文件：
- 2026-04-22-royal-match.md
- 2026-04-22-candy-crush.md
...

你：好的，执行

Claude：[开始批量处理]
```

**使用 git 版本控制**：
```bash
# 处理前先提交
git add .
git commit -m "before Claudian batch processing"

# 如果出问题，回滚
git reset --hard HEAD
```

### 4. 上下文管理

**减少不必要的上下文**：
- 明确指定要读取的文件/文件夹
- 避免"读取整个 vault"这种请求
- 大文件只让 Claude 读取相关章节

**利用文件夹结构**：
```
你：总结 raw/market/2026-04/ 下的所有报告

✅ 明确的范围，Claude 只读取该文件夹
```

### 5. 工作流自动化

**创建"流水线"提示词**：
```
你：对当前笔记执行以下流水线：
1. 删除无关内容（导航、广告）
2. 提取关键数据到表格
3. 生成 3 句摘要
4. 添加 frontmatter（source, date_clipped, type）
5. 保存结果

Claude：[自动执行 5 步操作]
```

**使用模板文件**：
- 在 `templates/` 创建常用提示词模板
- 每次复制粘贴到 Claudian 对话框
- 或配置为自定义命令

### 6. 质量检查

**AI 生成内容需要人工审核**：
- ✅ 数据提取（高准确度）
- ✅ 格式清理（高准确度）
- ⚠️ 内容总结（需审核）
- ⚠️ 趋势分析（需审核和补充）
- ❌ 关键决策（不能完全依赖 AI）

**审核检查清单**：
- [ ] 数据是否准确（与原始素材对比）
- [ ] 引用来源是否正确
- [ ] Markdown 格式是否正常
- [ ] 是否有遗漏的关键信息
- [ ] 是否有误导性的分析

## 总结

### Claudian 的核心价值

1. **效率提升**：
   - 传统方式：手动清洗剪藏内容 → 15-30 分钟/篇
   - Claudian：自动清洗 + 提取数据 → 2-3 分钟/篇
   - **效率提升 5-10 倍**

2. **质量提升**：
   - 结构化提取：不遗漏关键数据
   - 格式统一：所有笔记遵循相同规范
   - 关键洞察：AI 能发现人容易忽略的模式

3. **工作流优化**：
   - 素材收集（Web Clipper） → 自动清洗（Claudian） → 人工审核编辑 → Wiki 条目
   - 从"收集-整理-分析-产出"全流程加速

### 适合 Claudian 的任务

**✅ 推荐使用**：
- 清洗 Web Clipper 剪藏内容
- 从长文中提取结构化数据
- 生成 Wiki 条目初稿
- 批量添加/修改 frontmatter
- 合并多个来源的信息
- 格式转换（HTML → Markdown）
- 多语言翻译

**⚠️ 谨慎使用**：
- 关键数据分析（需人工验证）
- 商业决策建议（作为参考，不能依赖）
- 敏感内容处理（隐私问题）

**❌ 不推荐**：
- 完全替代人工分析
- 处理机密信息
- 不经审核直接发布 AI 生成内容

### 学习曲线

**第一周**：熟悉基础功能
- 使用侧边栏对话
- 选中文本处理
- 简单的清洗和提取任务

**第二周**：掌握高级用法
- 批量文件处理
- 自定义提示词
- 多文件上下文整合

**第一个月后**：建立高效工作流
- 完整的素材处理流水线
- 自动化重复任务
- 质量审核标准

### 下一步

**马上开始**：
1. ✅ 确认 Claude Code CLI 已安装并登录
2. ✅ 安装 Claudian 插件
3. ✅ 配置 Claude CLI 路径
4. ✅ 测试：打开一个剪藏笔记，让 Claude 清洗内容
5. ✅ 根据效果调整提示词

**进阶学习**：
- 参考 [Dataview 文档](./dataview.md) 配合使用
- 参考 [Templater 文档](./templater.md) 创建自动化模板
- 参考 [使用技巧](../tips/usage-tips.md) 提升整体效率

**加入社区**：
- Obsidian 论坛：https://forum.obsidian.md/
- Claudian GitHub：https://github.com/chuangcaleb/obsidian-claudian
- Claude Code 文档：https://docs.anthropic.com/claude-code

祝你在 match3-wiki 项目中高效使用 Claudian！🎉
