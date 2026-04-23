# Facebook Ad Library（Meta 广告库）

> 地址：https://www.facebook.com/ads/library
> 运营方：Meta

## 工具定位

Facebook Ad Library（Meta 广告库）是 Meta 免费提供的广告透明度工具。它开放了 Facebook、Instagram、Messenger 和 Audience Network 上所有正在投放（以及近期停投）广告的查询权限。**无需账号或登录**即可使用大部分功能。

最初为政治广告透明度要求而上线，如今已成为手机游戏行业竞品买量（UA）研究最有价值的免费工具之一。

## 工作原理

### 数据覆盖范围

广告库包含：
- 所有**正在投放**的广告
- **已停投**广告：特殊广告类别（政治/住房/就业）保留 7 年，普通广告保留 1 年
- 所有格式：图片、视频、轮播、合集、故事

**不包含**的内容：
- 普通/游戏广告的花费数据（只有特殊广告类别有）
- 非政治广告的展示量（部分地区有估算区间）
- 点击率或转化率数据
- 受众定向参数

### 搜索方式

**按广告主名称或主页名称搜索**：找到特定公司或游戏的所有广告。例如搜索"Playrix"查看 Homescapes、Gardenscapes 和 Fishdom 的所有在投广告。

**按关键词搜索**：找到文案中含特定词的广告。例如搜索"match 3"或"puzzle game"查看多个广告主使用这些词的素材。

**可用筛选项**：
- 国家（哪个国家的用户看到该广告）
- 平台（Facebook、Instagram、Messenger、Audience Network）
- 广告状态（在投、全部）
- 素材类型（图片、视频、表情包、无媒体）
- 语言（按文案语言过滤）
- 时间范围（仅特殊广告类别可用）

### 每条广告显示的信息

- 完整素材（图片/视频/轮播——视频可直接播放）
- 广告文案（标题、正文、CTA 按钮）
- 首次投放日期（广告开始投放的时间——用于判断活动启动时间）
- 在投状态
- 该广告主当前在投广告数量
- 广告投放的平台

### 特殊广告类别

政治、选举、住房、就业和信贷类广告可获取额外数据：
- 花费区间（以 $1k 为档）
- 估算曝光量区间
- 人群画像（触达用户的年龄、性别、地区分布）

手机游戏广告**不属于**特殊广告类别，因此无花费和曝光量数据。

## 使用方法

### 基础竞品研究工作流

1. 进入 https://www.facebook.com/ads/library
2. 选择国家：设为目标市场（美国、英国或核心地区）
3. 搜索竞品公司名或游戏名
4. 筛选：广告状态 = 在投
5. 按"最新"排序查看当前在投素材
6. 点击"查看广告详情"查看完整文案和首次投放日期

### 识别高效素材

高效素材通常具备以下特征：
- **持续投放时间长**（首次投放日期在几周或几个月前，仍在投放）
- **变体多**（同一创意概念略微变化文案/画面 = 在大规模 A/B 测试）
- **跨平台投放**（Facebook + Instagram = 花费有信心）

如果某个广告主的同一个视频连投 3 个月，几乎可以确定它是盈利的。

**记录一条高效素材的实际操作**：在 Facebook 广告库找到 Dream Games 的一条持续投放 8 周的 Royal Match 广告后，用 Obsidian Web Clipper 剪藏该页面，手动在笔记里补充以下字段：

```markdown
---
source: "https://www.facebook.com/ads/library/?id=XXXXXXXXXX"
date_clipped: "2025-04-10"
type: raw
advertiser: dream-games
game: royal-match
platform: [facebook, instagram]
first_run: "2025-02-14"
status: active
tags: [ua-creative, hook-puzzle, royal-match]
---

# Royal Match - 情感挫败 Hook 广告（2025-02 起投）

## 素材描述
视频广告，15 秒。
**Hook（前 3 秒）**：玩家已清空大半棋盘，剩 2 步，突然棋盘被新一排色块填满——
明显的"挫败感触发"开场，配合痛苦音效。
**主体（4–12 秒）**：切换到主角 Butler Austin 喊"Help me!"画面，
展示游戏内玩法：用道具炸弹清除一整行。
**CTA（13–15 秒）**："Can you do better? Play now"，应用商店下载按钮。

## 效果信号
- 首次投放：2025-02-14
- 当前状态：仍在投放（截至 2025-04-10，已连续 55 天）
- 平台：Facebook + Instagram（跨平台 = 高置信度）
- 变体数量：同一 Hook 有 3 个文案变体同时在投

## 归类
Hook 类型：挫败感/激怒式
情感触发点：完成欲望被阻断
玩法展示：道具系统（炸弹）
目标：解题能力召唤
```

这条笔记保存到 `raw/ua/facebook/dream-games/2025-04/` 后，运行 `/wiki:ingest` 即可将其纳入 `wiki/growth/hook-types.md` 的素材库。

### 发现品类素材趋势

1. 在广告库中关键词搜索"match 3"或"puzzle"
2. 筛选：国家 = 美国，平台 = Facebook + Instagram，状态 = 在投
3. 翻阅结果，寻找多个广告主共同出现的 Hook 类型、视觉风格、文案公式
4. 多个广告主同时使用的 Hook = 很可能是 A/B 测试结果在行业内被复制

### 追踪单个竞品

将特定主页的广告库 URL 加入书签：
```
https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=US&view_all_page_id=PAGE_ID
```

每周检查：
- 是否有新素材上线
- 哪些素材已下线（广告停投）
- UA 投入强度变化（在投广告数量增加 = 放量）

### 批量获取（API）

Meta 提供广告库 API 用于程序化访问：
- 端点：`https://graph.facebook.com/v17.0/ads_archive`
- 要求：Meta 开发者账号 + 申请通过
- 返回：含广告详情、主页信息、素材元数据的 JSON
- 有速率限制，限制程度因访问级别而异

对 match3-wiki 来说，API 访问可以批量采集素材数据进入 `raw/ua/` 供 nvk/llm-wiki 处理。

## 在 match3-wiki 项目中的作用

### 主要买量素材情报来源

PRD（§五）将 Facebook Ad Library 列为**高优先级**数据源，属于 UA 专项来源类别。它是 match3-wiki `wiki/growth/` 章节两个核心买量素材情报工具之一（另一个是 TikTok Creative Center）。

### 具体数据采集任务

**买量素材趋势页面**
每月系统性浏览头部三消广告主（Playrix、King、Scopely、Dream Games、Jam City 等）。对每个广告主：
1. 截图在投的视频/图片素材
2. 记录：Hook 类型、展示的玩法、情感角度、文案公式、CTA
3. 通过 Obsidian Web Clipper 保存至 `raw/ua/facebook/{广告主}/YYYY-MM/`
4. 运行 `/wiki:research ua-creative-trends` 将发现综合进 wiki 页面

**"当前有效 Hook"情报**
定期关键词搜索（"match 3"、"puzzle game"、"3 stars"、"blast"），识别跨广告主的素材规律。产出输入：
- `wiki/growth/hook-types.md` — 已验证有效的开场 Hook 目录
- `wiki/growth/copy-formulas.md` — 高效广告文案结构
- `wiki/growth/seasonal-trends.md` — 节假日/活动周期的素材规律

**竞品活动追踪**
监测头部广告主何时发起新活动（大量首次投放日期相同的新素材 = 新活动）。产出输入：
- `wiki/entities/{游戏名}.md` — 主要游戏的实体页面
- `wiki/market/ua-activity-log.md` — 主要买量活动时间线

**首次投放日期作为活动信号**
首次投放日期是有价值的情报。某竞品突然批量出现新素材 = 新活动或新素材测试。与 AppMagic/Sensor Tower 的下载排名变化关联分析，了解哪种素材有效。

### 对 match3-wiki 研究的局限性

- 无游戏广告花费数据——无法知道实际预算规模
- 无展示量数据——无法知道触达规模
- 只有截图无法评估素材质量（需要视频播放）
- 历史广告 1 年后过期——无法研究 2024 年以前的活动
- 关键词搜索会漏掉文案中不包含该关键词的广告
- 无法知道哪些素材带来了最多安装量或收入

### 建议采集频率

按 PRD 的持续数据刷新要求：
- **每周**：检查头部 5 家竞品的在投广告，寻找新素材
- **每月**：全面关键词搜索，挖掘跨品类趋势
- **每季度**：审查 `raw/ua/facebook/` 的完整性；触发 growth 类 wiki 页面的重新编译
