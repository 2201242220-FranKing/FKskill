# 豚说论坛接口参考（2026-11-11 实测版）

仅在需要核对字段、排查串校或调整映射时阅读本文件。日常查询直接运行 `scripts/forum_query.py`。

## 接口与鉴权差异

| 路径 | 用途 | 匿名可读 | 备注 |
|---|---|---|---|
| `GET /app/dynamic/page` | 帖子列表（最新 / 关键词） | 是 | `circleId`、`pageNum`、`pageSize`、`type=dynamic`、`tagId` 有效 |
| `GET /app/dynamic/detail?id=<帖子ID>` | 帖子详情 | 是 | 返回约 41 个字段 |
| `GET /app/dynamic/ten/page` | 十大热帖 | 否 | 返回 `code=110 请先登录` |
| `GET /app/dynamic/new/num` | 新帖提醒数 | 否 | 返回 `code=110 请先登录` |

技术文档里「站内信 / 提醒未读消息」写成了与十大热帖相同的 `ten/page` 路径，疑似笔误，正确路径待确认。

**因此本技能不依赖任何需登录的接口**：热帖用「最新取样里按 `totalHeatNum` 降序」代替，输出时必须如实标注这不是全站十大榜。

响应外层（实测）：

```json
{"code":200, "data":[{"id":"...", "content":"..."}], "recordsTotal":7614,
 "message":"请求成功", "encrypt":false, "exception":null}
```

`data` 直接是帖子数组，不是 `records/list` 包裹；`recordsTotal` 在顶层。`code=400` 为参数错误，`code=110` 为缺登录态。

## 字段映射

| 本技能字段 | 来源 | 说明 |
|---|---|---|
| `id` | `id` | 19 位字符串，`dynamicNo` 仅作兜底 |
| `title` | `content` | 真实数据没有标题字段，取正文首 24 字（去链接、合并空白、话题转方括号） |
| `content` | `content` | 正文原文，用于详情与微信成文 |
| `author` | `userName` | 默认打码，`--show-author` 才显示 |
| `tag` | `tagList[0].name` | 兜底 `circleTitle` |
| `heat` | `totalHeatNum` | 兜底 `heatNum / zanNum / commentsNum / browseNum` |
| `time` | `createTime` | 字符串时间，可直接按字典序比较 |
| `comments` | `commentsNum` | 评论数；详情里的 `commentList` 实测恒为 `None` |
| `circle_title` | `circleTitle` | 用于回读校验学校名 |
| `circle_id` | `circleId` | 存在时用于防串校过滤 |
| `url` | 无 | 接口未返回任何链接，原帖 H5 规则待技术提供 |

## keyword 参数（未文档化，实测有效）

`/app/dynamic/page` 接受 `keyword`，`recordsTotal` 会随命中数变化（例：浙外搜「奶茶」从 7645 降到 34），`pageNum` 分页有效，匿名可读。**这是实测发现的未文档化参数**，建议向技术确认是否长期稳定、最大 `pageSize` 与限频。脚本据此实现服务端检索，并在命中总数不超过单页容量时自动停止翻页，避免发出多余请求。

## 防串校

不传 `circleId` 时接口返回全站数据。脚本对每个学校单独带 `circleId` 请求；若响应条目里带 `circleId` 且与当前学校不一致，直接丢弃该条目。合并后按 `id` 去重。单个学校失败（超时、空数组、错误码）不影响其他学校，空圈子不算失败。

## 四校登记（2026-11-11 匿名联调）

| 简称 | circleId | 回读圈子名 | recordsTotal |
|---|---|---|---|
| 浙外 | `1844924022131912706` | 浙外校友圈 | 约 7637 |
| 浙工大 | `1849752540716011521` | 浙工大校友圈 | 约 7295 |
| 浙科 | `1846842931990769666` | 浙科校友圈 | 约 12152 |
| 长征 | `1860950189561458688` | 空数组 | 0 |

长征返回 `code=200` 但 `data=[]`；换 `type=dynamic` / 不带 `type` / `type=all` 均相同。可能是 ID 写错或圈子尚未开放发帖，保留在列表中，不影响其他学校。

## 仍需技术确认

1. 完整「学校简称 → circleId」对照表；是否有一次拿到全部圈子列表的接口；长征 ID 是否写错。
2. `keyword` 是否官方支持、最大 `pageSize`、限频、能否与 `circleId` 同时传、能否搜评论内容。
3. 十大热帖 / 新帖数能否开匿名只读入口；若不能，token 获取方式、Header 名称、有效期与刷新方式。
4. 站内信未读的正确路径与返回字段。
5. 原帖 H5 链接拼接规则。
6. 「我的帖子列表」「评论 / 回复列表」接口；`createId`、`userNo` 传参实测被忽略。
7. `new/num` 的 `time` 语义、`tagId` 枚举、多校并发请求的限频。

## 安全约定

只读 GET；不使用、不保存、不打印任何令牌；不做发帖 / 回复 / 点赞等写操作；默认不自动轮询；导出与状态文件仅在用户显式指定路径时写入。
