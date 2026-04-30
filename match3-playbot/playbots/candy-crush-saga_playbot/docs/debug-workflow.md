# Bot 调试流程

## 职责边界

**人只做两件事：** 连接手机、打开游戏。其余一切由 Python 处理。

Bot 必须能独立应对所有情况——不只是正在下棋时，还包括：
- 游戏刚打开、还在加载
- 在地图界面、关卡选择界面
- 关卡开始前的弹窗
- 通关/失败结算界面
- 各类广告、弹窗、权限请求
- 网络断开、游戏崩溃后重启

**AI 的职责：** 验证 Python 写得是否正确和健壮，不是替 bot 解决某一次的具体问题。

**修 bug 的原则：** 修完之后 bot 下次遇到同样或类似情况必须能自己处理，不能只是打补丁让这一次过去。每次修改都要问：*如果这个情况再发生，bot 会怎么做？*

**AI 的行动原则：发现问题 → 立刻修复 → 立刻重启 bot，不停地观察日志 → 发现下一个问题继续修复，形成闭环。除非用户主动中断，否则 AI 不能停下来等待。**

---

## 启动

```bash
cd candy-crush-saga_playbot
bash run.sh main.py --verbose
```

---

## 问题定位：看哪一层出错

| 现象 | 出错层 | 改哪里 |
|------|--------|--------|
| `screen_state=unknown` 反复出现 | 屏幕识别 | `core/ui_detector.py` HSV 阈值 |
| board 颜色打印明显错误 | 棋盘解析 | `core/color_classifier.py` / `board_geometry.py` |
| 有 board 但一直 `no move found` | 决策 | `core/solver.py` |
| tap/swap 落点偏 | 坐标 | `core/board_geometry.py` / `steps/decide.py` 里的 fallback 坐标 |
| 命令发出但手机没反应 | ADB 连接 | 检查 `adb devices`，确认 `core/adb.py` `DEVICE_SERIAL` 一致 |
| log 显示 swap 成功，但棋盘没动 | 执行时序 | `steps/execute.py` `_SLEEP_AFTER[ACT_SWAP]` 太短，动画还没结束就截图了 |
| log 显示 tap 成功，但界面没跳转 | 执行时序 | `_SLEEP_AFTER[ACT_TAP]` 太短，或坐标打在了无效区域 |
| swipe 方向反了 / 滑动距离不够 | 滑动参数 | `steps/execute.py` `duration_ms` 太短导致识别为 tap；检查 `core/board_geometry.py` 格子坐标顺序 |

---

## 单步复现

```bash
# 只截图+识别，不做任何操作
bash run.sh steps/capture.py

# 等棋盘稳定再识别
bash run.sh steps/capture.py --stable

# 把 capture 输出直接喂给 decide
bash run.sh steps/capture.py | bash run.sh steps/decide.py

# 手动执行一个动作，看手机实际反应
echo '{"action_type":"tap","tap_x":610,"tap_y":1635,"reason":"test"}' | bash run.sh steps/execute.py

# 手动执行一个 swap，确认滑动方向和格子对应是否正确
echo '{"action_type":"swap","r1":3,"c1":2,"r2":3,"c2":3,"reason":"test"}' | bash run.sh steps/execute.py
```

---

## 修改后验证

```bash
python -m py_compile src/<改过的文件>.py   # 语法检查
bash run.sh steps/capture.py               # 重新跑单步确认
```

---

## 运行时文件位置

| 文件 | 路径 |
|------|------|
| log | `workspace/bot.log` |
| 截图 | `workspace/screenshots/bot_<ts>.png` |

每个 cycle 对应一张截图，`ts` 和 `bot.log` 里该行的 `"ts"` 字段对齐。
