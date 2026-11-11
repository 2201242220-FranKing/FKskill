---
name: tuntun-forum
description: "This skill should be used when the user wants to read Tunshuo campus forum posts (豚说 / 校友圈): latest posts, hottest posts, keyword search, post detail, per-school comparison, daily digest, CSV export, keyword alerts, or turning forum posts into a WeChat / 公众号 article draft. 触发词：查帖子、最新动态、热帖、搜一下「关键词」、浙外 / 浙工大 / 浙科 / 长征、四校对比、日报、导出表格、写成微信推文。全部为匿名只读 GET，不发帖不登录。"
agent_created: true
---

# 豚说论坛查询与微信成文

## 用途

用自然语言完成「查帖子 → 看数据 → 出内容」全流程：从 4 个学校校友圈匿名只读地取帖子，按用户要求汇总、对比、导出，或进一步写成微信 / 公众号稿。**一个技能覆盖取数与成文**，不需要记命令，根据用户这句话判断该做什么即可。

## 快速开始

先定位本技能目录（`SKILL.md` 所在目录），记为 `$SKILL_DIR`。所有能力都通过同一个只读脚本完成，脚本只用 Python 标准库、不依赖任何本机项目：

```bash
python3 "$SKILL_DIR/scripts/forum_query.py" --help
python3 "$SKILL_DIR/scripts/forum_query.py" schools
python3 "$SKILL_DIR/scripts/forum_query.py" latest --limit 10
```

任何命令都可加 `--json` 输出结构化数据，便于二次加工；加 `--show-author` 才显示作者原名（默认打码）。

## 意图 → 动作映射

根据用户说的话直接选命令，不要让用户背参数：

| 用户可能这么说 | 执行 |
|---|---|
| 「看看最近有什么新帖」「刷一下论坛」 | `latest`，默认全部 4 校、20 条 |
| 「浙工大最近发了啥」 | `latest --school 浙工大` |
| 「最火的帖子」「热帖榜」 | `hot`（默认 10 条），并如实说明口径 |
| 「浙外热度最高的 5 条」 | `hot --school 浙外 --limit 5` |
| 「搜一下有没有人提校园卡」 | `search --keyword 校园卡`（默认 10 条，按热度降序） |
| 「找 20 条关于奶茶的帖子」 | `search --keyword 奶茶 --limit 20` |
| 「这条帖子详细内容」 | `detail --id <帖子ID>` |
| 「四个学校哪个最活跃」 | `compare` |
| 「给我一份今天的日报」 | `report` |
| 「导成 Excel / CSV」 | `export --out <用户指定路径>` |
| 「盯着『兼职』有没有新帖」 | `watch --keyword 兼职` |
| 「把本周热帖写成公众号 / 微信推文」「用帖子做一期微信内容」 | `wechat --json` 取素材包，再按下方工作流成文 |
| 「我发的帖子和回复呢」 | `my`，返回占位说明，**不要编数据** |
| 「有哪些学校 / 别名」 | `schools` |

组合需求按数据流串联：例如「把浙科讲考研的帖子找出来写成微信稿」→ `wechat --school 浙科 --keyword 考研 --json` → 成文。

**指定学校**：`--school` 接受简称、全称、别名或直接给 circleId；省略即全部 4 校。遇到不认识的名字先用 `schools` 核对，不要猜测 ID。

## 命令速查

```
schools                                      列出 4 校、别名与 circleId
latest   [--school X] [--limit N] [--json]    最新帖，按时间倒序
hot      [--school X] [--limit N] [--json]    热度榜
search   --keyword K [--school X] [--limit N] [--pages N] [--json]
detail   --id ID [--json]                     帖子详情
compare  [--json]                             4 校发帖量 / 热度 / 活跃时段
report   [--days 1] [--json]                  日报素材
export   --out PATH                           导出 CSV（UTF-8 BOM）
watch    --keyword K [--state PATH] [--json]  关键词命中；不给 --state 则不写任何文件
wechat   [--school X] [--keyword K] [--limit N] [--json]   微信成文素材包
my                                            占位：需登录态与接口，暂未开放
selftest                                      离线自测，不发网络请求
```

全局参数：`--base`、`--circle ID --name 名称`（临时换成单个自建圈子）、`--timeout`、`--show-author`、`--json`。

## 数据口径（必须原样告知用户，不得美化）

- **热帖不是全站十大榜**：`ten/page` 需登录（返回「请先登录」），当前为「最近取样里按 `totalHeatNum` 降序」。输出时写清「取样热榜，非全站十大」。
- **搜索不是全量**：走服务端 `keyword` 检索，默认每校最多翻 5 页 × 50 条；命中总数不超过单页容量时自动停止翻页。输出固定带「接口命中 X 条 / 本次扫描 Y 条 / 返回前 N 条」。
- **日报不是精确按天**：接口没有时间范围参数，`report --days` 只影响取样量，结果基于最近取样帖，需注明。
- **详情看不到评论内容**：`commentList` 实测恒为空，只能给评论数，不要编造回复文本。
- **长征当前 0 条**：`code=200` 但 `data=[]`，保留在列表、不算失败；不要把它写成「接口挂了」。
- **作者默认打码**，接口未返回原帖 URL，不要伪造链接。
- 单个学校失败不影响其他学校；全部失败时明确报错，不要用旧数据冒充新结果。

## 微信成文工作流

1. 运行 `wechat --json`（可带 `--school` / `--keyword` / `--limit`）拿到素材包：分学校帖子、热度榜、统计与口径说明。
2. 按用户在提示里给的角度、字数、语气、栏目名撰写；用户没指定时用简洁校园资讯口吻，给 3 个标题备选 + 正文 + 「本帖数据来自……」的来源标注。
3. **只使用素材包里真实存在的帖子**：不编造标题、作者、时间、热度、链接；引用正文时可摘录，但不要改写成未发生的事实。
4. 结尾附上数据口径（取样热榜、扫描条数、抓取时间、涉及学校）。
5. 需要配图时，若本机装有 `tun-skill`（豚豚插画）可交给它；未安装就只交付文字稿，本技能不生成图片，也不依赖任何插画技能。

第一版输出格式从简，以准确、可读为准；排版与模板化放到 2.0 再优化。

## 账号与 `my` 占位

「我的帖子 / 评论回复」暂不可查：技术尚未提供「我的帖子列表」「评论列表」接口（`createId`、`userNo` 传参实测被忽略，`detail` 里 `commentList` 为空），且需要登录态识别身份。运行 `my` 会返回明确说明。不要编造个人帖子，不要临时把令牌贴进对话或写进配置。接口到位后再补这个子命令。

## 安全红线

- 只发匿名只读 GET；不发 POST，不做发帖、回复、点赞、删除等写操作。
- 不读取、不保存、不打印任何令牌；不使用登录态接口；不修改 `auto_poll`，不启动桌宠程序。
- 不修改仓库里的 `config.example.json`；本地覆盖请用同目录 `config.json`（已被 `.gitignore` 排除）。
- `export` / `watch --state` 只在用户显式指定路径时写文件，不写默认位置、不覆盖无关文件。
- 不引入第三方库，不拼接本机绝对路径，不 import 其他技能或桌宠项目的代码。

## 配置

默认公开参数写在 `config.example.json`（域名与 4 校 circleId，均为匿名只读接口参数，不含凭据）。脚本内置同一份兜底值，因此单独拷贝技能目录也能跑。覆盖优先级：

`--base / --circle` 参数 > 环境变量 `TUNTUN_FORUM_BASE` / `TUNTUN_FORUM_CIRCLES`(JSON) / `TUNTUN_FORUM_TIMEOUT` > 本地 `config.json` > `config.example.json` > 内置默认值。

换学校时复制 `config.example.json` 为 `config.json` 后改 `circles`，不用改代码。

## 排错

- 报「请先登录」：说明走到了 `ten/page` 或 `new/num`；本技能应自动降级，检查是否被改成了需登录的路径。
- 某校 0 条：先看是否为空圈子（长征），再核对 circleId。
- 超时：用 `--timeout 25` 放宽；空圈子实测响应偏慢。
- 字段变动：只改脚本顶部的映射常量或 `references/api.md` 里登记的表，不要重写逻辑。
- 先跑 `selftest` 确认离线逻辑正常，再判断是不是网络问题。

## 资源

- `scripts/forum_query.py`：全部查询与导出逻辑，可脱离上下文直接执行。
- `references/api.md`：接口清单、字段映射、鉴权差异、防串校规则、待技术确认问题。排查数据异常或改字段时再读。
- `config.example.json`：公开只读配置模板。
