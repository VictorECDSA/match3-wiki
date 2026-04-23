# Docusaurus

> 官网：https://docusaurus.io
> 维护方：Meta（Facebook）开源团队

## 工具定位

Docusaurus 是一个专为技术文档和 wiki 设计的开源静态网站生成器。它将 Markdown（及 MDX）文件转换为带有全文搜索、版本控制、国际化和清晰导航结构的生产级网站——无需自建前端，输出静态文件可部署到任何 CDN 或托管服务，零后端依赖。

在 match3-wiki 项目中，Docusaurus 是 **Phase 3** 的发布层，负责将内部 Obsidian/Markdown wiki 转变为公开可访问的知识库网站。

## 核心功能

### 三种内容类型

1. **Docs（文档）**——带版本控制、侧边栏导航的结构化文档
2. **Blog（博客）**——按时间排序的文章
3. **Pages（页面）**——独立自定义页面

### MDX——Markdown + React

Docusaurus 用 **MDX** 扩展标准 Markdown：React 组件可以直接嵌入 `.mdx` 文件。适用场景：
- 可排序的竞品对比表格
- 嵌入式图表
- 折叠章节
- 信息提示框

### 文档版本控制

支持同时维护多个文档版本，用户通过下拉菜单切换。match3-wiki 用例：同时维护"2024 年版"和"2025 年版"市场数据页面。

### Algolia 搜索

Docusaurus 内置 Algolia DocSearch 集成（对开源和公开文档免费）：
- 全文搜索覆盖所有页面
- 快捷键（Ctrl+K / Cmd+K）
- 按分类过滤

### 部署

构建输出到 `build/` 静态目录：
- **GitHub Pages**：`docusaurus deploy` 一键完成
- **Vercel / Netlify**：连接仓库后自动检测并构建
- **任意 CDN**：上传 `build/` 文件夹

## 使用方法

### 初始化项目

```bash
npx create-docusaurus@latest match3-wiki classic
cd match3-wiki
npm start
```

### 从 Obsidian/nvk-llm-wiki 迁移

wiki Markdown 文件需要少量调整：
1. 添加 `sidebar_position` frontmatter 控制排序
2. 将 Obsidian 的 `[[wikilink]]` 转换为标准 Markdown `[文字](./路径.md)` 链接
3. 将 Obsidian 特有的标注语法替换为 Docusaurus 的提示框语法

### match3-wiki 配置示例

```js
// docusaurus.config.js
module.exports = {
  title: 'Match-3 Wiki',
  tagline: '三消游戏行业从业者知识库',
  url: 'https://match3.wiki',
  baseUrl: '/',

  themeConfig: {
    navbar: {
      items: [
        { to: '/docs/mechanics', label: '玩法机制', position: 'left' },
        { to: '/docs/market', label: '市场数据', position: 'left' },
        { to: '/docs/growth', label: '增长与买量', position: 'left' },
      ],
    },
    algolia: {
      appId: 'YOUR_APP_ID',
      apiKey: 'YOUR_SEARCH_KEY',
      indexName: 'match3wiki',
    },
  },
};
```

## 在 match3-wiki 中的作用

### Phase 3：公开知识库发布层

PRD 将 Docusaurus 定为 **Phase 3 发布层**（第 17 周起）。完整工作流：

```
wiki/（nvk/llm-wiki 编译出的 Markdown 文件）
  ↓  迁移脚本（wikilink 转换）
docs/（Docusaurus 兼容 Markdown）
  ↓  npm run build
build/（静态 HTML/CSS/JS）
  ↓  部署到 Vercel / GitHub Pages
https://match3.wiki（公开网站）
```

### 为什么选 Docusaurus

| 特性 | Docusaurus | Obsidian Publish | GitBook |
|---|---|---|---|
| 全文搜索 | Algolia（免费） | 内置 | 内置 |
| 自定义域名 | 免费 | $8/月 | 付费 |
| MDX / React 组件 | 支持 | 不支持 | 不支持 |
| 版本控制 | 内置 | 不支持 | 付费 |
| 开源 | 是 | 否 | 否 |
| 自托管 | 支持 | 不支持 | 付费 |

### match3-wiki 具体优势

- **结构化导航**：侧边栏 + Algolia 搜索
- **市场数据版本控制**：快照历史数据
- **嵌入式数据表格**：MDX 组件实现可排序列
- **通过 PR 协同编辑**："编辑此页"链接指向 GitHub
- **SEO 带来自然流量**：静态 HTML 可被搜索引擎爬取

## 局限性

- 需要构建步骤——不支持编辑时实时预览
- 从 Obsidian 格式迁移时 wikilink 转换增加了过渡摩擦
- MDX 组件的高级定制需要 React 知识
- Algolia DocSearch 需要提交网站 URL 审核
- 不适合需要保持内部私密的内容
