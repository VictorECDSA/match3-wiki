# Candy Crush Saga 关卡设计分析文章合集

本目录收集了关于 **Candy Crush Saga / 三消游戏关卡设计** 的中英文分析文章，从设计哲学、Blocker 框架、难度调控、AI 辅助、UX/Booster、再到地形数学指标，各篇侧重不同。

> 抓取日期：2026-04-29
> 所有文章保留了来源链接、作者、发布日期，便于回溯。

---

## 文章索引

### 一、关卡设计哲学与方法论

| # | 文件 | 作者/来源 | 核心主题 |
|---|------|-----------|----------|
| 01 | [01_match-3-level-design-study_fran-ruiz.md](./01_match-3-level-design-study_fran-ruiz.md) | Fran Ruiz / Medium | CCS 关卡设计三原则（Hook、≤4 元素、不依赖 booster），并以 Easy/Medium/Hard 三关原型示范 |
| 03 | [03_anas-shaer_level-6000-design.md](./03_anas-shaer_level-6000-design.md) | Anas Shaer（CCS 关卡设计师）| 设计 Level 6000 里程碑关卡的思考：庆祝感、爆发节奏；Color Cannon 功能整合 |
| 13 | [13_gamedeveloper_processes-behind-king-candy-crush.md](./13_gamedeveloper_processes-behind-king-candy-crush.md) | Christian Nutt / Game Developer 2013 | King 工作室文化、内部众包、关卡难度取舍、玩家流失的接受 |

### 二、Blocker / 障碍物体系（最核心议题）

| # | 文件 | 作者/来源 | 核心主题 |
|---|------|-----------|----------|
| 02 | [02_alex-braysy_level-designer-portfolio.md](./02_alex-braysy_level-designer-portfolio.md) | Alex Bräysy（前 King 设计师）| Sour Skull 设计案例；APS/EGP 双轴关卡分类法（Puzzle / Explosive / Endurance）；用方差而非平均值评估 RNG blocker |
| 04 | [04_pocketgamer_crafting-difficulty-blockers-ai.md](./04_pocketgamer_crafting-difficulty-blockers-ai.md) | PocketGamer / John Davies 访谈 | "复杂度阶梯"概念；现代 blocker 设计原则；新 blocker Mal-O-Matic 案例 |
| 10 | [10_sohu_king-blocker-framework-gdc.md](./10_sohu_king-blocker-framework-gdc.md) | Lucien Chen GDC 演讲 / 搜狐 | King 的 16 特征 × 4 类别 Blocker Framework；雷达图分析；最常见 5 特征及其原因 |

### 三、难度曲线与 AI 辅助

| # | 文件 | 作者/来源 | 核心主题 |
|---|------|-----------|----------|
| 07 | [07_neurohive_ai-helped-king-13755-levels.md](./07_neurohive_ai-helped-king-13755-levels.md) | Neurohive / Sahar Asadi 访谈 | King 用 bot 测试关卡，开发速度 +50%、人工修复 -95%；AI 是助手而非替代 |
| 09 | [09_gamelook_king-pm-20000-levels.md](./09_gamelook_king-pm-20000-levels.md) | GameLook / John Davies 访谈（中文版）| 2 万关时代的难度平衡；难度刻意波动而非递增；AI 工具应用 |

### 四、UX / Booster 设计

| # | 文件 | 作者/来源 | 核心主题 |
|---|------|-----------|----------|
| 05 | [05_pocketgamer_ux-boosters-deceptively-complex.md](./05_pocketgamer_ux-boosters-deceptively-complex.md) | PocketGamer / Andrea Serfaty 访谈 | "看似简单实则复杂"的 booster 设计；Super Charger / Super Colour Bomb；Fish 3.0 改造 |
| 06 | [06_yu-kai-chou_octalysis-why-addicting.md](./06_yu-kai-chou_octalysis-why-addicting.md) | Yu-kai Chou | 用 Octalysis 八角框架解析 CCS 上瘾的 8 大核心驱动力 |

### 五、量化分析与机制分类（理论基础）

| # | 文件 | 作者/来源 | 核心主题 |
|---|------|-----------|----------|
| 08 | [08_match-game-mechanics-exhaustive-survey.md](./08_match-game-mechanics-exhaustive-survey.md) | Jonathan Bailey / Game Developer 2015 | Match-3 机制完整分类学：拓扑、块结构、生成、玩家行为、匹配条件、奖励、结束条件 |
| 11 | [11_gcores_match3-design-elements.md](./11_gcores_match3-design-elements.md) | 游戏虾 / 机核 GCORES 2024 | 三消元素手感（前摇/释放/后摇）、道具生成与组合、Royal Match 双色消的商业价值 |
| 12 | [12_shouyoujz_terrain-design-tutorial.md](./12_shouyoujz_terrain-design-tutorial.md) | 游戏矩阵 | 关卡基本地形的"平均连通数"量化指标；"二宽"高难度设计法；斜向掉落带来的动态复杂度 |

### 六、历史参考

| # | 文件 | 作者/来源 | 核心主题 |
|---|------|-----------|----------|
| 14 | [14_sohu_2013_ccs-level-types.md](./14_sohu_2013_ccs-level-types.md) | 任玩堂 / 搜狐 2013 | CCS 早期 4 种关卡类型（限次积分 / 果冻 / 运送果子 / 限时积分），可作为机制演化的时间锚点 |

---

## 阅读建议路线

- **快速建立全局观**：08 → 10 → 04
- **学习 King 内部方法论**：02 → 03 → 04 → 09 → 13
- **理解上瘾与商业化**：06 → 05 → 11
- **学习量化与可执行的关卡难度调控**：12 → 02 → 10
- **想动手做关卡**：01 → 12 → 10 → 04

---

## 抓取失败/未收录的潜在好文

下列文章在抓取时受反爬限制（Cloudflare / 知乎 / 今日头条 / WordPress.com 验证），暂未收录，可日后手动补充：

- mobilegamer.biz — *How King defines a 'good' Candy Crush Saga level – and why it constantly prunes the bad ones*（GDC 报道，玩家技能分层与难度权重）
- mobilegamer.biz — *How King balances human and AI-powered design in Candy Crush Saga*
- 知乎专栏 — *Candy Crush Saga（糖果传奇）—— 关卡类型* (zhuanlan.zhihu.com/p/344649269)
- 知乎专栏 — *BI 研究院：如何做三消游戏的策略性研究* (zhuanlan.zhihu.com/p/23771694)
- 知乎专栏 — *Candy Crush Saga 关卡间节奏分析（一/二/三）* (zhuanlan.zhihu.com/p/507489363)
- IEEE CoG 2024 论文 — *The Royal Crush: Analysis of Match-3 Mechanics*（PDF）
