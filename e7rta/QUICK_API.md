# Quick 推荐接口文档

> 极简 BP 推荐：只输入敌方阵容 → top 个我方推荐英雄。专为 MuMu 模拟器截图识别后实时调用设计。

---

## 接口

**Endpoint**：`POST http://127.0.0.1:8799/api/draft/quick`

**Content-Type**：`application/json`

**响应耗时**：首次冷启动 6s（建索引），之后缓存复用 **~35ms**。MuMu 每秒可调用 28 次。

---

## 请求体

```json
{
  "enemy_picks": ["c5154", "c2124", "c1183"],
  "top": 20,
  "season": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `enemy_picks` | `string[]` | 是 | 敌方已选英雄 code（最多 5 个）。code 格式：`c\d{4}`（如 `c5154`）。**无效 code 自动忽略**，不报错 |
| `top` | `int` | 否 | 返回前 N 个推荐。默认 20，clamp 到 `[0, 100]`。`top=0` 返回空数组 |
| `season` | `string \| null` | 否 | 赛季 code（如 `pvp_rta_ss21`）。`null` = 全部赛季（推荐值，默认覆盖最新赛季） |

---

## 响应

```json
{
  "recommendations": [
    {
      "code": "c1168",
      "name": "利纳柯",
      "attr": "火",
      "attr_raw": "fire",
      "job": "骑士",
      "rarity": 5,
      "score": 0.549,
      "self_win_rate": 52.3,
      "counter_score": 68.3,
      "synergy": 52.3,
      "counter_src": "lineup",
      "lineup": {
        "size": 3,
        "wr": 68.3,
        "games": 82,
        "heroes": [
          {"code": "c5154", "name": "调香师维波里丝"},
          {"code": "c2124", "name": "组长亚露嘉"},
          {"code": "c1183", "name": "艾丝黛"}
        ]
      },
      "vs_list": [
        {"code": "c5154", "name": "调香师维波里丝", "wr": 63.3, "games": 7449},
        {"code": "c2124", "name": "组长亚露嘉", "wr": 58.0, "games": 4521},
        {"code": "c1183", "name": "艾丝黛", "wr": 51.2, "games": 8932}
      ],
      "pos_order": 1,
      "pos_rate": 2.2,
      "pos_games": 1179,
      "pos_wr": 52.3,
      "games": 7449,
      "reasons": [
        "克制敌方当前阵容（对位胜率 68.3%）",
        "自身强度 52.3%",
        "⚠ 第 1 选位几乎不用（历史 2.2%），慎选"
      ],
      "counters_weak": ["风"],
      "counters_strong": ["水"]
    }
  ],
  "meta": {
    "input_enemy_picks": ["c5154", "c2124", "c1183"],
    "lineup_subsets_used": [2, 3],
    "scored_candidates": 393,
    "lineup_hit_candidates": 66,
    "lineup_hit_top": {
      "size": 3,
      "wr": 58.0,
      "games": 257,
      "heroes": [
        {"code": "c5154", "name": "调香师维波里丝"},
        {"code": "c2124", "name": "组长亚露嘉"},
        {"code": "c1183", "name": "艾丝黛"}
      ]
    }
  }
}
```

---

## 字段说明

#### `recommendations[]` 每条候选

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | `string` | 英雄 code（如 `c1168`） |
| `name` | `string` | 中文名（如 `利纳柯`） |
| `attr` | `string` | 中文属性（火/水/风/光/暗） |
| `attr_raw` | `string` | 英文属性（fire/ice/wind/light/dark），用于图标渲染 |
| `job` | `string` | 中文职业（战士/骑士/游侠/法师/术师/刺客/辅助） |
| `rarity` | `int` | 星数（3/4/5） |
| `score` | `float` | **推荐指数（0-1）**，越大越推荐。乘 100 即前端展示的 0-100 整数 |
| `self_win_rate` | `float` | 该英雄自身历史胜率（%） |
| `counter_score` | `float` | 该英雄对当前敌方阵容的胜率（%）。阵容级命中时 = `lineup.wr` |
| `synergy` | `float` | 与我方已选英雄的配合胜率（%，未传我方时 = `self_win_rate`） |
| `counter_src` | `string` | 对位估计层级（见下表） |
| `lineup` | `object\|null` | 阵容级命中详情（`counter_src=lineup` 时存在） |
| `vs_list` | `array` | 对敌方**每个**已选英雄的历史对位明细（胜率降序） |
| `pos_order` | `int` | 当前选位（1-5 pick phase；ban 时无意义） |
| `pos_rate` | `float` | 该英雄在第 N 顺位选出的占比（%） |
| `pos_games` | `int` | 该英雄在第 N 顺位的出场场次 |
| `pos_wr` | `float` | 该英雄在第 N 顺位的胜率（%，经验贝叶斯收缩 K=60） |
| `games` | `int` | 该英雄的总出场场次 |
| `reasons` | `string[]` | 推荐理由（中文短语，渲染悬浮窗副标题用） |
| `counters_weak` | `string[]` | 该英雄**克**的属性（如 `["风"]`） |
| `counters_strong` | `string[]` | 该英雄**被克**的属性（如 `["水"]`） |

#### `counter_src` 层级

| 值 | 含义 | 样本条件 |
|---|---|---|
| `lineup` | 阵容级命中（候选 vs 敌方已选全员同时在场） | ≥25 场时采用，按场数加权混合 |
| `pair` | 单体对位（候选 vs 敌方每个英雄分别取胜率加权平均） | 阵容级样本不足时降级 |
| `position` | 选位兜底（无对位样本，回归自身强度 + 选位胜率） | 连单体对位都没有时采用 |
| `none` | 无数据（不参与排序） | 该英雄无任何对局数据 |

#### `lineup` 对象

```json
{
  "size": 3,           // 子集规模（敌方 N 人中的 K 人同时在场）
  "wr": 68.3,          // 该子集在我方选该英雄时的胜率（%，收缩后）
  "games": 82,         // 样本量
  "heroes": [...]      // 该子集包含的敌方英雄
}
```

#### `meta` 对象

| 字段 | 说明 |
|---|---|
| `input_enemy_picks` | 实际参与计算的敌方 code（无效 code 被过滤后） |
| `lineup_subsets_used` | 阵容级命中用了哪些子集规模（如 `[2, 3]` 表示用了 2 人核心和 3 人子集） |
| `scored_candidates` | 总候选数（393 是上限，393 = 全英雄 - 已被 ban/选） |
| `lineup_hit_candidates` | 命中阵容级的候选数 |
| `lineup_hit_top` | 头部推荐中样本量最大的子集（用于 UI 显示「vs 敌方 N 人 68.3% · 412 场」） |

---

## 边界情况

| 输入 | 行为 |
|---|---|
| `enemy_picks: []` | 返回按自身强度排序的全英雄推荐（前 14 个 = 当前版本强势） |
| `enemy_picks: ["c9999"]`（无效 code） | 自动忽略，等价于空阵容 |
| `enemy_picks: ["c9999", "c8888"]`（全无效） | `meta.lineup_hit_top=null`，推荐按自身强度排 |
| `top: -1` 或 `top: 0` | 返回空数组 |
| `top: 99999` | clamp 到 100 |
| `season: "invalid"` | 静默回退到全赛季（不报错） |
| `hand/side` 字段 | quick 接口忽略（建议固定 `first` + `me`） |

---

## 完整 curl 示例

```bash
# 单次查询
curl -X POST http://127.0.0.1:8799/api/draft/quick \
  -H "Content-Type: application/json" \
  -d '{"enemy_picks": ["c5154", "c2124"], "top": 10}'
```

```python
import requests
r = requests.post('http://127.0.0.1:8799/api/draft/quick',
    json={'enemy_picks': ['c5154', 'c2124'], 'top': 10})
for rec in r.json()['recommendations']:
    print(f"{rec['name']:6s} score={rec['score']:.3f}  counter={rec['counter_score']}%")
```

---

## 配套接口（BP 模拟器用）

如果需要更复杂的 BP 流程（preban / pick 顺序 / postban），用 `/api/draft/suggest`：

```bash
curl -X POST http://127.0.0.1:8799/api/draft/suggest \
  -H "Content-Type: application/json" \
  -d '{
    "hand": "first", "side": "me", "phase": "pick",
    "my_picks": ["c2124"], "enemy_picks": ["c5154"],
    "my_bans": [], "enemy_bans": [],
    "season": null
  }'
```

返回字段在 `recommendations` 基础上**多**：bp_step、bp_hand、matchup（终局胜率）、attr_overview（属性克制总览）。