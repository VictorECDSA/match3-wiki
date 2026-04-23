# Obsidian 安装与配置

## 快速开始

### 第一步：下载并创建 Vault

从 https://obsidian.md 下载安装包（macOS/Windows/Linux 均有）。个人使用永久免费，商用需一次性购买商业许可。

安装后点击"Create new vault"，**把 vault 路径直接指向你的 match3-wiki 项目根目录**（不是新建一个空文件夹，而是选择已有的 `anim-auxiliary/docs/match3/` 目录）。Obsidian 会读取这个目录里的所有 `.md` 文件，不会创建任何额外的数据库文件，只会在目录下生成一个 `.obsidian/` 配置文件夹。

### 第二步：创建文件夹结构

在 Obsidian 左侧文件树右键"New Folder"，按 match3-wiki PRD 的分类体系创建以下目录结构：

```
match3/
├── raw/                    ← 原始素材（Web Clipper 剪藏到这里）
│   ├── market/
│   │   ├── appmagic/
│   │   │   └── 2025-04/
│   │   └── sensortower/
│   ├── ua/
│   │   ├── facebook/
│   │   │   └── playrix/
│   │   └── tiktok/
│   └── mechanics/
├── wiki/                   ← nvk/llm-wiki 编译产出（只读，不手动编辑）
│   ├── market/
│   ├── mechanics/
│   ├── growth/
│   ├── entities/
│   └── production/
├── history/                ← nvk/llm-wiki 审计日志
└── CLAUDE.md               ← schema 配置文件
```

### 第三步：安装基础插件

依次进入 `Settings（齿轮图标）→ Community plugins → Turn on community plugins → Browse`。

**必装插件（先安装这 3 个）：**

1. **Dataview**：搜索安装，用于对笔记元数据做类 SQL 查询
2. **Templater**：搜索安装，在 Settings → Templater 设置 Template folder 为 `_templates/`
3. **Obsidian Git**：搜索安装，设置 Auto pull 10分钟，Auto push 30分钟

安装完这 3 个后，继续配置 Web Clipper。

到这里，基础配置完成！你可以开始收集素材了。

## 推荐插件配置

参见 [插件配置文档](../plugins/recommended.md)。
