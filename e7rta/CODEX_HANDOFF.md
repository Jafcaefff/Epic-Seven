# Codex Handoff — BP 客户端开发

> 你是 Codex（OpenAI 模型，跑在 Mac 端），接手 BP 推荐引擎的客户端实现。
> 本文告诉你：你要做什么、怎么做、怎么测、怎么交。

---

## 你接手的项目

**仓库**：`https://github.com/Jafcaefff/Epic-Seven.git`
**目标平台**：Windows（最终跑 MuMu 模拟器）。你在 Mac 上写代码、跨平台库保证可移植。
**已有后端**：Python `e7rta/server.py` 监听 `127.0.0.1:8799`，提供 BP 推荐 API。**不需要碰后端**。

---

## 必读文档（按顺序）

1. `README.md` — 项目概览、Codex 任务分配
2. `e7rta/QUICK_API.md` — **接口契约（最重要）**，定义你要调的 API 字段
3. `e7rta/MUMU_INTEGRATION.md` — 5 步接入流程 + OpenCV 模板匹配骨架 + PyQt 悬浮窗骨架
4. `e7rta/static/img/heroes/.gitkeep` — 图标目录占位，实际图 Windows 本地有，你 Mac 上需要从 jsDelivr CDN 下载：
   ```bash
   # 每个 c\d{4}.png
   curl -L "https://cdn.jsdelivr.net/gh/CeciliaBot/E7Assets-Temp@main/assets/face/c5154_s.png" -o c5154_s.png
   ```
   373 个英雄，写一个脚本批量下载到 `e7rta/client/templates/c\d{4}.png`。

---

## 你的任务（按优先级）

### 1. OCR 识别模块（`e7rta/client/hero_recognizer.py`）

**做什么**：从截图中识别英雄 code。

**算法**：OpenCV 模板匹配
- 输入：PIL Image + 5 个英雄槽位 rect `(x, y, w, h)`
- 输出：`["c5154", "c2124", ...]`（按槽位顺序）
- 阈值：`score > 0.7` 算匹配成功

**测试**（**关键**——你 Mac 上能完整跑）：
```python
# tests/test_hero_recognizer.py
from hero_recognizer import recognize_enemy_team
from PIL import Image
import os

def test_recognize_known_image():
    # 用一张已知的 BP 模拟器截图（Windows 端提供）
    img = Image.open('tests/fixtures/enemy_team_3.png')
    # 标定好的 5 个槽位 rect
    slot_rects = [(100, 200, 64, 64), (200, 200, 64, 64), (300, 200, 64, 64)]
    codes = recognize_enemy_team(img, slot_rects)
    assert codes[0] == 'c5154'
    assert codes[1] == 'c2124'
```

**Mac 端独立测试方法**：
- 合成测试图——用 PIL 把 5 张英雄图标（`c\d{4}.png`）拼成一张 640×400 的"模拟选人界面"
- 跑 recognize_enemy_team 验证返回正确 codes
- **不需要真 MuMu**

### 2. PyQt 悬浮窗（`e7rta/client/overlay_ui.py`）

**做什么**：半透明置顶窗口，实时显示推荐。

**要求**：
- `Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool`
- `setAttribute(Qt.WA_TranslucentBackground)`
- `setWindowOpacity(0.9)`
- 黑色背景 + 黄色/白色文字（参考 MUMU_INTEGRATION.md 的 CSS）
- 每张推荐卡显示：头像 + 名字 + 推荐指数（0-100 整数）+ 对位数据

**Mac 端独立测试**：直接 `python overlay_ui.py` 跑出窗口，填 mock 数据看渲染。

### 3. API 客户端（`e7rta/client/recommender.py`）

**做什么**：封装 `POST /api/draft/quick`。

```python
import requests

class Recommender:
    def __init__(self, base_url='http://127.0.0.1:8799'):
        self.base_url = base_url
        self.session = requests.Session()

    def recommend(self, enemy_codes, top=10, timeout=2):
        """返回 dict（参考 QUICK_API.md 的 response 字段）"""
        r = self.session.post(
            f'{self.base_url}/api/draft/quick',
            json={'enemy_picks': enemy_codes, 'top': top},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()
```

**Mock 测试**（**不需要真服务**）：
```python
# tests/test_recommender.py
from unittest.mock import patch
from recommender import Recommender

def test_recommend_with_mock():
    fake = {'recommendations': [{'code': 'c1168', 'name': '利纳柯', 'score': 0.55}],
            'meta': {'lineup_hit_candidates': 0}}
    with patch.object(Recommender, 'recommend', return_value=fake):
        rec = Recommender()
        out = rec.recommend(['c5154'])
        assert out['recommendations'][0]['name'] == '利纳柯'
```

### 4. 主循环骨架（`e7rta/client/main.py`）

```python
import time
from capture_stub import capture           # TODO: Windows 端替换为 MuMu ADB 截图
from hero_recognizer import recognize_enemy_team
from recommender import Recommender
from overlay_ui import Overlay

SLOT_RECTS = [...]  # 标定好的 5 个敌方英雄槽位 (x, y, w, h)
INTERVAL = 1.5      # 截图周期（秒）

rec = Recommender()
ov = Overlay()
ov.show()

last_codes = None
while True:
    img = capture()                                      # 截图（Mac 用 stub）
    codes = recognize_enemy_team(img, SLOT_RECTS)
    if codes and codes != last_codes:
        result = rec.recommend(codes, top=10)
        ov.update(result['recommendations'])
        last_codes = codes
    time.sleep(INTERVAL)
```

**`capture_stub.py`**（**Mac 端 mock**）：
```python
from PIL import Image

def capture():
    """Mac 端 stub：返回一张合成测试图。Windows 上替换为 MuMu ADB 截图。"""
    # TODO Windows: subprocess adb screencap + Image.open(io.BytesIO(...))
    return Image.open('tests/fixtures/synthetic_enemy_team.png')
```

### 5. 测试 fixtures

`e7rta/client/tests/fixtures/` 需要几张测试图：
- `synthetic_enemy_team.png` — 合成图（3 个英雄已知 code）
- `enemy_team_3.png` — 真实截图（Windows 端你拉 PR 时附上）

---

## 提交代码规范

**目录结构**：
```
e7rta/client/
├── __init__.py
├── hero_recognizer.py
├── overlay_ui.py
├── recommender.py
├── main.py
├── capture_stub.py
└── tests/
    ├── test_hero_recognizer.py
    ├── test_recommender.py
    └── fixtures/
```

**不要碰**：
- `e7rta/draft.py`（后端推荐引擎）
- `e7rta/server.py`（HTTP 服务）
- `e7rta/data.db`（数据文件，.gitignore 已排除）
- `e7rta/static/img/heroes/*.png`（373 张图标，.gitignore 排除）

**提交格式**：
```
git checkout -b feat/client-v1
git add e7rta/client/
git commit -m "feat(client): OCR + PyQt overlay + API client + main loop + tests"
git push origin feat/client-v1
# 在 GitHub 开 PR，标题同 commit message
```

**PR 模板**（`.github/PULL_REQUEST_TEMPLATE.md`）：
```markdown
## 改动
- [ ] OCR 识别模块（hero_recognizer.py + tests）
- [ ] PyQt 悬浮窗（overlay_ui.py）
- [ ] API 客户端（recommender.py + mock test）
- [ ] 主循环骨架（main.py + capture_stub.py）
- [ ] 测试 fixtures（synthetic + real screenshots）

## 测试
- [ ] 所有 pytest 通过（`pytest e7rta/client/tests/`）
- [ ] Mac 端合成图识别准确率 ≥ 95%
- [ ] 截图周期 ≤ 2s（`time.time()` 包 capture + recognize）

## 待办
- [ ] Windows 端 capture() 实现（MuMu ADB 截图）— 留给 Windows 端接手人
- [ ] 真机端到端测试
```

---

## 依赖安装

```bash
pip install pillow opencv-python-headless pyqt5 requests pytest
```

- `opencv-python-headless`（不要 full 版，PyQt 不需要 GUI）
- `PyQt5`（Mac 端用 python 3.11+ 可能装不上，需要 `brew install pyqt@5`）

---

## 常见问题

**Q: 服务连不上？**
A: Mac 端测试时 Recommender 用 mock；Windows 上 `python e7rta/server.py` 起本地推荐服务在 8799。

**Q: 模板匹配率低？**
A: 检查图标大小（统一 resize 到 64×64）、截图分辨率、slot rect 标定精度。

**Q: PyQt 在 Mac 上跑不起来？**
A: `brew install pyqt@5` 或用 conda env。

---

## 完成定义

你的 PR 合并后：
1. `pytest e7rta/client/tests/` 全过
2. Mac 端能跑 main.py 显示合成图推荐
3. README.md 加一段 "Windows 端集成测试" 说明，留 TODO 给 Windows 端接手人

剩下的（MuMu ADB 截图 + 真机集成）由 Windows 端接管。