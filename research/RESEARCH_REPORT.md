# 第七史诗 RTA 战绩网站（e7stats）研究报告

> 目标：重启「第七史诗查询工具」项目，分析 RTA（世界竞技场）对战数据。
> 研究日期：2026-09-18
> 结论先行：**数据源（e7stats 后端 API）全部存活，可直接用于分析；原 WinForms 项目已无法对接，需重建数据+分析层。**

---

## 1. 网站现状

- **前端已下线**：服务器对所有路径统一返回 2921 字节的 SPA 壳（`<script src="/next/actv/2024/.../bundle.js">` 实际也返回壳），即 `/next/.../bundle.js` 静态资源已不可达。
- **后端 API 存活**：`https://e7stats.qyzlgame.com/gameApi/*` 全部正常返回 JSON。
- **静态 CDN 存活**：`https://media.zlongame.com/media/pictures/qy/e7/actv/2023/Epic7_Stats/json/*` 可访问。

> 含义：无需依赖原前端，直接调 API 即可重建整个分析与展示层。

---

## 2. 已验证存活的 API 端点

所有端点均为 **POST + `Content-Type: application/x-www-form-urlencoded` + `Referer: https://e7stats.qyzlgame.com/`**。
（原项目用 query string 传参会被 SPA 壳兜底成 HTML，导致解析崩溃。）

### 2.1 `getBattleList`（核心：玩家对局列表）
参数：`nick_no`(必填) `world_code=world_zlong1` `lang=zh-CN` `season_code`(可空=全部/最新)
返回 `result_body.battle_list[]`，每场字段：

| 字段 | 说明 |
|---|---|
| `battle_seq` | 对局唯一 ID（=roomUid） |
| `battle_day` | 日期时间 `2025-01-04 07:12:21.0` |
| `iswin` | 胜负（1/0） |
| `turn` | 回合数 |
| `battle_time` | 对局时长（秒） |
| `season_code` / `season_name` | 赛季 |
| `teamBettleInfo` | **字符串化 JSON** `"{\"my_team\":[...]}"` 我方阵容 |
| `teamBettleInfoenemy` | 敌方阵容 |
| `prebanList` | **字符串化 JSON** `"{\"preban_list\":[\"c2124\",\"\"]}"` 我方 ban |
| `prebanListEnemy` | 敌方 ban |
| `my_deck` / `enemy_deck` | **空壳**（hero_list/preban_list 均为空，旧字段） |

`my_team` 元素字段（**极丰富**）：
`hero_code, pick_order, position, artifact, equip[], grade, awaken_grade, attribute_cd, job_cd, attack_damage, receive_damage, recovery, mvp_point, kill_count, level, mvp, respawn`

### 2.2 `getBattleDetail`（单场详情）
参数：`nick_no`(必填) + `battle_seq`(必填) + `world_code` `lang` `season_code`
返回：`roomUid, teamBettleInfo(=my_team/enemy_team，注意此处为对象而非字符串), teamBettleInfoEnemy, energy_gauge[], turn_list[], regDate, nick_no, nickname, world_code`

- `energy_gauge[]`：每英雄 `{hero_code, energy, team("1"=我方/"2"=敌方), position_no}`
- `turn_list[]`：逐英雄战斗表现，元素含 `my_team[]` 与 `enemy_team[]`，hero 字段同 2.1（含 attack_damage/receive_damage/mvp_point/kill_count 等）

### 2.3 `getSeasonList`
返回 11 个赛季：`pvp_rta_ss11`(2023-08) ~ `pvp_rta_ss21`(2026-08 至今，当前赛季)。含 `season_code, startDate, endDate`。

### 2.4 `getUserInfo`
参数：`nick_no`
返回：`nickname, world_code, grade_code(段位: silver等), rank, winScore, topPercent(胜率%), season_code, season_name, hero_code(招牌英雄), myscore_info{win_rate, win_score}, season_list[]`（该玩家赛季历史，含 is_now_season 标记）

> 注：探测到的 `getBattleInfo` 返回 405；其余猜测端点（getHeroStats 等）均为 405，基本不存在。

---

## 3. 静态映射数据（CDN，GET 即可）

| 文件 | 内容 | 规模 |
|---|---|---|
| `epic7_user_world_cn.json` | 玩家列表 `nick_no / nick_nm / rank / code` | 127,801 用户 |
| `epic7_hero.json` | 英雄 `code → name`（zh-CN 数组 373 项） | 373 英雄 |
| `epic7_equip.json` | 装备/套装定义 | —— |

---

## 4. 关键数据规律（决定采样策略）

**阵容完整度与赛季强相关**（实测 8 玩家 × 各赛季）：

| 赛季 | 名称 | my_team 非空率 |
|---|---|---|
| ss15 / ss15f | 追击/自由 | **0%** |
| ss16 / ss18 | （待验证） | — |
| ss17 / ss17f | 2025夏季 | **100%** |
| ss19 | 2026春季 | 40% |
| ss20 / ss20f | 2026夏季 | **95~100%** |
| ss21 | 2026秋季（当前） | 待验证 |

- **ban 位（prebanList）：100% 完整**（所有赛季）。
- **基本信息（胜负/回合/时长/日期）：100% 完整**。
- 结论：做"出场率/搭配/装备"等**需要阵容**的分析，应优先采样 **ss17 及以后**赛季；做"胜率/ban 率/玩家画像"可覆盖全赛季。

---

## 5. 可分析的维度（基于 my_team 字段）

1. **英雄出场率 / Ban率 / 胜率**：按 `hero_code` 聚合，结合 `iswin` 与 `prebanList`。
2. **阵容搭配**：`my_team` 组合、pick 顺序（`pick_order`）、位置分布（`position`）。
3. **装备/神器**：`equip[]`（set_cri/set_speed/set_counter/set_immune…）、`artifact`。
4. **职业/属性 Meta**：`job_cd`（ranger/knight/assassin…）、`attribute_cd`（dark/light/wind…）。
5. **战斗表现排行**：`attack_damage / receive_damage / mvp_point / kill_count`。
6. **段位维度**：`grade_code` 区分的 Meta 差异（需 getUserInfo）。
7. **赛季趋势**：ss17→ss21 的 Meta 演变。
8. **玩家画像**：getUserInfo（段位/分/胜率/赛季历史）。

---

## 6. 重启方案建议

原 `dqss` 项目（C# WinForms）已不可用：① 接口调用方式错（query vs body）；② 解析字段名已过时（`my_deck.hero_list` → 现 `teamBettleInfo.my_team`）；③ `my_hero_list.First()` 在空列表抛异常。建议重建为三层：

- **数据层**：批量遍历 `epic7_user_world_cn.json` 的玩家 → `getBattleList` 抓取对局 → `getBattleDetail` 补细节 → 落库（SQLite/JSON）。采样优先 ss17+。
- **分析层**：上述 8 类聚合统计。
- **展示层**：Web 看板 / 报表导出（参考原项目 NPOI 导出 Excel 思路，但用更现代的栈）。

---

## 7. 待确认细节

- `getBattleDetail.teamBettleInfo` 为**对象**，`getBattleList.teamBettleInfo` 为**字符串**——解析时需兼容两种格式。
- `turn_list` 语义待明确（实测 len=2，疑似双快照/双阶段）。
- `ss16 / ss18 / ss21` 阵容完整度待验证。
- API 是否有频率限制 / 是否需要登录态（当前无 token 可访问，但需观察稳定性）。
