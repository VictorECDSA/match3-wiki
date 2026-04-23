# Web Clipper 配置指南

## 安装插件

在浏览器中安装 Obsidian Web Clipper 插件：
- Chrome/Edge：https://obsidian.md/clipper
- Firefox：搜索 "Obsidian Web Clipper"
- Safari：App Store 搜索 "Obsidian Web Clipper"

## 首次配置

1. **安装后首次打开**：点击浏览器工具栏的 Obsidian 图标
2. **连接 vault**：
   - 点击"Connect to vault"
   - 选择你的 match3 vault（如 `anim-auxiliary/docs/match3/`）
   - Obsidian 桌面端会弹出授权确认，点击"Allow"
3. **验证连接**：插件界面显示 vault 名称即为成功

## 创建模板：手把手教程

根据你的截图，Web Clipper 的设置界面包含以下几个关键部分。我逐个说明怎么填：

### 1. Template 部分

#### Template name（模板名称）
- **怎么填**：给模板起个名字，用于区分不同用途
- **示例**：
  - `match3-raw`（通用素材剪藏）
  - `match3-market`（市场数据专用）
  - `match3-ua`（买量素材专用）

#### Template triggers（模板触发器）
- **怎么填**：输入网站 URL 模式，匹配时自动选择该模板
- **示例**：
  ```
  https://appmagic.rocks/*
  https://www.sensortower.com/*
  https://www.facebook.com/ads/*
  ```
- **注意**：每行一个规则，可以用 `*` 通配符
- **可以留空**：如果留空，就手动选择模板（推荐新手留空）

### 2. Location 部分

#### Behavior（行为模式）
- **默认选项**："Create new note"（创建新笔记）
- **其他选项**：
  - "Append to existing note"（追加到已有笔记）
  - "Create new note and open it"（创建后打开）
- **推荐**：保持默认 "Create new note"

#### Note name（笔记文件名）
- **怎么填**：定义保存的文件名格式，支持变量
- **你的截图**：`{{title}}` 
- **常用格式**：
  ```
  {{title}}                                → 使用网页标题
  {{date}}-{{title}}                       → 2026-04-22-Royal-Match-Report
  {{date|date:YYYYMMDD}}-{{title}}         → 20260422-Royal-Match-Report
  {{domain}}-{{date}}                      → appmagic-20260422
  ```
- **推荐**：`{{date}}-{{title}}` 方便按时间排序

#### Note location（笔记保存路径）
- **怎么填**：填写保存到 vault 的哪个文件夹
- **你的截图**：`Clippings`（这是默认值，需要修改）
- **关键注意**：这里必须填完整路径，不能只填 `raw`
- **正确填法**：
  ```
  raw/{{date|date:YYYY-MM}}              → raw/2026-04/
  raw/market                              → 固定存到 raw/market/
  raw/{{domain}}                          → raw/appmagic.rocks/
  raw/{{date|date:YYYY}}/{{date|date:MM}} → raw/2026/04/
  ```
- **常见错误**：
  - ❌ 填 `raw` → 下次打开会变回 `Clippings`
  - ✅ 填 `raw/{{date|date:YYYY-MM}}` → 自动按月分类

#### Vault（保险库）
- **怎么填**：下拉选择你已连接的 vault
- **通常**：选 "match3" 或你的 vault 名称
- **如果没有选项**：回到"首次配置"章节重新连接 vault

### 3. 实际配置示例

假设你想剪藏 AppMagic 的市场数据报告，这样填：

```
【Template 部分】
Template name:        match3-market
Template triggers:    https://appmagic.rocks/*

【Location 部分】
Behavior:             Create new note
Note name:            {{date}}-{{title}}
Note location:        raw/market/{{date|date:YYYY-MM}}
Vault:                [选择你的 vault]
```

点 Save 后,去 AppMagic 网站打开任何报告，点击浏览器的 Web Clipper 图标，就会自动：
- 选中 `match3-market` 模板
- 文件名生成如：`2026-04-22-Royal-Match-Revenue-Q1.md`
- 保存到：`raw/market/2026-04/` 文件夹

### 4. 创建多个模板

根据不同来源创建多个模板，快速归类：

| 模板名 | Template triggers | Note location | 用途 |
|--------|-------------------|---------------|------|
| `match3-market` | `https://appmagic.rocks/*`<br>`https://www.sensortower.com/*` | `raw/market/{{date\|date:YYYY-MM}}` | 市场数据 |
| `match3-ua` | `https://www.facebook.com/ads/*`<br>`https://ads.tiktok.com/*` | `raw/ua/{{date\|date:YYYY-MM}}` | 买量素材 |
| `match3-mechanics` | `*` | `raw/mechanics/{{date\|date:YYYY-MM}}` | 玩法机制 |
| `match3-general` | 留空 | `raw/{{date\|date:YYYY-MM}}` | 通用剪藏 |

这样配置后：
- 访问 AppMagic → 自动选 `match3-market` 模板
- 访问 Facebook Ad Library → 自动选 `match3-ua` 模板
- 其他网站 → 手动选 `match3-general`

## 使用流程

1. **浏览目标网页**（如 AppMagic 报告页面）
2. **点击浏览器的 Obsidian 图标**
3. **选择对应模板**（如果有 trigger 规则会自动选择）
4. **预览内容**：插件显示即将保存的 Markdown 预览
5. **点击 "Add to Obsidian"**：自动保存到指定目录

## 模板变量参考

### 基础变量
```
{{title}}               → 网页标题
{{url}}                 → 完整 URL
{{domain}}              → 域名（如 appmagic.rocks）
{{author}}              → 作者（如果网页有）
{{published}}           → 发布日期（如果网页有）
{{content}}             → 完整页面内容（自动转 Markdown）
{{selection}}           → 选中的文字
```

### 时间变量

**简单格式（使用默认）：**
```
{{date}}                → 2026-04-22（默认格式）
{{time}}                → 14:30
{{datetime}}            → 2026-04-22 14:30
```

**自定义格式（使用过滤器）：**
```
{{date|date:YYYY-MM-DD}}        → 2026-04-22
{{date|date:YYYY-MM}}           → 2026-04
{{date|date:YYYYMMDD}}          → 20260422
{{date|date:YYYY/MM/DD}}        → 2026/04/22
{{date|date:YYYY年MM月DD日}}    → 2026年04月22日
{{time|date:HH:mm}}             → 14:30
{{time|date:HH:mm:ss}}          → 14:30:45
```

**格式符号说明：**
- `YYYY` → 四位年份（2026）
- `MM` → 两位月份（01-12）
- `DD` → 两位日期（01-31）
- `HH` → 24小时制小时（00-23）
- `mm` → 分钟（00-59）
- `ss` → 秒（00-59）

## 高级配置

### 1. 自动添加 Frontmatter

Web Clipper 支持在 Note content（笔记内容）区域添加 YAML frontmatter：

在设置界面的 "Template" 部分，展开后可以看到 "Content" 编辑框，填入：

```markdown
---
source: {{url}}
date_clipped: {{date|date:YYYY-MM-DD}}
type: raw
domain: {{domain}}
tags: []
---

# {{title}}

{{content}}
```

这样剪藏的每个笔记都会自动带上元数据。

### 2. 按域名自动分类

Note location 可以这样填：
```
raw/{{domain}}/{{date|date:YYYY-MM}}
```

剪藏效果：
- appmagic.rocks 的页面 → 存到 `raw/appmagic.rocks/2026-04/`
- sensortower.com 的页面 → 存到 `raw/sensortower.com/2026-04/`

### 3. 只保存选中内容

如果某个网站页面内容太杂，可以：
1. 先在页面上选中想要的文字/图片
2. 点击 Web Clipper 图标
3. 在 Content 模板里使用 `{{selection}}` 而不是 `{{content}}`

```markdown
---
source: {{url}}
---

{{selection}}
```

### 4. 针对特定网站的自定义提取

如果是固定结构的网站（如 Facebook Ad Library），可以用 CSS 选择器：

```markdown
# {{title}}

**广告创意：**
{{selector:#ad_creative}}

**文案：**
{{selector:.ad-text}}
```

只提取指定区域，忽略页面其他内容。

## 常见问题

### Q1: 路径总是变回 Clippings？
**原因**：你可能在剪藏时手动改了路径，但那个路径不会保存到模板。

**解决**：
1. 去 Web Clipper 设置 → 编辑模板
2. 在 "Note location" 填写完整路径（如 `raw/{{date|date:YYYY-MM}}`）
3. 点 Save
4. 下次剪藏就会用这个路径

### Q2: 变量不生效（如 {{title}} 没被替换）？
**检查**：
- 大括号是英文 `{{}}` 而不是中文 `｛｛｝｝`
- 变量名拼写正确（大小写敏感）
- 日期格式变量要用过滤器：`{{date|date:YYYY-MM-DD}}` 而不是 `{{date:YYYY-MM-DD}}`
- 有些网页可能缺少 title 标签，可以加个后备：`{{title|Unknown}}`

### Q3: 剪藏的内容格式很乱？
**解决方案**：
- **简单页面**：用默认的 `{{content}}`，Web Clipper 会自动转 Markdown
- **复杂页面**：先选中想要的内容，再用 `{{selection}}`
- **剪藏后处理**：在 Obsidian 里用 Claudian 插件重新格式化

### Q4: 能否批量剪藏多个标签页？
**回答**：Web Clipper 本身不支持批量，但可以：
- 快速单个剪藏（熟练后 3-5 秒一个）
- 或用 Python 脚本批量抓取 + 转 Markdown（适合几十个以上）

### Q5: 手机能用 Web Clipper 吗？
**限制**：iOS/Android 浏览器不支持插件扩展

**替代方案**：
- **iOS**：用 Share Sheet → "Add to Obsidian"（需要 Obsidian app）
- **Android**：用 "Share to Obsidian" 功能
- **缺点**：都需要手动选文件夹，无法使用模板

### Q6: 剪藏 PDF 怎么办？
**步骤**：
1. 先下载 PDF 到本地
2. 在 Obsidian 里右键拖入 `raw/` 文件夹
3. 用 PDF++ 插件打开并标注
4. 提取标注到 Markdown 笔记

或者如果 PDF 是网页生成的（如 report），用浏览器打印功能生成更干净的版本。

### Q7: 如何避免重复剪藏？
**技巧**：
1. 在 Note name 里加上日期：`{{date}}-{{title}}`
2. Obsidian 如果检测到同名文件会自动加数字后缀
3. 或者在剪藏前先搜索 vault 看是否已存在

### Q8: 模板的 Behavior 选项怎么选？
**选项说明**：
- **Create new note**（默认）：每次剪藏创建新文件
- **Append to existing note**：追加到指定的已有笔记（适合收集同类内容）
- **Create and open**：创建后立即在 Obsidian 打开（适合需要马上编辑）

**推荐**：保持默认 "Create new note"

## 完整配置示例

### 示例 1：通用剪藏模板

```
【Template】
Template name:        match3-general
Template triggers:    留空

【Location】
Behavior:             Create new note
Note name:            {{date}}-{{title}}
Note location:        raw/{{date|date:YYYY-MM}}
Vault:                match3
```

### 示例 2：市场数据专用模板

```
【Template】
Template name:        match3-market
Template triggers:    https://appmagic.rocks/*
                      https://www.sensortower.com/*

【Location】
Behavior:             Create new note
Note name:            {{date}}-{{domain}}-{{title}}
Note location:        raw/market/{{date|date:YYYY-MM}}
Vault:                match3
```

**Content 区域（展开后填入）**：
```markdown
---
source: {{url}}
date_clipped: {{date|date:YYYY-MM-DD HH:mm}}
type: market-data
domain: {{domain}}
tags: [market, {{domain}}]
---

# {{title}}

> 来源：[{{domain}}]({{url}})
> 剪藏时间：{{date|date:YYYY年MM月DD日 HH:mm}}

{{content}}
```

### 示例 3：买量素材模板

```
【Template】
Template name:        match3-ua
Template triggers:    https://www.facebook.com/ads/*
                      https://ads.tiktok.com/*
                      https://library.tiktokbusiness.com/*

【Location】
Behavior:             Create new note
Note name:            {{date|date:YYYYMMDD}}-{{domain}}-ad
Note location:        raw/ua/{{date|date:YYYY-MM}}
Vault:                match3
```

**Content 区域**：
```markdown
---
source: {{url}}
date_clipped: {{date|date:YYYY-MM-DD}}
type: ua-creative
platform: {{domain}}
tags: [ua, creative, {{domain}}]
---

# Ad Creative - {{date|date:YYYY-MM-DD}}

**Platform**: {{domain}}
**URL**: {{url}}

---

{{content}}
```

这样配置后，访问 Facebook Ad Library 剪藏广告创意，会自动：
- 文件名：`20260422-facebook.com-ad.md`
- 保存到：`raw/ua/2026-04/`
- 自动标记为买量素材类型
