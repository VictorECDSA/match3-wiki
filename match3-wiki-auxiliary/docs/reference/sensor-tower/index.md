# Sensor Tower

> 官网：https://sensortower.com
> 状态：企业级平台（2023 年收购 data.ai，2025 年完成统一数据管线）

## 工具定位

Sensor Tower 是业界领先的企业级移动市场情报平台。它提供了在第一方发行商数据之外，最全面、最准确的应用商店下载量、收入、用户行为、ASO 数据和广告情报估算。

2023 年收购 data.ai（前身为 App Annie）、2025 年完成统一数据管线后，Sensor Tower 将行业内两个最大的移动情报数据集合二为一，在面板覆盖度和广告情报两个维度上均达到业内最高水平。

对 match3-wiki 项目，Sensor Tower 是市场数据验证、竞品广告素材研究和 ASO 研究的黄金标准来源。

## 工作原理

### 数据采集方式

Sensor Tower 采用多重叠加的数据采集方式：

**应用商店面板网络**：数百万选择加入的用户通过 SDK 集成和授权应用分享匿名使用数据。并购 data.ai 后，这是行业内规模最大的面板之一。

**应用商店抓取和监控**：持续追踪全球主要应用商店的排名、搜索结果、编辑推荐、评分和应用元数据。

**广告网络合作**：广告情报数据来自与广告网络的合作伙伴关系和直接集成，不只是素材抓取。这使实际广告花费模式的覆盖更准确。

**发行商合作**：部分发行商直接共享数据，换取品类基准访问权限。

**统计建模与校准**：面板数据通过专有模型外推至全市场，参照 App Store 财务披露和谷歌公开的汇总指标进行校准。

### 核心产品模块

**App Intelligence（应用情报）**
- 按日/周/月/国家的下载量和收入
- DAU/MAU/互动指标
- 特定市场的人群画像（年龄、性别）
- 分组留存率（第 1、7、14、30、60、90 天）
- 会话时长和频率数据（Usage Intelligence 模块）

**Store Intelligence（商店情报）**
- ASO 关键词排名（应用在哪些关键词上排名靠前）
- 关键词搜索量估算
- 品类排名历史
- 编辑推荐历史（App Store 编辑精选、Google Play 编辑精选）
- 评论挖掘和情感分析

**Ad Intelligence（广告情报）**
- 跨平台竞品广告素材：Facebook、Instagram、Google UAC、ironSource、AppLovin、Unity Ads
- 各素材的估算展示量（不只是"有没有"，而是"跑了多少量"）
- 广告主和广告网络的花费估算
- 规模扩张中的素材格式趋势数据
- 素材下载功能（可直接查看和导出竞品视频/图片广告）

**Usage Intelligence（使用情报）**
- 会话时长分布
- 功能参与度（通过问卷和面板获取）
- 跨应用使用模式（游戏 X 的用户还使用哪些其他应用）

### 企业定价

Sensor Tower 是企业工具：
- 不公开标价
- 市场估算：完整访问约 $25,000–40,000/年
- 支持按模块单独订购（如仅 Ad Intelligence + Store Intelligence）
- 免费版：功能极为有限——应用概览 + 基础估算
- 面向合格企业提供试用账号

这一定价使 Sensor Tower 主要面向有资金的游戏工作室、发行商、风险投资机构和研究机构。对独立研究者或小团队，AppMagic 是更实际的替代方案。

### 并购 data.ai 后（2025 年）

2025 年统一数据管线完成的影响：
- 纳入 data.ai 更早期的历史数据（覆盖时间早于原 Sensor Tower）
- 更好的面板覆盖（data.ai 在日本、韩国、东南亚更强的市场）
- 统一 API，整合原两套分离系统
- 合并后的广告主档案覆盖两个数据集

## 使用方法

### 应用表现研究

1. 搜索游戏名称
2. 进入游戏资料页
3. 重点面板：
   - **下载量**：趋势、国家分布、iOS vs. Android
   - **收入**：月度/季度趋势、国家分布
   - **留存**：分组留存率 D1/D7/D30（如可访问）
   - **排名**：品类排名历史、营销活动期间的排名峰值
   - **编辑推荐**：何时获得 App Store/Google Play 编辑推荐？对下载量有多大影响？

### 广告情报研究

1. 进入 Ad Intelligence 模块
2. 搜索发行商/游戏
3. 按广告网络筛选：Facebook、Google 或"所有网络"
4. 对每条素材：
   - 在 Sensor Tower 内直接查看/播放
   - 查看估算展示量区间
   - 查看首次/最后出现日期
   - 下载素材文件
5. 按"展示量"排序优先查看花费最高的素材

### 品类级竞品分析

1. 进入 Top Charts
2. 筛选：品类 = Puzzle（休闲游戏），国家 = 美国
3. 按收入排序（最近 30 天）
4. 导出前 30 款游戏排名列表
5. 点击每款游戏查看收入分布和买量素材策略

### ASO 研究

1. 搜索竞品游戏
2. 打开 Store Intelligence 标签页
3. 查看：
   - 应用排名靠前的关键词（前 10–50）
   - 每个关键词的搜索量
   - 哪些关键词排名 #1–3？哪些在 #10 以后？
4. 用这些关键词指导自己的 ASO 策略或找到竞争较小的空缺

### 导出和 API

Sensor Tower 提供：
- 大多数数据视图支持 CSV 导出
- 格式规范的 Excel 报告
- REST API（企业版）：时间序列数据、应用档案、关键词排名、素材元数据
- 定时数据推送（按计划自动发送报告到邮件）

## 在 match3-wiki 项目中的作用

### 黄金标准验证层

PRD（§五）将 Sensor Tower 与 AppMagic 并列为**高优先级**数据源。考虑到 Sensor Tower 的企业级定价，match3-wiki 的建议用法是：

**主力**：AppMagic 用于日常市场数据（更实惠）
**验证**：Sensor Tower 免费版或定期访问用于高价值数据点的核实
**广告情报**：如果有访问权限，Sensor Tower 明显优于 AppMagic（综合来看是最好的广告素材研究工具）

如果团队有企业版 Sensor Tower 访问权限，它可以成为大多数市场数据需求的单一来源。

### 具体数据输入

**市场基准（精度高于 AppMagic）**：
- `wiki/market/match3-revenue-benchmarks.md` — 经验证的三消品类收入层级
- `wiki/market/top-grossing-games.md` — 更准确的国家级数据
- `wiki/market/china-market.md` — 并购后中国数据更好

**广告素材情报（Sensor Tower 独特优势）**：
- `wiki/growth/top-creatives-by-impressions.md` — 不只是"投了什么"，而是"大规模投了什么"
- `wiki/growth/ad-network-strategy.md` — 哪些游戏侧重 Facebook vs. Google vs. ironSource
- `wiki/growth/creative-performance-signals.md` — 用展示量作为素材成功的代理指标

**留存和互动基准**：
- `wiki/mechanics/retention-benchmarks.md` — 三消各层级 D1/D7/D30/D60/D90 基准
- `wiki/production/engagement-targets.md` — 会话时长和频率基准

**ASO 情报**：
- `wiki/growth/aso-keyword-strategy.md` — 头部三消游戏优化哪些关键词？
- `wiki/growth/app-store-featuring.md` — 三消游戏如何获得编辑推荐？影响有多大？

**主要游戏实体页面**：
每个 `wiki/entities/{游戏}.md` 页面都受益于 Sensor Tower 全面的生命周期数据——比 AppMagic 更准确，尤其是亚洲市场。

### 没有完整访问权限时的价值

即使只有免费版或定期访问，Sensor Tower 也能提供：
1. **交叉验证**：将 AppMagic 的关键数字与 Sensor Tower 免费版估算对比。大幅差异意味着某个来源的数据质量问题。
2. **广告情报**：免费版展示部分素材（筛选有限）——比什么都没有强，可了解竞品 Meta/Google 策略。
3. **Trending**：免费版的"热门应用"板块展示快速上升的产品，无需订阅。

### 采集工作流

如有 Sensor Tower 访问权限：
```
季度深度调研：
1. 导出按收入排名的前 30 款三消游戏（Puzzle 品类，美国）→ raw/market/sensortower/YYYY-Q{N}/rankings.csv
2. 拉取前 5 名竞品广告素材集 → raw/ua/sensortower/{游戏}/YYYY-Q{N}/
3. 导出前 10 款游戏关键词排名 → raw/market/sensortower/YYYY-Q{N}/aso-keywords.csv
4. 运行 /wiki:ingest 处理新 raw 文件
5. 运行 /wiki:research market-benchmarks, ua-ad-intelligence, aso-strategy
```

如只有免费版：
```
每月抽查：
1. 查看热门三消应用动态
2. 记录主要产品的重大排名变化
3. 抓取可见的竞品广告素材
4. 将观察记录至 raw/market/sensortower/notes/YYYY-MM.md
```

### Sensor Tower vs. AppMagic 决策矩阵

| 问题 | 用 AppMagic | 用 Sensor Tower |
|---|---|---|
| "三消前 20 款游戏按收入怎么排？" | ✓ 够用 | ✓ 精度更高 |
| "Dream Games 在 Facebook 上投什么广告？" | 有限 | ✓ 更好 |
| "Royal Match 的 D30 留存是多少？" | ✓ 有 | ✓ 有 |
| "中国三消市场表现如何？" | 有限 | ✓ 并购后更好 |
| "King 在哪些 ASO 关键词上排名？" | ✓ 有 | ✓ 覆盖关键词更多 |
| "Playrix Q3 在谷歌上花了多少钱？" | 无 | 估算值（企业版） |
| 可用预算 | $300–500/月 | $2,000+/月 |

## 局限性

- 企业定价使其无法在没有公司/机构预算的情况下访问
- 数据仍是估算值，非审计数字
- 广告情报覆盖 Facebook/Google 较强，新兴 DSP 覆盖较薄
- 中国市场数据并购后改善，但仍不如第一方数据可靠
- 免费版基本是营销工具，无法满足真实研究需求
- data.ai 并购意味着部分历史数据集存在方法论不一致问题（合并前 vs. 合并后）
- 无 TikTok 广告情报覆盖（TikTok 不向第三方大规模共享素材数据）
