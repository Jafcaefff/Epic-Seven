# 第七史诗 RTA BP 辅助系统

> Epic Seven RTA Ban-Pick 辅助系统：基于 5.4 万场真实对局数据，给玩家提供选人/ban 人推荐 + 终局胜率预测。
> 主战场：中国服（紫龙代理），未来扩展到 MuMu 模拟器自动识别阵容。

---

## 项目结构

```
第七史诗查询工具/
├── e7rta/                              # BP 辅助核心（Python 服务端）
│   ├── server.py                       # HTTP 服务 (端口 8799)
│   ├── draft.py                        # 推荐引擎（分层对位 + 选位匹配 + matchup）
│   ├── analytics.py                    # 数据查询层
│   ├── config.py                       # API 客户端（紫龙 e7stats 后端）
│   ├── crawler.py / crawl_full.py      # 数据抓取（按 (nick_no, season) 维度断点续传）
│   ├── importer.py                     # 静态 JSON 导入（英雄/装备/玩家）
│   ├── fetch_images.py                 # 英雄图标本地缓存
│   ├── fetch_meta.py                   # Champion+ 段位职业选手 meta 共识抓取
│   ├── static/
│   │   ├── index.html                  # 主页面（5 Tab 数据分析）
│   │   ├── draft.html                  # BP 模拟器 UI
│   │   └── img/heroes/                 # 373 张英雄图标 (c\d{4}.png)
│   ├── data.db                         # SQLite：battles + battle_picks + heroes
│   ├── QUICK_API.md                    # Quick 接口文档（MuMu 接入用）
│   ├── MUMU_INTEGRATION.md             # MuMu 接入指南
│   ├── verify_system.py                # 综合回归测试（30 项断言）
│   ├── audit_strategy.py / audit_deep.py  # 推荐质量策略审查
│   └── verify_bpflow.js                # BP 流程状态机回归
├── dqss/                               # 旧项目存档（不动）
├── Debug/                              # 旧调试 DLL（不动）
└── .workbuddy/                         # AI 助手记忆（不进 git）
```

---

## 快速开始

### 启动推荐服务

```bash
cd e7rta
python server.py
# 监听 http://127.0.0.1:8799
```

### 测试接口

```bash
curl -X POST http://127.0.0.1:8799/api/draft/quick \
  -H "Content-Type: application/json" \
  -d '{"enemy_picks": ["c5154", "c2124"], "top": 5}'
```

### 浏览器访问

- **主页面**：`http://127.0.0.1:8799/`（数据分析：总览/对阵库/克制关系）
- **BP 模拟器**：`http://127.0.0.1:8799/draft`（选人辅助）

---

## 当前状态

| 模块 | 状态 |
|---|---|
| BP 推荐引擎（分层对位 / 选位匹配 / matchup）| ✅ 完成 |
| Quick 接口（MuMu 极简调用）| ✅ 完成 |
| 性能（缓存后 0.035s 响应）| ✅ 完成 |
| 测试（30/30 回归 + 策略审查）| ✅ 全过 |
| ss21（2026秋）数据 | ✅ 53k 场 |
| ss20（2026夏）数据 | ⏳ 抓取中 |
| MuMu 客户端 | ❌ 未实现 |
| Codex 协作 | ⏳ 进行中 |

---

## Codex 任务分配（Mac 端）

Codex 在 Mac 上负责：

1. **OCR 识别模块**（`e7rta/client/hero_recognizer.py`）
   - OpenCV 模板匹配，从截图中识别英雄 code
   - 单元测试：Mac 上用 `e7rta/static/img/heroes/*.png` mock 输入
   - 接口预留：`capture()` 函数返回 PIL Image，Windows 端实现 ADB/MuMu 截图

2. **PyQt 悬浮窗**（`e7rta/client/overlay_ui.py`）
   - 跨平台 UI，半透明置顶
   - 显示推荐指数 + 对位数据
   - Mac/Linux/Windows 都能跑（无需 MuMu）

3. **API 客户端**（`e7rta/client/recommender.py`）
   - requests 封装 `/api/draft/quick`
   - mock 服务端测试（不依赖真实服务）

4. **主循环骨架**（`e7rta/client/main.py`）
   - 截图 → OCR → API → 渲染悬浮窗
   - 截图接口预留 TODO，注释清楚"Windows 上替换为 ADB 实现"

5. **测试**（`e7rta/client/tests/`）
   - pytest 单元测试，覆盖 OCR / API / 主循环
   - Mac 端完整可跑

### Windows 端（我）后续做

- MuMu 模拟器 ADB 截图实现（替换 client/main.py 里的 capture mock）
- 真机端到端集成测试

### 关键文档

- **Quick 接口**：`e7rta/QUICK_API.md`（必读，定义 Codex 要调的接口）
- **MuMu 接入**：`e7rta/MUMU_INTEGRATION.md`（架构图 + 代码骨架）

---

## 数据说明

- **数据源**：紫龙 e7stats 后端 API（`gameApi/*`，Referer 必需）
- **赛季**：ss11 (2023-08) ~ ss21 (2026-08 当前)
- **样本**：54k 场 + 525k picks，覆盖国服 Master+ 段位
- **赛季过滤**：阵容完整度 ss17+ 才 ~100%，BP 辅助分析应采样 ss17+

---

## 开发约定

- **Python 3.13+**，无第三方依赖（stdlib only）
- **数据库**：SQLite，schema 见 `e7rta/db.py`
- **测试**：跑 `python e7rta/verify_system.py` 应全过
- **重启服务**：改了 `server.py` 或 `draft.py` 要重启 server.py

---

## 后续路线

1. **数据补全**：ss20 + ss19 全赛季（背景爬虫）
2. **客户端实现**：Codex Mac 端 → Windows 端集成测试
3. **MuMu 实机**：截图识别准确率优化
4. **韩服/全球服扩展**：单独抓取 + 独立 season_code