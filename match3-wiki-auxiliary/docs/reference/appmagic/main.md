# AppMagic

> 官网：https://appmagic.rocks

## 工具定位

AppMagic 是一个手机市场情报平台，追踪 iOS App Store 和 Google Play 上的应用表现数据，包括下载量、收入、DAU/MAU、留存曲线、ASO 关键词排名和广告素材情报。相比 Sensor Tower 等企业级竞品，AppMagic 定价亲民得多，同时覆盖了大多数研究团队的核心需求。

AppMagic 是 match3-wiki 市场情报数据的主力来源，主要提供三消品类的收入基准、下载趋势、地区表现和品类排名数据。

## 核心功能

### 数据维度

- **下载量**：按国家的日/周/月下载量，iOS vs. Android 分类
- **收入**：估算净收入（应用商店抽成后），IAP vs. 广告收入分类
- **DAU / MAU**：日活跃用户和月活跃用户估算
- **留存曲线**：第 1 天、第 7 天、第 30 天留存率估算（**稀缺特性**）
- **排名**：实时和历史 Top Charts（总榜、品类榜）
- **ASO 情报**：关键词排名、流量估算、评论分析
- **广告素材情报**：Apple Search Ads 和 Google UAC 渠道投放素材

### 定价

- **免费版**：有限访问——Top Charts、基础应用概览
- **入门版**：约 $99–199/月
- **专业版**：完整访问，包含留存数据、高级筛选、API（约 $299–499/月）
- **企业版**：自定义定价，批量数据导出

## 使用场景

### 查找头部三消游戏

1. 进入 https://appmagic.rocks
2. 导航至 Top Charts
3. 筛选：品类 = Puzzle，国家 = 美国
4. 按收入排序（最近 30 天）
5. 导出前 20 名结果为 CSV

### 分析单款游戏表现

以 Royal Match 为例，记录关键指标：
- 月收入估算：~$85M–$95M
- 月下载量：~25M–30M
- Revenue/Download：~$3.2（高，说明货币化能力强）
- D1/D7/D30 留存：45%/22%/12%
- IAP 占比：~95%

### 三消品类竞品基准分析

采集头部 15–20 款三消游戏数据建立基准表，每季度更新。

## 在 match3-wiki 中的作用

### 主要市场数据来源

PRD 将 AppMagic 与 Sensor Tower 并列为**高优先级**数据源。AppMagic 是更易入手的起点——比 Sensor Tower 便宜得多，能满足 wiki 大部分市场数据需求。

### 具体数据输入

- `wiki/market/match3-revenue-benchmarks.md` — 按收入层级分类的品类基准
- `wiki/market/top-grossing-games.md` — 排名列表
- `wiki/entities/royal-match.md` — 各游戏表现数据
- `wiki/mechanics/retention-benchmarks.md` — 留存基准（**AppMagic 独有优势**）
- `wiki/growth/monetization-model-comparison.md` — IAP vs. 广告收入占比

### 采集工作流

```
每月数据采集：
1. 导出按收入排名的前 20 款三消游戏 → raw/market/appmagic/YYYY-MM/top-games.csv
2. 导出前 5 款游戏留存数据 → raw/market/appmagic/YYYY-MM/retention.csv
3. 导出地区分布 → raw/market/appmagic/YYYY-MM/regional.csv
4. 运行 /wiki:ingest 处理新 raw 文件
5. 运行 /wiki:research market-benchmarks 更新市场 wiki 页面
```

## 局限性

- 所有数据均为估算值，非精确数字
- 中国市场数据有限
- 广告素材情报弱于 Facebook Ad Library 或 TikTok Creative Center
- 免费版功能太有限
- 没有实时数据——通常延迟 24–48 小时更新
