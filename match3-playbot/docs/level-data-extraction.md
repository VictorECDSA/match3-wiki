# 三消游戏关卡设计数据自动化提取方案

本文针对 Candy Crush Saga 等三消游戏，系统梳理关卡设计数据的自动化提取方法，涵盖原理、工具链、操作步骤与数据结构设计，供 `match3-playbot` 项目参考。

---

## 一、目标：关卡设计数据包含哪些内容

在开始之前，先明确"关卡设计数据"的范畴：

| 数据类别 | 具体字段示例 |
|---|---|
| **棋盘结构** | 行列数、每格是否可用（格子形状/遮罩）|
| **初始棋子布局** | 每格初始棋子颜色/类型（是否预设，还是随机）|
| **障碍物与特殊格** | 果冻层数、奶油块、冰块、传送门位置、锁链、巧克力等 |
| **关卡目标** | 达成条件类型（消除 N 个某色、收集特定物品、撑过 N 步等）、目标数量 |
| **步数 / 时间限制** | 最大步数或倒计时秒数 |
| **可用道具** | 本关预置的 Booster 种类与数量 |
| **评分阈值** | 一星 / 二星 / 三星 对应分数 |
| **特殊机制** | 传送带方向、重力方向、糖果生成规则 |

---

## 二、四种提取方案概览

| 方案 | 原理 | 难度 | 需要 Root | 实时性 | 精度 | 适合场景 |
|---|---|---|---|---|---|---|
| **A. 截图 + CV 分析** | 截取游戏画面，用计算机视觉识别棋盘状态 | ★★☆ | 否 | 实时 | 中（依赖识别质量） | 已进入关卡、通用于任何三消 |
| **B. APK 逆向工程** | 反编译 APK 直接读取内嵌关卡定义文件 | ★★★ | 否 | 离线 | 高 | 关卡数据内嵌于 APK 的游戏 |
| **C. 网络流量拦截** | 代理截获游戏从服务器下载的关卡数据包 | ★★☆ | 否 | 在线 | 高 | 关卡从云端动态下载的游戏 |
| **D. 应用数据目录读取** | 直接读取手机上游戏的本地缓存 / 数据库 | ★★☆ | 是 | 离线 | 高 | 已 Root 设备，数据已缓存到本地 |

> **推荐组合**：对 Candy Crush Saga，建议优先尝试 **方案 C（流量拦截）** 获取结构化关卡定义，辅以 **方案 A（CV）** 提取已进入关卡的实时棋盘状态。

---

## 三、方案 A：截图 + 计算机视觉分析

### 3.1 原理

通过 ADB 持续截取游戏画面，使用 OpenCV / YOLO 等 CV 工具识别：
- 棋盘区域的边界框
- 每个格子的位置（网格分割）
- 每格内的棋子颜色、类型（是否为特殊棋子）
- 障碍物类型（通过图像模板匹配或分类器）
- HUD 区域的目标文字（步数、目标数量，用 OCR 读取）

### 3.2 ADB 截图

```bash
# 安装 ADB（macOS）
brew install android-platform-tools

# 验证连接
adb devices
# 期望输出：<serial>  device

# 获取屏幕分辨率（建议提前记录，用于坐标换算）
adb shell wm size
# 示例输出：Physical size: 1080x2400

# 方式一：直接输出到标准流（推荐，无磁盘 I/O）
adb exec-out screencap -p > screen.png

# 方式二：先存到手机再拉取（兼容性最好）
adb shell screencap -p /sdcard/screen.png
adb pull /sdcard/screen.png ./
adb shell rm /sdcard/screen.png
```

> ⚠️ Windows cmd 下不要用 `adb shell screencap -p > screen.png`，会因 `\r\n` 转换损坏 PNG，务必用 `adb exec-out screencap -p`。

Python 中直接获取图像对象（无落盘）：

```python
# import subprocess
# from PIL import Image
# from io import BytesIO
#
# raw = subprocess.check_output(['adb', 'exec-out', 'screencap', '-p'])
# img = Image.open(BytesIO(raw))
```

### 3.3 棋盘识别流程

```
截图
  │
  ▼
定位棋盘区域
  ├─ 方法1：固定坐标（手动标注一次，按分辨率比例换算）
  └─ 方法2：模板匹配棋盘边框图案，或检测均匀网格结构
  │
  ▼
网格分割（计算每格中心坐标）
  │
  ▼
逐格分类
  ├─ 颜色识别：取格子中心区域的主色（HSV 空间聚类）
  ├─ 特殊棋子：模板匹配（条纹糖/包装糖/彩虹糖图标）
  └─ 障碍物：分类器（需预先标注样本）
  │
  ▼
OCR 读取 HUD
  ├─ 裁剪步数 / 目标数量区域
  └─ 使用 Tesseract 或 EasyOCR 识别数字
  │
  ▼
输出结构化数据（JSON）
```

### 3.4 关键工具

```bash
# Python 依赖（需手动安装，确认后执行）
# pip install opencv-python pillow pytesseract easyocr numpy
```

| 工具 | 用途 |
|---|---|
| `opencv-python` | 图像处理、模板匹配、颜色分析 |
| `Pillow (PIL)` | 图像解码、裁剪 |
| `pytesseract` / `EasyOCR` | OCR 读取步数、目标数字 |
| `numpy` | 数组运算 |
| `ultralytics (YOLOv8)` | 若需训练目标检测器识别特殊棋子 |

### 3.5 优缺点

**优点**：无需 root、无需逆向，对所有三消游戏通用
**缺点**：
- 需要手动进入关卡后才能截图，无法批量离线提取
- 识别精度受游戏动画、特效、分辨率影响
- 需要为每款游戏单独调参（棋盘区域、格子大小、颜色映射）

---

## 四、方案 B：APK 逆向工程

### 4.1 原理

部分三消游戏将关卡定义内嵌在 APK 的 `assets/` 或 `res/raw/` 目录中，格式通常为：
- JSON / 压缩 JSON
- Protocol Buffers（protobuf）
- 自定义二进制格式
- SQLite 数据库

反编译 APK 即可直接拿到所有关卡定义，无需运行游戏。

### 4.2 从手机提取 APK

```bash
# 查找目标游戏包名
adb shell pm list packages | grep -i candy
# 示例输出：package:com.king.candycrushsaga

# 查找 APK 路径
adb shell pm path com.king.candycrushsaga
# 示例输出：package:/data/app/~~xxxxx==/com.king.candycrushsaga-xxxxx==/base.apk

# 拉取 APK 到本地
adb pull /data/app/~~xxxxx==/com.king.candycrushsaga-xxxxx==/base.apk ./candycrush.apk
```

### 4.3 反编译工具

**工具一：apktool**（提取资源文件，decode assets）

```bash
# 安装（macOS）
brew install apktool

# 反编译（-s 跳过 dex 反编译，只提取资源）
apktool d -s candycrush.apk -o candycrush_decoded/

# 查看 assets 目录
ls candycrush_decoded/assets/
```

**工具二：jadx**（反编译 Java / Kotlin 代码，用于理解数据格式）

```bash
# 安装（macOS）
brew install jadx

# 反编译为 Java 源码
jadx candycrush.apk -d candycrush_src/

# 搜索关卡加载逻辑
grep -r "level" candycrush_src/ --include="*.java" -l
```

**工具三：直接解压 APK**（APK 本质上是 ZIP）

```bash
unzip candycrush.apk -d candycrush_zip/
ls candycrush_zip/assets/
```

### 4.4 识别关卡数据格式

进入 `assets/` 后，常见的关卡数据特征：

| 文件特征 | 可能格式 | 处理方式 |
|---|---|---|
| 文件名含 `level_` / `stage_` / `map_` | JSON / Binary | 直接用文本编辑器查看或 `file` 命令检测 |
| 文件头为 `{` 或 `[` | JSON | 直接解析 |
| 文件头为 `PK` | ZIP 内嵌 ZIP | 再次解压 |
| 二进制乱码但有规律重复结构 | Protobuf / 自定义二进制 | 用 protoc / 010 Editor 分析 |
| 扩展名 `.db` / `.sqlite` | SQLite | `sqlite3 file.db .tables` |
| 扩展名 `.lua` | Lua 脚本 | 直接阅读或运行 |

**Candy Crush Saga 特别说明**：
- 早期版本关卡以 XML 嵌在 assets 中
- 现代版本大量关卡通过 OTA 更新（方案 C 更合适）
- 可在 `assets/` 中搜索 `.json` / `.pb` / `.bytes` 后缀文件

### 4.5 解析 Protobuf（如适用）

```bash
# 若文件是 protobuf 且没有 .proto 定义，用 protoc 暴力解码查看字段编号
protoc --decode_raw < level_001.pb

# 示例输出（字段编号: 值）：
# 1: 9        <- 可能是列数
# 2: 9        <- 可能是行数
# 3 {         <- 可能是棋子列表
#   1: 1
#   2: 3
# }
```

### 4.6 优缺点

**优点**：可批量离线提取全部关卡，数据完整精确
**缺点**：
- 部分游戏代码混淆严重，数据格式难以解读
- 违反游戏 ToS（仅供研究学习）
- 现代游戏越来越多地将关卡下载到服务器（方案 C 更合适）

---

## 五、方案 C：网络流量拦截（推荐）

### 5.1 原理

许多三消游戏启动关卡时会从服务器下载最新关卡定义（支持 OTA 热更新）。通过在手机和网络之间插入 HTTPS 代理，可以捕获这些请求及响应中的结构化关卡数据。

```
手机 → [HTTPS 代理（电脑）] → 游戏服务器
                ↓
        捕获关卡数据响应
```

### 5.2 工具：mitmproxy

**电脑端安装**

```bash
# macOS
brew install mitmproxy

# 验证
mitmproxy --version
```

**建立代理并安装证书**

```bash
# 1. 启动 mitmproxy（默认监听 8080 端口）
mitmproxy

# 或使用 mitmweb（浏览器图形界面，更直观）
mitmweb --web-port 8081
```

```bash
# 2. 查看电脑 IP（手机和电脑须在同一 Wi-Fi）
ipconfig getifaddr en0   # macOS
# 示例：192.168.1.100
```

手机端配置代理：
- 进入 **Wi-Fi 设置 → 长按当前网络 → 修改网络 → 高级 → 代理 → 手动**
- 主机名：`192.168.1.100`（电脑 IP）
- 端口：`8080`

安装 mitmproxy 根证书（拦截 HTTPS 必须）：
- 手机浏览器打开 `http://mitm.it`
- 下载并安装 Android 证书
- 进入 **设置 → 安全 → 加密与凭据 → 安装证书 → CA 证书**，选择刚下载的证书

> ⚠️ Android 7+ 默认不信任用户安装的 CA 证书用于应用流量。需要应用的 `network_security_config.xml` 允许用户 CA，或使用 Root + Magisk 将证书装入系统证书库（见下方）。

**Root 设备将证书装入系统库（Android 7+）**

```bash
# 获取证书 hash（在电脑上执行）
openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem | head -1
# 示例输出：c8750f0d

# 重命名并推送到系统证书目录
cp ~/.mitmproxy/mitmproxy-ca-cert.pem c8750f0d.0
adb push c8750f0d.0 /sdcard/

# 以 root 权限移动到系统证书目录
adb shell
su
mount -o rw,remount /system
cp /sdcard/c8750f0d.0 /system/etc/security/cacerts/
chmod 644 /system/etc/security/cacerts/c8750f0d.0
# 重启手机
```

### 5.3 使用 mitmproxy 脚本自动保存关卡数据

创建过滤脚本 `capture_levels.py`（电脑上运行）：

```python
# mitmproxy addon script: capture_levels.py
# Run with: mitmproxy -s capture_levels.py
#
# import json, os
# from mitmproxy import http
#
# SAVE_DIR = "./captured_levels"
# os.makedirs(SAVE_DIR, exist_ok=True)
#
# TARGET_KEYWORDS = ["level", "stage", "episode", "map"]
#
# def response(flow: http.HTTPFlow) -> None:
#     url = flow.request.pretty_url.lower()
#     if not any(kw in url for kw in TARGET_KEYWORDS):
#         return
#     content_type = flow.response.headers.get("content-type", "")
#     if "json" in content_type or "protobuf" in content_type or "octet" in content_type:
#         filename = url.split("/")[-1].split("?")[0] or "response"
#         filepath = os.path.join(SAVE_DIR, f"{filename}_{flow.id[:8]}.bin")
#         with open(filepath, "wb") as f:
#             f.write(flow.response.content)
#         print(f"[SAVED] {url} -> {filepath}")
```

```bash
# 启动带脚本的 mitmproxy
mitmproxy -s capture_levels.py
```

### 5.4 分析捕获的数据

```bash
# 查看捕获的文件
ls ./captured_levels/

# 尝试解析 JSON
python3 -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1])), indent=2))" level_xxx.bin

# 若为 protobuf，用 protoc 尝试解码
protoc --decode_raw < level_xxx.bin
```

### 5.5 优缺点

**优点**：
- 获取的数据与游戏服务器实际下发完全一致
- 无需 root（证书问题另解决）
- 可捕获最新关卡（OTA 更新）

**缺点**：
- HTTPS 证书 pinning（SSL Pinning）可能阻止拦截（需 Frida 等工具绕过）
- 需要逐关卡触发网络请求，无法一次性批量获取
- 网络环境配置相对复杂

---

## 六、方案 D：应用数据目录读取（需 Root）

### 6.1 原理

游戏运行后会将关卡数据缓存到 `/data/data/<包名>/` 目录。Root 后可直接访问该目录，读取数据库、JSON 缓存文件等。

### 6.2 操作步骤

```bash
# 确认包名
adb shell pm list packages | grep candy
# com.king.candycrushsaga

# 进入 root shell
adb shell
su

# 查看应用数据目录结构
ls /data/data/com.king.candycrushsaga/

# 常见子目录
# databases/  - SQLite 数据库
# files/      - 应用内部文件（关卡缓存常在此处）
# cache/      - 临时缓存
# shared_prefs/ - SharedPreferences XML（存进度、配置）
```

```bash
# 将整个数据目录拉到电脑（在 root shell 中先 cp 到 sdcard）
cp -r /data/data/com.king.candycrushsaga/files /sdcard/ccs_files/
cp -r /data/data/com.king.candycrushsaga/databases /sdcard/ccs_db/

# 退出 shell，拉取文件
exit
exit
adb pull /sdcard/ccs_files ./
adb pull /sdcard/ccs_db ./
```

```bash
# 查看 SQLite 数据库表结构
sqlite3 ccs_db/some_database.db ".tables"
sqlite3 ccs_db/some_database.db ".schema"
sqlite3 ccs_db/some_database.db "SELECT * FROM levels LIMIT 5;"
```

### 6.3 优缺点

**优点**：数据最完整，可获取本地已缓存的所有关卡
**缺点**：必须 Root，可能导致游戏反作弊检测触发（部分游戏检测 root 后拒绝运行）

---

## 七、绕过 SSL Pinning（方案 C 的补充）

当游戏实现了证书固定（SSL Pinning），mitmproxy 会收到 SSL 握手失败错误。此时需要使用 Frida 在运行时 Hook 绕过：

### 7.1 安装 Frida

```bash
# 电脑端
pip install frida-tools

# 手机端（需 root 或用 frida-gadget）
# 1. 查看设备 CPU 架构
adb shell getprop ro.product.cpu.abi
# 示例：arm64-v8a

# 2. 从 https://github.com/frida/frida/releases 下载对应架构的 frida-server
# 文件名格式：frida-server-<version>-android-arm64.xz

# 3. 解压并推送到手机
xz -d frida-server-*.xz
adb push frida-server /data/local/tmp/
adb shell chmod +x /data/local/tmp/frida-server

# 4. 启动 frida-server（需 root）
adb shell su -c '/data/local/tmp/frida-server &'
```

### 7.2 使用 objection 自动绕过 SSL Pinning

```bash
# 安装 objection
pip install objection

# 启动目标应用并自动 patch SSL Pinning
objection --gadget com.king.candycrushsaga explore
# 在 objection shell 中执行：
# android sslpinning disable
```

或直接用 frida 脚本：

```bash
# 使用社区维护的通用 SSL Pinning 绕过脚本
frida -U -f com.king.candycrushsaga -l ssl_pinning_bypass.js --no-pause
# ssl_pinning_bypass.js 可从 https://codeshare.frida.re/@akabe1/frida-multiple-unpinning/ 获取
```

---

## 八、统一数据结构设计

无论使用哪种方案，建议将提取结果统一输出为以下 JSON 格式：

```json
{
  "meta": {
    "game": "candy_crush_saga",
    "level_id": 1,
    "episode": 1,
    "extraction_method": "cv|apk|network|filesystem",
    "extracted_at": "2026-01-01T00:00:00Z",
    "source_resolution": "1080x2400"
  },
  "board": {
    "rows": 9,
    "cols": 9,
    "grid": [
      ["R", "G", "B", "Y", "P", "O", "R", "G", "B"],
      ["G", "W", "R", "P", "_", "P", "R", "W", "G"]
    ],
    "cell_types": {
      "R": "red_candy",
      "G": "green_candy",
      "B": "blue_candy",
      "Y": "yellow_candy",
      "P": "purple_candy",
      "O": "orange_candy",
      "W": "wrapped_candy",
      "_": "empty"
    }
  },
  "obstacles": [
    {"type": "jelly", "row": 0, "col": 0, "layers": 2},
    {"type": "chocolate", "row": 3, "col": 4},
    {"type": "licorice", "row": 5, "col": 2}
  ],
  "objectives": [
    {"type": "collect_ingredient", "item": "cherry", "count": 2},
    {"type": "reach_score", "score": 10000}
  ],
  "constraints": {
    "moves": 25,
    "time_seconds": null
  },
  "scoring": {
    "one_star": 5000,
    "two_star": 10000,
    "three_star": 20000
  },
  "boosters": [
    {"type": "lollipop_hammer", "count": 1}
  ],
  "special_mechanics": {
    "gravity_direction": "down",
    "portals": [
      {"from": {"row": 0, "col": 0}, "to": {"row": 8, "col": 8}}
    ],
    "conveyor_belts": []
  }
}
```

---

## 九、推荐工具链汇总

### 电脑端依赖

| 工具 | 安装方式 | 用途 |
|---|---|---|
| `adb` | `brew install android-platform-tools` | 手机截图、文件读写 |
| `apktool` | `brew install apktool` | APK 反编译 |
| `jadx` | `brew install jadx` | Java 代码反编译 |
| `mitmproxy` | `brew install mitmproxy` | HTTPS 流量拦截 |
| `frida-tools` | `pip install frida-tools` | 运行时 Hook |
| `objection` | `pip install objection` | SSL Pinning 绕过 |
| `sqlite3` | 系统自带 | 数据库查看 |
| `protoc` | `brew install protobuf` | Protobuf 解码 |

### Python 库依赖

| 库 | 安装方式 | 用途 |
|---|---|---|
| `opencv-python` | `pip install opencv-python` | CV 图像处理 |
| `Pillow` | `pip install Pillow` | 图像读取 |
| `numpy` | `pip install numpy` | 数组运算 |
| `pytesseract` | `pip install pytesseract` | OCR |
| `easyocr` | `pip install easyocr` | OCR（效果更好）|
| `mitmproxy` | `pip install mitmproxy` | 代理脚本 |
| `protobuf` | `pip install protobuf` | Protobuf 解析 |

---

## 十、方案选型决策树

```
目标：提取三消游戏关卡设计数据
        │
        ▼
设备是否已 Root？
  ├─ 是 → 方案 D（读取应用数据目录）最直接
  │         + 方案 C（流量拦截）补充在线关卡
  │
  └─ 否 ─→ 关卡数据是否从网络动态下载？
              ├─ 是 → 方案 C（流量拦截）
              │       └─ 游戏有 SSL Pinning？
              │           ├─ 是 → 需 Frida 绕过（实际需要 Root 或测试版 APK）
              │           └─ 否 → 直接用 mitmproxy 捕获
              │
              └─ 否（数据内嵌于 APK）→ 方案 B（APK 逆向）
                        │
                        ▼
              需要实时棋盘状态？
                  └─ 是 → 叠加方案 A（截图 + CV）
```

---

## 十一、针对 Candy Crush Saga 的具体记录

实际执行结果（APK 路径、SQLite 结构、22,205 关数据、tileMap 解码验证等）已整理到独立文档：

- [candy-crush-saga_levels/data-extraction.md](./candy-crush-saga_levels/data-extraction.md) — 提取过程与产物清单
- [candy-crush-saga_levels/level-format.md](./candy-crush-saga_levels/level-format.md) — JSON 字段说明、tileMap 编码规则、item ID 对照表

---

## 十二、参考资源

- ADB 官方文档：<https://developer.android.com/tools/adb>
- apktool：<https://apktool.org>
- jadx：<https://github.com/skylot/jadx>
- mitmproxy：<https://mitmproxy.org>
- Frida：<https://frida.re>
- objection：<https://github.com/sensepost/objection>
- Frida SSL Pinning Bypass 脚本：<https://codeshare.frida.re/@akabe1/frida-multiple-unpinning/>
- scrcpy（高性能投屏，CV 实时分析可配合使用）：<https://github.com/Genymobile/scrcpy>
- uiautomator2（Python ADB 高级封装）：<https://github.com/openatx/uiautomator2>
