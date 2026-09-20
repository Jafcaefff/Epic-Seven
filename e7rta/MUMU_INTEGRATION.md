# MuMu 模拟器接入指南

> 把 BP 推荐引擎挂到 MuMu 模拟器上：截图 → 识别敌方阵容 → POST /api/draft/quick → 渲染悬浮窗推荐。

---

## 整体架构

```
┌──────────────┐    截图     ┌─────────────┐   识别  ┌─────────────┐
│ MuMu 模拟器   │ ─────────→ │  截图模块    │ ─────→ │  OCR 识别    │
│ (BP 选人界面) │            │  (ADB/dxcam) │        │  (英雄图标)  │
└──────────────┘            └─────────────┘        └──────┬──────┘
                                                          │ code list
                                                          ▼
                              ┌─────────────────────────────────────┐
                              │  POST /api/draft/quick              │
                              │  {enemy_picks: ["c5154", "c2124"]}  │
                              └──────────────────┬──────────────────┘
                                                 │ recommendations
                                                 ▼
                              ┌─────────────────────────────────────┐
                              │  悬浮窗渲染（5 个英雄卡）           │
                              │  显示「推荐指数」「vs 敌方 N 人 WR」 │
                              └─────────────────────────────────────┘
```

---

## 接入步骤

### 1. 启动 BP 推荐服务（已完成）

```bash
cd E:\第七史诗查询工具\e7rta
C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe server.py
# 监听 0.0.0.0:8799（MuMu 本机访问用 127.0.0.1:8799）
# 局域网访问要改 server.py 的 HTTPServer(('0.0.0.0', 8799), ...)
```

### 2. 截图模块

MuMu 截图两种方式：

**方式 A：ADB 截图**（推荐，延迟低 ~50ms）
```python
import subprocess
from PIL import Image
import io

def capture():
    out = subprocess.check_output(['adb', '-s', '127.0.0.1:7555', 'exec-out', 'screencap', '-p'])
    return Image.open(io.BytesIO(out))
```

**方式 B：Windows GDI 截图**（需要 PyWin32）
```python
import win32gui, win32ui, win32con
# 找到 MuMu 窗口句柄，截屏
```

### 3. 识别敌方阵容

**E7 选人界面**：每方 5 个英雄图标，从左到右排列。每个图标下方有名字。

**OCR 思路**：
- **方案 A（推荐）**：模板匹配。用 `fetch_images.py` 抓的本地图片 `/static/img/heroes/<code>.png` 与截图每个图标位置做 OpenCV `cv2.matchTemplate`。命中率 95%+。
- **方案 B**：OCR 文字。Tesseract / PaddleOCR 识别英雄名字，映射回 code。慢且依赖字体。

**模板匹配代码骨架**：
```python
import cv2, numpy as np
from pathlib import Path

# 加载模板图（按 code 索引）
templates = {}
for png in Path('static/img/heroes').glob('*.png'):
    code = png.stem  # "c5154"
    img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    img = cv2.resize(img, (64, 64))  # 统一大小
    templates[code] = img

# 在截图中查找
def find_heroes(screen_img, slot_rects):
    """slot_rects: 5 个英雄槽位 [(x,y,w,h), ...]"""
    found = []
    for rect in slot_rects:
        roi = screen_img[rect[1]:rect[1]+rect[3], rect[0]:rect[0]+rect[2]]
        best_code, best_score = None, 0
        for code, tmpl in templates.items():
            res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
            score = res.max()
            if score > best_score:
                best_score = score
                best_code = code
        if best_score > 0.7:  # 阈值
            found.append(best_code)
    return found
```

### 4. 调用推荐 API

```python
import requests

def recommend(enemy_codes, top=10):
    r = requests.post('http://127.0.0.1:8799/api/draft/quick',
        json={'enemy_picks': enemy_codes, 'top': top},
        timeout=2)
    return r.json()
```

### 5. 渲染悬浮窗

PyQt5 / Tkinter 都可以。**关键点**：
- 半透明置顶窗口（`setWindowOpacity(0.9)` + `WindowStaysOnTopHint`）
- 实时刷新（每 1-2 秒一次，或敌方阵容变化时）
- 显示「推荐指数」+ 「vs 敌方 N 人 X% · NNN 场」让玩家知道推荐依据

```python
from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtCore import Qt

class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.9)
        self.setFixedSize(400, 600)
        self.label = QLabel('加载中…', self)
        # 样式：黑色背景，黄色文字
        self.setStyleSheet('background: rgba(0,0,0,0.85); color: #ffd700; border-radius: 10px;')

    def update_recs(self, recs):
        lines = []
        for r in recs[:10]:
            lu = r.get('lineup')
            counter = f"阵容{lu['size']}人 {lu['wr']:.1f}%" if lu else f"对{r['counter_score']:.1f}%"
            lines.append(f"{r['name']:6s} 推{r['score']*100:.0f}  {counter}")
        self.label.setText('\n'.join(lines))
```

---

## 完整循环伪代码

```python
import time, requests
from overlay import Overlay

ov = Overlay()
ov.show()

last_codes = None
while True:
    screen = capture()                              # 截图
    codes = find_heroes(screen, ENEMY_SLOT_RECTS)  # OCR
    if codes and codes != last_codes:               # 阵容变了才调
        recs = recommend(codes, top=10)
        ov.update_recs(recs['recommendations'])
        last_codes = codes
    time.sleep(1.5)                                 # 每 1.5s 循环
```

---

## 已知坑点

1. **截图频率**：别太高，1-2s 一次足够（敌方选人动作通常 3-5 秒一次）。API 响应 35ms 不是瓶颈，截图 + 模板匹配才是。
2. **图标分辨率**：MuMu 默认缩放比例可能让图标大小不是 64×64，需要先在真机标定 slot 区域。
3. **敌方/我方区分**：E7 选人界面我方在左、敌方在右，需要分别标定两组 slot rect。
4. **"我方选人"瞬间识别**：玩家点击英雄的瞬间图标可能闪动，建议加 200ms debounce。
5. **网络可达性**：MuMu 默认是 `127.0.0.1:7555`（ADB）。如果模拟器和推荐服务在不同机器，要改 ADB 连接 + 服务器监听 `0.0.0.0`。
6. **code 命名**：所有英雄都是 `c\d{4}` 格式（紫龙官方）。无效 code（如 OCR 识别错）服务端自动忽略。
7. **赛事背景**：MuMu 跑的是国服，数据基于 `world_zlong1` 服。韩服/全球服需要单独抓数据。

---

## 给 Codex / 其他 AI 的入口

如果让另一个 AI 接手写客户端代码，重点告诉他：

1. **接口契约**：`e7rta/QUICK_API.md`（已写好）
2. **示例模板图**：`e7rta/static/img/heroes/c\d{4}.png`（373 张已下载）
3. **服务端在 8799 端口已起**，先 `curl` 验证：
   ```bash
   curl -X POST http://127.0.0.1:8799/api/draft/quick \
     -H "Content-Type: application/json" \
     -d '{"enemy_picks": ["c5154", "c2124"], "top": 5}'
   ```
4. **不需要碰后端代码**，所有逻辑都在 `draft.py` 里。

---

## 状态

- ✅ 服务端：`POST /api/draft/quick` 已上线，0.035s 响应
- ✅ 数据：ss21（2026秋）+ 部分 ss20，可识别全部 373 英雄
- ⏳ 客户端：未实现（你来 or 派给 Codex）