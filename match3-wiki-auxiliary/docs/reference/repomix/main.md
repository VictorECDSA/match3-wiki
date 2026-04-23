# Repomix

> 仓库：https://github.com/yamadashy/repomix
> 网页版：https://repomix.com

## 工具定位

Repomix 是一个 TypeScript/Node.js 工具，将整个代码仓库（或任意目录）打包成单个 AI 优化文件。打包后的文件设计用于直接投入 LLM 上下文窗口——让模型在一次输入中获得对整个项目的完整、结构化视图，无需分批检索或搜索。

核心使用场景：**"我想让 Claude 理解我的整个项目，而不只是我手动粘贴的几个文件。"**

在 match3-wiki 中，Repomix 的作用是将整个 wiki 语料打包，支持对知识库的全局分析和质量审查。

## 工作原理

### 打包流程

Repomix 遍历目标目录，生成包含以下内容的单一输出文件：
1. 完整项目结构的目录树
2. 每个文件的内容，用清晰的分隔符隔开
3. Token 用量估算（基于 tiktoken）
4. 可选的安全扫描结果

输出格式针对 LLM 解析优化，用 XML 标签（默认）、Markdown 标题或 JSON 结构分隔每个文件段。

### 输出格式

| 格式 | 适用场景 |
|---|---|
| XML（默认） | 最适合 Claude——XML 标签给出清晰的文件边界 |
| Markdown | 人可读，适合文档用途 |
| JSON | 程序化处理，结构化访问 |

### Tree-sitter 压缩

对代码文件，Repomix 可选用 tree-sitter 只提取结构骨架（函数签名、类定义、引用）而不是完整文件内容，在保留语义结构的同时减少 token 用量。对 Markdown/文本文件（如 wiki），完整内容即结构，tree-sitter 压缩帮助不大。

### 安全扫描（Secretlint）

打包前对所有文件运行 Secretlint。发现密钥、token、凭证等敏感信息时，Repomix 会警告并可阻止打包操作，防止敏感信息意外进入 LLM 上下文。

### Token 计数

打包完成后输出 token 总数，让你立即知道是否能装进目标模型的上下文窗口：
- Claude 3.5 Sonnet：200k tokens
- GPT-4o：128k tokens

超出则需要缩小范围（排除目录、使用压缩或分段打包）。

### .repomixignore

类似 `.gitignore`，列出不打包的模式：
```
raw/          # 排除原始素材（太大，wiki 分析不需要）
history/      # 排除审计日志
*.pdf         # 排除二进制文件
node_modules/
```

## 使用方法

### 安装

```bash
# 全局安装（推荐频繁使用时）
npm install -g repomix

# 或不安装直接运行
npx repomix
```

### 基本用法

```bash
# 打包当前目录
repomix

# 打包指定目录
repomix --path ./wiki/

# 指定输出文件
repomix --path ./wiki/ --output wiki-pack.xml

# Markdown 格式输出
repomix --path ./wiki/ --style markdown --output wiki-pack.md

# 只查看 token 数量，不生成文件
repomix --path ./wiki/ --token-count-only
```

### 选择性打包

```bash
# 只包含特定模式
repomix --path ./wiki/ --include "**/*.md"

# 排除特定模式
repomix --path ./wiki/ --exclude "raw/**,history/**"
```

### 远程仓库打包

```bash
# 直接打包 GitHub 仓库（无需本地克隆）
repomix --remote https://github.com/nvk/llm-wiki
```

### VS Code 插件

Repomix VS Code 插件在任何文件或文件夹上添加右键菜单"用 Repomix 打包"，输出到可配置位置。适合开发中快速临时打包。

### 网页版

[repomix.com](https://repomix.com) 支持在浏览器中打包公开 GitHub 仓库，无需安装。粘贴仓库 URL，配置选项，下载打包文件。适合一次性分析外部仓库。

### 配置文件

项目根目录的 `repomix.config.json`：
```json
{
  "output": {
    "filePath": "repomix-output.xml",
    "style": "xml",
    "showLineNumbers": true
  },
  "ignore": {
    "useGitignore": true,
    "customPatterns": ["raw/", "history/"]
  },
  "security": {
    "enableSecretlint": true
  }
}
```

## 在 match3-wiki 项目中的作用

### 全局 Wiki 分析

match3-wiki 最终会包含 100+ 个 Markdown 页面，分布在多个主题聚类中。当需要 Claude 对**整个知识库**进行推理时——而不只是某一页——需要一次性投入所有内容。Repomix 让这件事变得可行：

```bash
# 打包整个 wiki 供 Claude 分析
repomix --path ./wiki/ --output wiki-pack.xml --exclude "raw/**"
```

然后将 `wiki-pack.xml` 粘贴进 Claude 会话或作为项目文件使用。

### 具体使用场景

**覆盖盲点分析**
打包 wiki 后问 Claude："请审查这个三消游戏知识库。哪些重要主题已有覆盖？哪些重要主题缺失？各页面之间有没有矛盾？"

**跨页一致性检查**
打包 wiki 后问 Claude："请检查这些 wiki 页面的不一致之处——冲突的数据、对同一机制的不同叫法、被更新内容推翻的旧数据。"

**Phase 3 发布前质量审查**
在发布到 Docusaurus 之前，打包 wiki 跑一次预发布质量审查："这些是我即将发布的 wiki 页面。请检查：需要引用来源的事实声明、内容过短的页面、可能不适合公开的内容。"

**Token 预算规划**
定期运行 `repomix --token-count-only` 追踪 wiki 增长情况。当打包超过 150k tokens 时，是剪除冗余内容或按领域分段打包（机制包、市场包等）的信号。

**理解 nvk/llm-wiki 工具本身**
用 Repomix 打包 nvk/llm-wiki 仓库后喂给 Claude，快速理解编译器的工作方式、局限性以及如何为 match3 用例配置 `CLAUDE.md`。

### 工作流集成

在 Makefile 或 npm scripts 中添加：
```bash
# 打包 wiki 供分析（排除原始素材）
pack-wiki:
    repomix --path ./wiki/ --output ./tmp/wiki-pack.xml --exclude "raw/**,history/**"
    repomix --path ./wiki/ --token-count-only
```

### 阶段质量检查点

PRD 质量门（§八）要求定期审查 wiki 完整性。Repomix 让 Claude 能在单个文件中获取完整 wiki 上下文，支持这些审查：
- Phase 1 检查点（第 8 周）：打包 wiki，对照 PRD 主题清单审查
- Phase 2 检查点（第 16 周）：打包扩展后的 wiki，验证所有实体页面是否有交叉链接
- Phase 3 前：最终质量打包，发布前审查

## 局限性

- 大型 wiki（200+ 页）可能超出 200k token 上下文窗口，需要选择性打包
- 二进制文件（图片、PDF）无法有意义地打包——只能按路径引用
- Tree-sitter 压缩对代码最有效，对 Markdown 内容价值有限
- 远程仓库打包只支持公开 GitHub 仓库，私有仓库需先本地克隆
- 输出是静态快照——每次 wiki 重大更新后需要重新打包
