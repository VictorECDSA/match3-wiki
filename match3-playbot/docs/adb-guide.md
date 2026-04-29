# ADB 调试完全指南：安装、配置与常用功能

本指南涵盖从零开始安装 ADB、配置手机（以红米 / HyperOS 为例）到常用命令的完整流程，作为 `match3-playbot` 项目"获取手机画面 + 操作手机"环节的参考。

---

## 一、安装 ADB（电脑端）

ADB（Android Debug Bridge）是 Google 提供的命令行工具，用于与安卓设备通信。

### macOS

```bash
# 使用 Homebrew 安装
brew install android-platform-tools

# 验证安装
adb version
```

### Windows

1. 下载 Google 官方 Platform Tools：<https://developer.android.com/studio/releases/platform-tools>
2. 解压到任意目录（例如 `C:\platform-tools`）
3. 将此目录添加到系统环境变量 `Path` 中
4. 打开 `cmd` 或 PowerShell 验证：

```cmd
adb version
```

### Linux (Debian / Ubuntu)

```bash
sudo apt update
sudo apt install adb
adb version
```

---

## 二、手机端准备（红米 Note 14 Pro / HyperOS）

### 1. 开启开发者模式

- 进入 **设置 → 我的设备 → 全部参数与信息**
- 连续点击 **HyperOS 版本** 7 次，直到提示"您现在处于开发者模式"

### 2. 开启 USB 调试及安全设置

- 返回 **设置 → 更多设置 → 开发者选项**
- 开启顶部 **开发者选项** 总开关
- 向下滑动，开启：
  - ✅ **USB 调试**
  - ✅ **USB 调试（安全设置）** —— **关键！** 允许模拟点击 / 输入
  - （可选）✅ **USB 安装**：方便直接安装应用
  - （可选）✅ **指针位置**：调试触摸坐标时非常有用

### 3. 授权电脑连接

1. 用数据线连接手机与电脑
2. 手机弹出 **"允许 USB 调试吗？"** 对话框，勾选 **"始终允许"**，点击"确定"
3. 在电脑终端执行：

```bash
adb devices
```

设备状态应显示为 `device`，而非 `unauthorized` 或 `offline`。

---

## 三、常见权限问题及解决

### 问题：执行 `adb shell input tap` 报错 `SecurityException: INJECT_EVENTS permission`

| 原因 | 解决方法 |
|---|---|
| 未开启"USB 调试（安全设置）" | 进入开发者选项开启该项 |
| MIUI / HyperOS 优化干扰（最常见） | 开发者选项 → 关闭 **"启用 MIUI 优化"** → 重启手机；若问题解决，可再次开启并重启 |
| 手机未授权此电脑 | 重新插拔数据线，务必点击弹窗 **"始终允许"** |
| 服务未刷新 | `adb kill-server` 后再 `adb devices` 重启 ADB 服务，必要时重启手机 |

### 其他常见状态

| `adb devices` 显示 | 含义 | 处理 |
|---|---|---|
| `unauthorized` | 未授权 | 在手机上点击"允许 USB 调试"对话框 |
| `offline` | 连接异常 | 拔插数据线 / `adb kill-server` |
| `no permissions` (Linux) | 用户无权限访问 USB | 配置 udev 规则或用 `sudo` |
| 列表为空 | 未识别设备 | 检查驱动 / 数据线是否支持数据传输 |

---

## 四、ADB 核心功能与常用命令

ADB 就像一座桥梁，让你在电脑上通过命令行操作安卓设备。

### 4.1 设备与连接

| 命令 | 用法示例 | 效果 |
|---|---|---|
| `adb devices` | `adb devices` | 列出已连接的设备及状态 |
| `adb -s <serial> ...` | `adb -s 1234abcd shell` | 多设备时指定目标设备 |
| `adb kill-server` / `adb start-server` | `adb kill-server` | 重启 ADB 守护进程 |
| `adb tcpip <port>` | `adb tcpip 5555` | 切换到 TCP/IP 模式（需先用 USB 连接） |
| `adb connect` | `adb connect 192.168.1.100:5555` | 通过 Wi-Fi 连接设备 |
| `adb disconnect` | `adb disconnect 192.168.1.100:5555` | 断开 Wi-Fi 连接 |
| `adb root` | `adb root` | 以 root 重启 adbd（需设备已 root） |

#### Android 11+ 无线调试（推荐）

Android 11 起官方支持无需 USB 的无线配对：

1. 手机开发者选项 → **无线调试** → 开启
2. 进入 **"使用配对码配对设备"**，会显示一个 IP:端口 与 6 位配对码
3. 电脑执行：

```bash
adb pair <手机IP>:<配对端口>
# 输入手机上显示的 6 位配对码

adb connect <手机IP>:<连接端口>
adb devices
```

### 4.2 应用管理

| 命令 | 用法示例 | 效果 |
|---|---|---|
| `adb install` | `adb install app.apk` | 安装应用 |
| `adb install -r` | `adb install -r app.apk` | 覆盖安装，保留数据 |
| `adb uninstall` | `adb uninstall com.example.app` | 卸载应用 |
| `adb shell pm list packages` | `adb shell pm list packages \| grep wechat` | 列出已安装包名 |
| `adb shell pm clear` | `adb shell pm clear com.example.app` | 清除应用数据 |
| `adb shell am start` | `adb shell am start -n com.pkg/.MainActivity` | 启动指定 Activity |
| `adb shell am force-stop` | `adb shell am force-stop com.example.app` | 强制停止应用 |

### 4.3 文件操作

| 命令 | 用法示例 | 效果 |
|---|---|---|
| `adb push` | `adb push local.txt /sdcard/` | 文件从电脑推送到手机 |
| `adb pull` | `adb pull /sdcard/remote.txt ./` | 文件从手机拉取到电脑 |

### 4.4 屏幕交互（自动玩游戏核心）

| 命令 | 用法示例 | 效果 |
|---|---|---|
| `adb shell input tap` | `adb shell input tap 500 1000` | 模拟点击坐标 (x, y) |
| `adb shell input swipe` | `adb shell input swipe 100 500 100 100 300` | 滑动（最后一个参数为时长 ms） |
| `adb shell input text` | `adb shell input text "Hello"` | 在焦点输入框输入文本（不支持空格 / 中文，需用 `%s` 转义或借助 ADBKeyBoard） |
| `adb shell input keyevent` | `adb shell input keyevent KEYCODE_HOME` | 模拟按键（HOME / BACK / POWER 等） |

#### 常用 keyevent

| KeyCode | 作用 |
|---|---|
| `KEYCODE_HOME` (3) | 回到桌面 |
| `KEYCODE_BACK` (4) | 返回 |
| `KEYCODE_POWER` (26) | 电源键 |
| `KEYCODE_MENU` (82) | 菜单 |
| `KEYCODE_APP_SWITCH` (187) | 多任务 |

> **三指匹配类游戏提示**：`input swipe` 的"时长"参数会显著影响识别为"滑动"还是"长按"。三消游戏交换通常用较短时长（如 100 ms）；过短可能被识别为点击，过长会触发长按或拖动。

### 4.5 截图与录屏（获取画面核心）

| 命令 | 用法示例 | 效果 |
|---|---|---|
| `adb exec-out screencap -p` | `adb exec-out screencap -p > screen.png` | **推荐**：直接输出 PNG 到 stdout |
| `adb shell screencap -p /sdcard/s.png` + `adb pull` | 见下方 | 先存到手机再拉回电脑 |
| `adb shell screenrecord` | `adb shell screenrecord /sdcard/demo.mp4` | 录屏（Ctrl+C 停止，最长 3 分钟） |

```bash
# 方式一：一行直出（最快）
adb exec-out screencap -p > screen.png

# 方式二：先存后拉（兼容性最好）
adb shell screencap -p /sdcard/screen.png
adb pull /sdcard/screen.png ./
adb shell rm /sdcard/screen.png
```

> **⚠️ 重要踩坑**：在 Windows 的 `cmd` 下使用 `adb shell screencap -p > screen.png` 会因 `\r\n` 转换损坏 PNG。**务必使用 `adb exec-out screencap -p`**（macOS / Linux 也建议统一用此方式，性能更好）。

### 4.6 系统信息与调试

| 命令 | 用法示例 | 效果 |
|---|---|---|
| `adb shell wm size` | `adb shell wm size` | 屏幕分辨率 |
| `adb shell wm density` | `adb shell wm density` | 屏幕 DPI |
| `adb shell dumpsys battery` | `adb shell dumpsys battery` | 电池信息 |
| `adb shell dumpsys window` | `adb shell dumpsys window \| grep mCurrentFocus` | 当前焦点窗口（定位 Activity） |
| `adb shell dumpsys activity activities` | 同左 | Activity 栈信息 |
| `adb logcat` | `adb logcat -s TAG_NAME` | 实时日志（可按 TAG 过滤） |
| `adb shell getprop` | `adb shell getprop ro.product.model` | 系统属性 |
| `adb shell uiautomator dump` | `adb shell uiautomator dump /sdcard/ui.xml` | 导出当前界面 UI 层级 XML，用于元素定位 |

### 4.7 进入交互式 Shell

```bash
adb shell
# 进入后是一个标准 Linux Shell，可执行 ls / cat / top 等
```

---

## 五、面向"自动玩游戏机器人"的最佳实践

针对 `match3-playbot` 这类自动化场景的建议：

### 5.1 截图链路

- 使用 `adb exec-out screencap -p` 配合 Python 的 `subprocess` 直接获取字节流，再用 PIL / OpenCV 解码，避免落盘 I/O：

  ```python
  # import subprocess
  # from PIL import Image
  # from io import BytesIO
  #
  # raw = subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
  # img = Image.open(BytesIO(raw))
  ```

- 单次截图耗时约 100~300 ms（取决于设备 / 分辨率）。如需更高帧率，可考虑 `scrcpy` 推流方案或 `minicap`。

### 5.2 操作链路

- 单次 `adb shell input tap` 启动 JVM 开销较大（每次约 100~300 ms）。**高频操作请使用持久化 shell**：

  ```python
  # proc = subprocess.Popen(['adb', 'shell'], stdin=subprocess.PIPE, ...)
  # proc.stdin.write(b'input tap 500 1000\n')
  ```

- 或考虑 [scrcpy](https://github.com/Genymobile/scrcpy) 的控制通道、[uiautomator2](https://github.com/openatx/uiautomator2)、[ADBKeyBoard](https://github.com/senzhk/ADBKeyBoard)（中文输入）。

### 5.3 坐标稳定性

- 不同手机分辨率不同，应记录 `wm size` 输出，将 `tap` 坐标按比例换算，而不是写死。
- 系统手势区域（屏幕底部上滑回桌面）会拦截 input，敏感区域避免触发。

### 5.4 避免被打断

- 操作前可执行：

  ```bash
  adb shell settings put global heads_up_notifications_enabled 0   # 关通知横幅（部分系统有效）
  adb shell svc power stayon usb                                    # USB 连接时常亮
  ```

- 运行结束恢复：

  ```bash
  adb shell svc power stayon false
  ```

### 5.5 多设备

- 多设备时务必带 `-s <serial>`，可通过 `adb devices` 获取序列号。
- 在脚本中将 `adb -s <serial>` 封装成函数 / 常量，避免散落的硬编码。

---

## 六、参考链接

- 官方 Platform Tools：<https://developer.android.com/studio/releases/platform-tools>
- ADB 命令官方文档：<https://developer.android.com/tools/adb>
- scrcpy（高性能投屏 / 控制）：<https://github.com/Genymobile/scrcpy>
- uiautomator2（Python ADB 高级封装）：<https://github.com/openatx/uiautomator2>
