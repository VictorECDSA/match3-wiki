1. 执行摘要
本方案旨在构建一套完整的三消游戏（Match-3 Games）自动化数据采集与分析系统，核心目标包括三
个层面：本地运行三消游戏环境、AI自动游玩引擎以及结构化Gameplay数据收集。该系统将支撑关卡测
评、难度评级、玩法分析和数值评估等应用场景，并为后续的新玩法设计与关卡自动生成提供数据基
础。
当前全球三消游戏市场规模已达约128亿美元，移动平台占据72.4%的市场份额[1]。《Royal Match》、
《Candy Crush Saga》和《Homescapes》等头部产品展现了成熟的关卡设计方法论与数值体系，为本
方案的实施提供了丰富的参考范本。
本方案整合了开源项目评估、AI框架选型、数据记录规范、资料渠道汇总以及应用落地路径，形成可执
行的完整技术方案。
2. 技术实施方案
2.1 开源项目推荐
在本地搭建三消游戏环境时，选择成熟的开源框架可显著降低开发成本。根据引擎类型和功能完整度，
推荐以下项目：
2.1.1 Unity引擎项目（首选）
项目名称 核心特性 适用场
景
GitHub链接
Game-Simulation￾Match-3-Sample
Unity官方出品，含完整关卡
系统（Level_A至Level_E）和
Match3Bot
AI训练
基准环
境
https://github.com/Unity￾Technologies/GameSimulationMatch3Sample
MatchOne 基于Entitas ECS框架，逻辑与
表现层彻底解耦
高性能
二次开
发
https://github.com/sschmid/
Match-One
RoyalMatchClone 针对Royal Match玩法的练习
项目
核心消
除逻辑
参考
https://github.com/topics/
match3-game
重点推荐：Unity官方的Game-Simulation-Match-3-Sample项目支持自定义棋盘大小、目标类型
及步数限制，内置的Match3Bot可直接用于自动化测试，是进行AI训练的理想基准环境[2]。
2.1.2 Python/Gym项目（强化学习首选）
项目名称 核心特性 适用场景 GitHub链接
gym￾match3
完全兼容OpenAI Gym接口，支持自定义关
卡参数(h,w,nshapes)
RL算法训练
与对比实验
https://github.com/
kamildar/gym-match3
gym-match3提供标准的 step() 和 reset() 方法，可直接调用Stable Baselines3等库中的DQN或PPO
算法进行训练[3]。
2.1.3 Cocos与HTML5项目
项目名称 核心特性 适用场景 链接
Match3
algorithmTSCocos-creator
TypeScript编写，专
注消除算法
Cocos
Creator
集成
https://github.com/topics/match3game
Phaser 3
Match-3 Class
纯JavaScript逻辑
类，框架无关
Web快速
原型
https://emanueleferonato.com/2018/12/17/
purejavascriptclasstohandlematch3gameslike-bejeweled-ready-to-communicate-with￾your-favorite-html5-framework-phaser-3-
example-included
Candy-Crush￾Clone (KorGE)
Kotlin
Multiplatform，支
持JVM/Android/
Web
教学与跨
平台原型 https://github.com/TobseF/CandyCrushClone
2.2 AI自动游玩框架
三消游戏的AI实现已从传统的规则引擎演进至基于深度强化学习（DRL）的智能体，根据项目复杂度和训
练资源，可选择以下方案：
2.2.1 Unity ML-Agents Match-3扩展
官方提供的集成方案要求开发者继承 AbstractBoard 类，实现以下核心接口：
接口方法 功能描述
GetCellType() 返回指定位置的棋子类型
接口方法 功能描述
IsMoveValid() 验证移动是否合法，生成动作掩码
MakeMove() 执行棋子交换操作
系统通过 Match3Sensor 自动生成棋盘观测向量，通过 Match3Actuator 将离散动作映射为棋子交换。
动作屏蔽（Action Masking）确保AI不会尝试非法操作，显著加速训练收敛[4][5]。
2.2.2 gym-match3 + Stable Baselines3
适用于Python技术栈的轻量化方案，支持以下强化学习算法：
算法 特点 适用场景
DQN 离散动作空间，经典基线 简单关卡快速验证
PPO 策略梯度，稳定性强 复杂障碍物关卡
Dueling DQN 价值分解，处理稀疏奖励 高难度关卡挑战
研究表明，使用DDQN架构的智能体在处理如《Jelly Juice》等复杂三消游戏时，其胜率能达到甚至超过
普通人类玩家水平[6]。
2.2.3 传统算法（无需训练）
算法类型 实现原理 优势 局限
贪心算法 评估函数f(x)=h(x)，选择当前最优动作 计算速度快，无需训
练
无法处理复杂组
合
Always have
move
预判棋盘状态，确保始终存在可消除移
动
避免死局 策略单一
2.3 Gameplay数据记录方案
为支持AI训练和游戏平衡性分析，必须建立结构化的数据记录系统，建议采用JSON格式进行序列化存
储。
2.3.1 关键字段定义
数据类别 关键字段 数据类型 描述
棋盘布局 griddata, width, height Array/Int 二维数组记录每格颜色ID
棋子属性 celltype, specialtype Enum 区分普通棋子与特殊道具
数据类别 关键字段 数据类型 描述
玩家操作 moveindex, frompos, topos Int/Tuple 交换动作的起始坐标与方向
关卡元数据 limit_type, max_moves, target_score String/Int 关卡限制条件及过关目标
时间戳 timestamp, duration_ms Long/Int 事件发生时间与持续时长
2.3.2 遥测与回放系统
事件驱动记录：仿照Photon Quantum或Redis Streams方案，记录 playermove 、
matchstart 、 matchend 等事件流，每个事件包含时间戳和上下文数据，支持毫秒级的回放重
现[7]。
自动化导出：在Unity中，可利用 Match3Sensor 实时捕获棋盘特征向量，并结合
Match3Actuator 的动作掩码导出为训练数据集[4]。
2.4 环境搭建步骤
完整的技术实施路径分为五个阶段：
阶段一：引擎安装
安装Unity 2021.3 LTS或更高版本
备选：Cocos Creator 3.x / Python 3.8+
阶段二：项目克隆
阶段三：依赖配置
Unity方案：通过Package Manager安装 com.unity.ml-agents 及其扩展包
Python方案：安装 stablebaselines3 、 gymnasium 等依赖
阶段四：AI接口接入
实现 AbstractBoard 接口，将游戏逻辑中的棋盘数组映射给AI
调用 IsMoveValid 接口生成动作掩码
设置奖励函数：消除普通棋子+0.1，合成特殊道具+0.5，步数耗尽1.0
• 
• 
• 
• 
git clone https://github.com/Unity-Technologies/Game-Simulation-Match-3-Sample.git
# 或
pip install gymmatch3
• 
• 
• 
• 
• 
阶段五：数据自动采集
启用Match3Bot或训练好的模型进行数千次自动游玩
在 MakeMove 执行后自动将BoardState和Action写入JSON文件
使用ClickHouse等方案存储大规模遥测数据[8