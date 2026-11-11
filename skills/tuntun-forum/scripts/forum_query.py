#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豚说论坛只读查询（FKskill / tuntun-forum）。

自包含：只用 Python 标准库，不 import 任何本机项目或其他技能。
只发匿名只读 GET；不读取、不保存、不打印任何令牌；默认不写文件。

用法示例：
    python3 forum_query.py schools
    python3 forum_query.py latest --limit 10
    python3 forum_query.py hot --school 浙外 --limit 5
    python3 forum_query.py search --keyword 校园卡 --limit 20
    python3 forum_query.py wechat --school 浙工大 --keyword 考研 --json
    python3 forum_query.py selftest
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

P_LATEST = "/app/dynamic/page"
P_DETAIL = "/app/dynamic/detail"

OK_CODES = (200, 0, "200", "0", "SUCCESS", "success")
AUTH_CODES = (110, 401, 403, "110", "401", "403")

# 字段候选表：技术改字段时只改这里（或 references/api.md 里登记的映射）。
FIELDS = {
    "id": ("id", "dynamicId", "postId", "dynamicNo"),
    "content": ("content", "dynamicContent", "text", "body"),
    "author": ("userName", "nickname", "author", "userNickname", "createBy"),
    "tag_list": ("tagList", "tags", "tagNames"),
    "tag_name": ("name", "tagName", "title", "labelName"),
    "tag": ("tagName", "tag", "tagTitle", "labelName", "circleTitle"),
    "time": ("createTime", "publishTime", "time", "createdAt", "createDate"),
    "heat": ("totalHeatNum", "heatNum", "heat", "hot", "zanNum",
             "commentsNum", "browseNum", "viewCount"),
    "comments": ("commentsNum", "commentCount", "replyNum"),
    "circle_title": ("circleTitle", "circleName"),
    "circle_id": ("circleId", "circle_id"),
    "url": ("url", "link", "h5Url", "shareUrl", "detailUrl"),
}

# 内置兜底值：与 config.example.json 保持一致，确保只拷贝本脚本也能跑。
# 这里只有公开匿名只读接口参数，不含任何账号、令牌或个人信息。
BUILTIN = {
    "base": "https://alumni.qiyuanheshan.com",
    "timeout": 15,
    "title_max": 24,
    "page_size": 50,
    "max_pages": 5,
    "circles": [
        {"id": "1844924022131912706", "name": "浙外",
         "aliases": ["浙外", "浙江外国语学院", "浙外校友圈", "zisu"]},
        {"id": "1849752540716011521", "name": "浙工大",
         "aliases": ["浙工大", "浙江工业大学", "浙工大校友圈", "zjut"]},
        {"id": "1846842931990769666", "name": "浙科",
         "aliases": ["浙科", "浙科大", "浙江科技大学", "浙江科技学院", "浙科校友圈", "zust"]},
        {"id": "1860950189561458688", "name": "长征",
         "aliases": ["长征", "浙江长征职业技术学院", "长征校友圈"]},
    ],
}

ALL_WORDS = ("", "全部", "所有", "所有学校", "全部学校", "all", "ALL", "any", "*")


class ForumError(Exception):
    """接口或配置错误。"""


class ForumAuthError(ForumError):
    """需要登录态（code=110 等）。"""


def pick(d, keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def as_int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def summarize(text, limit=24):
    s = re.sub(r"https?://\S+", "", str(text or ""))
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^#([^#]{1,20})#\s*", r"[\1] ", s)
    limit = max(8, min(120, as_int(limit, 24)))
    if len(s) > limit:
        s = s[:limit - 1] + "…"
    return s or "(无标题动态)"


def tag_of(p):
    lst = pick(p, FIELDS["tag_list"])
    if isinstance(lst, list):
        for it in lst:
            if isinstance(it, str) and it.strip():
                return it.strip()[:30]
            if isinstance(it, dict):
                n = pick(it, FIELDS["tag_name"])
                if n:
                    return str(n)[:30]
    return str(pick(p, FIELDS["tag"], "") or "")[:30]


def mask_author(name):
    s = str(name or "").strip()
    return (s[0] + "**") if s else "匿名"


def normalize(p, school, cfg):
    if not isinstance(p, dict):
        return None
    content = str(pick(p, FIELDS["content"], "") or "")
    title = summarize(content, cfg.get("title_max", 24))
    pid = str(pick(p, FIELDS["id"], "") or "") or title
    return {
        "id": pid,
        "school": str(school.get("name") or ""),
        "circle_id": str(school.get("id") or ""),
        "title": title,
        "content": content,
        "tag": tag_of(p),
        "heat": as_int(pick(p, FIELDS["heat"], 0)),
        "time": str(pick(p, FIELDS["time"], "") or "")[:30],
        "author": str(pick(p, FIELDS["author"], "") or "")[:60],
        "comments": as_int(pick(p, FIELDS["comments"], 0)),
        "circle_title": str(pick(p, FIELDS["circle_title"], "") or "")[:40],
        "raw_circle_id": str(pick(p, FIELDS["circle_id"], "") or ""),
        "url": str(pick(p, FIELDS["url"], "") or ""),
    }


def filter_circle(items, school):
    """接口不传 circleId 会返回全站数据；响应里带 circleId 且不匹配时丢弃，防串校。"""
    cid = str(school.get("id") or "")
    out = []
    for p in items:
        if not isinstance(p, dict):
            continue
        rc = str(pick(p, FIELDS["circle_id"], "") or "")
        if rc and cid and rc != cid:
            continue
        out.append(p)
    return out


def unwrap(raw):
    if isinstance(raw, list):
        return raw, 0
    if not isinstance(raw, dict):
        raise ForumError("接口返回格式不认识")
    code = raw.get("code", 200)
    if code not in OK_CODES:
        msg = str(raw.get("message") or raw.get("msg") or ("接口返回码 %s" % code))[:60]
        if code in AUTH_CODES:
            raise ForumAuthError(msg)
        raise ForumError(msg)
    if raw.get("encrypt"):
        raise ForumError("响应已加密，需技术提供解密方式")
    data = raw.get("data")
    total = as_int(raw.get("recordsTotal") or raw.get("total") or 0)
    if data is None:
        return [], total
    if isinstance(data, list):
        return data, total
    if isinstance(data, dict):
        for k in ("records", "list", "rows", "items", "data"):
            if isinstance(data.get(k), list):
                return data[k], as_int(data.get("total") or total)
        return [], total
    return [], total


def unwrap_detail(raw):
    if not isinstance(raw, dict):
        raise ForumError("详情接口返回格式不认识")
    code = raw.get("code", 200)
    if code not in OK_CODES:
        msg = str(raw.get("message") or raw.get("msg") or ("接口返回码 %s" % code))[:60]
        if code in AUTH_CODES:
            raise ForumAuthError(msg)
        raise ForumError(msg)
    d = raw.get("data")
    if isinstance(d, dict):
        return d
    if isinstance(d, list) and d and isinstance(d[0], dict):
        return d[0]
    raise ForumError("详情接口没有返回帖子对象")


def http_get(base, path, params, timeout):
    url = str(base).rstrip("/") + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "FKskill-tuntun-forum/1.0 (read-only)",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise ForumError("接口 HTTP %s" % e.code)
    except urllib.error.URLError as e:
        raise ForumError("连不上论坛：%s" % str(e.reason)[:60])
    except Exception as e:
        raise ForumError("请求失败：%s" % str(e)[:60])
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise ForumError("响应不是 JSON：%s" % body[:80])


def should_stop(page_count, page_size, total, scanned):
    """命中总数不超过单页容量时提前停，避免对空圈子/小结果集发多余请求。"""
    if page_count < page_size:
        return True
    if total and scanned >= total:
        return True
    return False


def fetch_page(cfg, school, page_num, page_size, keyword=None):
    params = {"circleId": school["id"], "pageNum": page_num,
              "pageSize": page_size, "type": "dynamic"}
    if keyword:
        params["keyword"] = keyword
    raw = http_get(cfg["base"], P_LATEST, params, cfg["timeout"])
    items, total = unwrap(raw)
    items = filter_circle(items, school)
    posts = [normalize(p, school, cfg) for p in items]
    return [p for p in posts if p], total


def unique(posts):
    seen, out = set(), []
    for p in posts:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        out.append(p)
    return out


def fetch_school(cfg, school, pages, page_size, keyword=None):
    all_posts, total, scanned = [], 0, 0
    for n in range(1, max(1, pages) + 1):
        posts, t = fetch_page(cfg, school, n, page_size, keyword)
        total = t
        scanned += len(posts)
        all_posts.extend(posts)
        if should_stop(len(posts), page_size, total, scanned):
            break
    return unique(all_posts), total, scanned


def fetch_all(cfg, schools, pages, page_size, keyword=None):
    merged, errors, totals, scanned = [], [], {}, 0
    for s in schools:
        try:
            posts, total, sc = fetch_school(cfg, s, pages, page_size, keyword)
            merged.extend(posts)
            totals[s["name"]] = total
            scanned += sc
        except ForumError as e:
            errors.append({"school": s["name"], "id": s["id"], "error": str(e)})
    return unique(merged), errors, totals, scanned


def deep_merge(base, override):
    out = dict(base)
    if not isinstance(override, dict):
        return out
    for k, v in override.items():
        if not str(k).startswith("_"):
            out[k] = v
    return out


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(args):
    cfg = dict(BUILTIN)
    example = os.path.join(SKILL_DIR, "config.example.json")
    local = os.path.join(SKILL_DIR, "config.json")
    for path, label in ((example, "config.example.json"), (local, "config.json")):
        if os.path.isfile(path):
            try:
                cfg = deep_merge(cfg, read_json(path))
            except (ValueError, OSError) as e:
                raise ForumError("%s 不是合法 JSON：%s" % (label, e))
    env_base = os.environ.get("TUNTUN_FORUM_BASE")
    if env_base:
        cfg["base"] = env_base
    env_circles = os.environ.get("TUNTUN_FORUM_CIRCLES")
    if env_circles:
        try:
            cfg["circles"] = json.loads(env_circles)
        except ValueError:
            raise ForumError("TUNTUN_FORUM_CIRCLES 不是合法 JSON")
    env_timeout = os.environ.get("TUNTUN_FORUM_TIMEOUT")
    if env_timeout:
        cfg["timeout"] = as_int(env_timeout, 15)
    if getattr(args, "base", None):
        cfg["base"] = args.base
    if getattr(args, "timeout", None):
        cfg["timeout"] = args.timeout
    if getattr(args, "circle", None):
        cfg["circles"] = [{"id": str(args.circle),
                           "name": getattr(args, "name", "") or "自定义",
                           "aliases": []}]
    if not re.match(r"^https?://", str(cfg.get("base") or "")):
        raise ForumError("base 必须是 http(s):// 开头的完整地址")
    cfg["timeout"] = max(3, min(60, as_int(cfg.get("timeout"), 15)))
    cfg["title_max"] = max(8, min(120, as_int(cfg.get("title_max"), 24)))
    cfg["page_size"] = max(1, min(100, as_int(cfg.get("page_size"), 50)))
    cfg["max_pages"] = max(1, min(20, as_int(cfg.get("max_pages"), 5)))
    circles = cfg.get("circles")
    if not isinstance(circles, list) or not circles:
        raise ForumError("配置里没有可用的 circles")
    norm = []
    for c in circles[:20]:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        norm.append({
            "id": str(c["id"]),
            "name": str(c.get("name") or c["id"]),
            "aliases": [str(x) for x in (c.get("aliases") or [])],
        })
    if not norm:
        raise ForumError("circles 里没有有效圈子 ID")
    cfg["circles"] = norm
    return cfg


def resolve_schools(cfg, word):
    w = str(word or "").strip().lower()
    if w in tuple(x.lower() for x in ALL_WORDS):
        return cfg["circles"]
    for c in cfg["circles"]:
        pool = [c["name"], c["id"]] + c["aliases"]
        if any(str(x).strip().lower() == w for x in pool):
            return [c]
    for c in cfg["circles"]:
        pool = [c["name"]] + c["aliases"]
        if any(w and w in str(x).strip().lower() for x in pool):
            return [c]
    raise ForumError("不认识的学校「%s」。用 schools 查看可用名称与别名。" % word)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def visible(posts, show_author):
    """默认作者打码；不改变原始数据。"""
    if show_author:
        return posts
    out = []
    for p in posts:
        q = dict(p)
        q["author"] = mask_author(p.get("author"))
        out.append(q)
    return out


def make_result(command, meta, posts=None, extra=None):
    r = {"command": command, "fetched_at": now_str(), "meta": meta}
    if posts is not None:
        r["posts"] = posts
    if extra:
        r.update(extra)
    return r


def posts_text(title, note, posts, errors, show_author):
    lines = [title, ""]
    if note:
        lines += [note, ""]
    for i, p in enumerate(posts, 1):
        author = p.get("author") if show_author else mask_author(p.get("author"))
        lines.append("%2d. [%s·%s] %s" % (i, p.get("school"), p.get("tag") or "未分类", p.get("title")))
        lines.append("     热度 %-6s 评论 %-4s %s  作者 %s  id=%s" % (
            p.get("heat"), p.get("comments"), p.get("time"), author, p.get("id")))
    if not posts:
        lines.append("（没有取到帖子）")
    if errors:
        lines += ["", "失败学校（不影响其他学校）："]
        lines += ["  - %s：%s" % (e["school"], e["error"]) for e in errors]
    return "\n".join(lines)


def cmd_schools(args, cfg):
    lines = ["登记学校（%d 所）" % len(cfg["circles"]), ""]
    for c in cfg["circles"]:
        lines.append("  %-6s  %s" % (c["name"], c["id"]))
        lines.append("          别名：%s" % ("、".join(c["aliases"]) or "无"))
    lines += ["", "指定学校用 --school <简称/别名/ID>；省略即全部学校。"]
    return make_result("schools", {"circles": cfg["circles"]}), "\n".join(lines)


def cmd_latest(args, cfg):
    schools = resolve_schools(cfg, getattr(args, "school", ""))
    limit = max(1, min(200, as_int(getattr(args, "limit", None), 20)))
    page_size = max(20, min(50, limit * 2))
    posts, errors, totals, scanned = fetch_all(cfg, schools, 1, page_size)
    posts.sort(key=lambda p: (p["time"], p["heat"]), reverse=True)
    posts = posts[:limit]
    note = "口径：%d 所学校最近取样（每校最多 %d 条，实扫 %d 条），按发帖时间倒序返回前 %d 条。" % (
        len(schools), page_size, scanned, len(posts))
    meta = {"circles": [s["name"] for s in schools], "sample_per_school": page_size,
            "scanned": scanned, "returned": len(posts), "records_total": totals,
            "errors": errors, "note": note}
    return (make_result("latest", meta, visible(posts, args.show_author)),
            posts_text("最新帖子", note, posts, errors, args.show_author))


def cmd_hot(args, cfg):
    schools = resolve_schools(cfg, getattr(args, "school", ""))
    limit = max(1, min(200, as_int(getattr(args, "limit", None), 10)))
    page_size = max(20, min(50, max(20, limit * 3)))
    posts, errors, totals, scanned = fetch_all(cfg, schools, 1, page_size)
    posts.sort(key=lambda p: (p["heat"], p["time"]), reverse=True)
    posts = posts[:limit]
    note = ("口径：取样热榜，不是全站十大（ten/page 需登录，返回「请先登录」）。"
            "%d 所学校每校最多 %d 条、实扫 %d 条，按 totalHeatNum 降序返回前 %d 条。" % (
                len(schools), page_size, scanned, len(posts)))
    meta = {"circles": [s["name"] for s in schools], "sample_per_school": page_size,
            "scanned": scanned, "returned": len(posts), "records_total": totals,
            "errors": errors, "note": note, "is_global_top_ten": False}
    return (make_result("hot", meta, visible(posts, args.show_author)),
            posts_text("热门帖子（取样热榜）", note, posts, errors, args.show_author))


def run_search(args, cfg, limit, pages=None, note_prefix=""):
    kw = str(getattr(args, "keyword", "") or "").strip()
    if not kw:
        raise ForumError("search / watch / wechat 需要 --keyword")
    schools = resolve_schools(cfg, getattr(args, "school", ""))
    pages = max(1, min(20, as_int(pages or getattr(args, "pages", None), cfg["max_pages"])))
    page_size = cfg["page_size"]
    posts, errors, totals, scanned = fetch_all(cfg, schools, pages, page_size, keyword=kw)
    posts.sort(key=lambda p: (p["heat"], p["time"]), reverse=True)
    hits = sum(totals.values())
    out = posts[:limit]
    note = ("%s口径：服务端 keyword 检索「%s」，接口命中约 %d 条 / 本次扫描 %d 条 / "
            "返回热度前 %d 条（每校最多 %d 页 × %d 条；命中不足单页时自动停止翻页）。"
            % (note_prefix, kw, hits, scanned, len(out), pages, page_size))
    meta = {"keyword": kw, "circles": [s["name"] for s in schools],
            "records_total": totals, "hit_total": hits, "scanned": scanned,
            "pages_per_school": pages, "page_size": page_size, "returned": len(out),
            "errors": errors, "note": note}
    return out, meta


def cmd_search(args, cfg):
    limit = max(1, min(200, as_int(getattr(args, "limit", None), 10)))
    posts, meta = run_search(args, cfg, limit)
    return (make_result("search", meta, visible(posts, args.show_author)),
            posts_text("关键词搜索：%s" % meta["keyword"], meta["note"], posts,
                       meta["errors"], args.show_author))


def cmd_detail(args, cfg):
    pid = str(getattr(args, "id", "") or "").strip()
    if not pid:
        raise ForumError("detail 需要 --id <帖子ID>")
    raw = http_get(cfg["base"], P_DETAIL, {"id": pid}, cfg["timeout"])
    d = unwrap_detail(raw)
    content = str(pick(d, FIELDS["content"], "") or "")
    author = str(pick(d, FIELDS["author"], "") or "")
    if not args.show_author:
        author = mask_author(author)
    pics = d.get("pics") or d.get("picList") or []
    comment_list = d.get("commentList")
    info = {
        "id": str(pick(d, FIELDS["id"], pid) or pid),
        "title": summarize(content, cfg["title_max"]),
        "content": content,
        "author": author,
        "tag": tag_of(d),
        "heat": as_int(pick(d, FIELDS["heat"], 0)),
        "comments": as_int(pick(d, FIELDS["comments"], 0)),
        "time": str(pick(d, FIELDS["time"], "") or "")[:30],
        "circle_title": str(pick(d, FIELDS["circle_title"], "") or "")[:40],
        "pic_count": len(pics) if isinstance(pics, (list, tuple)) else 0,
        "comment_list_available": bool(comment_list),
        "field_count": len(d),
    }
    lines = ["帖子详情：%s" % info["id"], "",
             "  标题    %s" % info["title"],
             "  正文    %s" % (content[:500] or "（空）"),
             "  标签    %s" % info["tag"],
             "  作者    %s" % info["author"],
             "  时间    %s" % info["time"],
             "  热度    %s    评论数 %s" % (info["heat"], info["comments"]),
             "  圈子    %s    图片 %s 张" % (info["circle_title"], info["pic_count"]),
             "  返回字段 %s 个" % info["field_count"], "",
             "  评论内容：接口 commentList 实测为空，只能看到评论数，不提供回复文本。"]
    meta = {"note": "详情匿名可读；commentList 实测为空，不展示回复文本。",
            "show_author": bool(args.show_author)}
    result = make_result("detail", meta, extra={"detail": info})
    if args.json:
        result["detail_raw"] = d
    return result, "\n".join(lines)


def cmd_compare(args, cfg):
    schools = cfg["circles"]
    rows, errors = [], []
    for s in schools:
        try:
            posts, total, scanned = fetch_school(cfg, s, 1, 50)
            heats = [p["heat"] for p in posts]
            hours = {}
            for p in posts:
                m = re.search(r"\s(\d{2}):", p["time"])
                if m:
                    h = m.group(1)
                    hours[h] = hours.get(h, 0) + 1
            busy = sorted(hours.items(), key=lambda x: -x[1])[:1]
            rows.append({
                "school": s["name"], "circle_id": s["id"], "sampled": len(posts),
                "records_total": total, "heat_sum": sum(heats),
                "heat_avg": round(sum(heats) / len(heats), 1) if heats else 0,
                "heat_max": max(heats) if heats else 0,
                "top_title": max(posts, key=lambda p: p["heat"])["title"] if posts else "",
                "latest": max([p["time"] for p in posts], default=""),
                "busy_hour": (busy[0][0] + "时") if busy else "无",
            })
        except ForumError as e:
            errors.append({"school": s["name"], "id": s["id"], "error": str(e)})
    lines = ["四校对比（基于最近取样，每校最多 50 条）", "",
             "%-8s %8s %8s %10s %10s %10s %s" % (
                 "学校", "取样", "帖子总数", "热度合计", "平均热度", "最高热度", "最活跃时段"),
             "%-8s %8s %8s %10s %10s %10s %s" % ("-" * 6, "-" * 6, "-" * 8,
                                                  "-" * 8, "-" * 8, "-" * 8, "-" * 8)]
    for r in rows:
        lines.append("%-8s %8d %8d %10d %10.1f %10d %s" % (
            r["school"], r["sampled"], r["records_total"], r["heat_sum"],
            r["heat_avg"], r["heat_max"], r["busy_hour"]))
    lines += ["", "各校最高热帖："]
    for r in rows:
        lines.append("  %-6s %4d  %s" % (r["school"], r["heat_max"], r["top_title"]))
    if errors:
        lines += ["", "失败学校："] + ["  - %s：%s" % (e["school"], e["error"]) for e in errors]
    note = "口径：每校最近取样最多 50 条，非全量统计；帖子总数来自接口 recordsTotal。"
    meta = {"note": note, "errors": errors, "circles": [s["name"] for s in schools]}
    return make_result("compare", meta, extra={"rows": rows}), "\n".join(lines)


def cmd_report(args, cfg):
    days = max(1, min(30, as_int(getattr(args, "days", None), 1)))
    page_size = min(50, max(20, days * 20))
    posts, errors, totals, scanned = fetch_all(cfg, cfg["circles"], 1, page_size)
    note = ("口径：接口没有时间范围参数，--days %d 只影响取样量（每校最多 %d 条）；"
            "结果基于最近取样帖，不是精确按自然日汇总。" % (days, page_size))
    lines = ["豚说论坛日报素材（%s）" % now_str(), "", note, ""]
    for s in cfg["circles"]:
        group = [p for p in posts if p["school"] == s["name"]]
        group.sort(key=lambda p: (p["heat"], p["time"]), reverse=True)
        lines.append("【%s】取样 %d 条 / 圈子总数 %s" % (
            s["name"], len(group), totals.get(s["name"], "?")))
        for p in group[:5]:
            lines.append("   %5d  %s·%s  %s" % (p["heat"], p["school"], p["tag"], p["title"]))
        if not group:
            lines.append("   （无帖子，可能是空圈子）")
        lines.append("")
    hot = sorted(posts, key=lambda p: p["heat"], reverse=True)[:5]
    lines += ["全局热度前 5（取样热榜，非全站十大）："]
    for p in hot:
        lines.append("   %5d  %s·%s  %s" % (p["heat"], p["school"], p["tag"], p["title"]))
    if errors:
        lines += ["", "失败学校："] + ["  - %s：%s" % (e["school"], e["error"]) for e in errors]
    meta = {"note": note, "days": days, "sample_per_school": page_size,
            "scanned": scanned, "records_total": totals, "errors": errors,
            "circles": [s["name"] for s in cfg["circles"]]}
    return (make_result("report", meta, visible(posts, args.show_author)),
            "\n".join(lines))


CSV_FIELDS = ["id", "school", "circle_id", "tag", "title", "content",
              "heat", "comments", "time", "author", "circle_title"]


def csv_bytes(posts, show_author):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    w.writeheader()
    for p in visible(posts, show_author):
        row = {k: p.get(k, "") for k in CSV_FIELDS}
        row["content"] = str(row["content"]).replace("\r", " ").replace("\n", " ")
        w.writerow(row)
    return buf.getvalue()


def cmd_export(args, cfg):
    out = str(getattr(args, "out", "") or "").strip()
    if not out:
        raise ForumError("export 需要 --out <路径>，本技能不写默认位置")
    out = os.path.abspath(os.path.expanduser(out))
    parent = os.path.dirname(out)
    if not os.path.isdir(parent):
        raise ForumError("输出目录不存在：%s（请先创建，本技能不自动建目录）" % parent)
    if os.path.exists(out) and not os.path.isfile(out):
        raise ForumError("输出路径不是普通文件：%s" % out)
    posts, errors, totals, scanned = fetch_all(cfg, cfg["circles"], 1, cfg["page_size"])
    data = csv_bytes(posts, args.show_author)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        f.write(data)
    note = "口径：%d 所学校每校最多 %d 条，实扫 %d 条，导出全部合并去重结果。" % (
        len(cfg["circles"]), cfg["page_size"], scanned)
    text = "已导出 %d 条 → %s\n%s\n（UTF-8 BOM，Excel 直接打开不乱码）" % (len(posts), out, note)
    if errors:
        text += "\n失败学校：" + "、".join(e["school"] for e in errors)
    meta = {"note": note, "out": out, "rows": len(posts), "scanned": scanned,
            "records_total": totals, "errors": errors}
    return make_result("export", meta), text


def cmd_watch(args, cfg):
    state_path = str(getattr(args, "state", "") or "").strip()
    limit = max(1, min(100, as_int(getattr(args, "limit", None), 20)))
    posts, meta = run_search(args, cfg, limit, pages=2,
                             note_prefix="关键词预警（只读，不写默认文件）。")
    seen = []
    if state_path:
        sp = os.path.abspath(os.path.expanduser(state_path))
        if os.path.isfile(sp):
            try:
                seen = list(read_json(sp).get("seen") or [])
            except (ValueError, OSError):
                seen = []
        fresh = [p for p in posts if p["id"] not in seen]
        seen = (seen + [p["id"] for p in fresh])[-1000:]
        with open(sp, "w", encoding="utf-8") as f:
            json.dump({"seen": seen, "updated_at": now_str()}, f, ensure_ascii=False, indent=2)
    else:
        fresh = posts
    meta["fresh_count"] = len(fresh)
    meta["state_written"] = bool(state_path)
    meta["note"] += " 本次新命中 %d 条。" % len(fresh)
    return (make_result("watch", meta, visible(fresh, args.show_author)),
            posts_text("关键词预警：%s" % meta["keyword"], meta["note"], fresh,
                       meta["errors"], args.show_author))


def cmd_wechat(args, cfg):
    """输出微信成文素材包；成文由调用方（AI）按用户提示完成。"""
    limit = max(3, min(50, as_int(getattr(args, "limit", None), 10)))
    kw = str(getattr(args, "keyword", "") or "").strip()
    if kw:
        posts, meta = run_search(args, cfg, limit, pages=2,
                                 note_prefix="微信成文素材包。")
    else:
        schools = resolve_schools(cfg, getattr(args, "school", ""))
        page_size = 50
        posts, errors, totals, scanned = fetch_all(cfg, schools, 1, page_size)
        posts.sort(key=lambda p: (p["heat"], p["time"]), reverse=True)
        posts = posts[:limit]
        meta = {"circles": [s["name"] for s in schools], "sample_per_school": page_size,
                "scanned": scanned, "returned": len(posts), "records_total": totals,
                "errors": errors,
                "note": "微信成文素材包。口径：取样热榜，不是全站十大；%d 所学校每校最多 %d 条，实扫 %d 条，按热度取前 %d 条。" % (
                    len(schools), page_size, scanned, len(posts))}
    by_school = {}
    for p in posts:
        by_school.setdefault(p["school"], []).append(p)
    stats = {
        "total_returned": len(posts),
        "by_school": {k: len(v) for k, v in by_school.items()},
        "heat_sum": sum(p["heat"] for p in posts),
        "heat_max": max([p["heat"] for p in posts], default=0),
        "tags": sorted({p["tag"] for p in posts if p["tag"]}),
    }
    lines = ["微信 / 公众号成文素材包", "", meta["note"], "",
             "统计：%s" % json.dumps(stats, ensure_ascii=False), ""]
    for name, group in by_school.items():
        lines.append("【%s】" % name)
        for p in group:
            lines.append("  · %s｜热度 %d｜%s｜%s" % (
                p["title"], p["heat"], p["time"], p["tag"]))
            lines.append("    正文：%s" % p["content"][:200].replace("\n", " "))
        lines.append("")
    lines += ["成文要求：只使用以上真实帖子，不编造标题、作者、时间、热度或链接；",
             "结尾标注数据口径、抓取时间与涉及学校；需要配图时交给插画技能。"]
    if meta.get("errors"):
        lines += ["", "失败学校："] + ["  - %s：%s" % (e["school"], e["error"]) for e in meta["errors"]]
    result = make_result("wechat", meta, visible(posts, args.show_author),
                         extra={"stats": stats, "by_school": {
                             k: [p["id"] for p in v] for k, v in by_school.items()}})
    return result, "\n".join(lines)


def cmd_my(args, cfg):
    text = ("「我发布的帖子 / 评论回复」暂未开放。\n\n"
            "原因：\n"
            "  1. 技术尚未提供「我的帖子列表」「评论/回复列表」接口；createId、userNo "
            "传参实测被忽略，detail 里 commentList 恒为空。\n"
            "  2. 需要登录态识别本人身份，本技能按约定不读取、不保存任何令牌。\n\n"
            "请勿编造个人帖子数据。接口到位后再补这个子命令。")
    return make_result("my", {"available": False, "note": text}), text


def cmd_selftest(args, cfg):
    checks = []

    def ck(name, cond):
        checks.append((name, bool(cond)))

    p1 = {"id": "111", "content": "https://x.com/a  奶茶 好喝 #校园# 推荐给大家",
          "tagList": [{"name": "日常求助"}], "userName": "张三",
          "totalHeatNum": "42", "createTime": "2026-11-11 10:00:00",
          "commentsNum": 3, "circleTitle": "浙外校友圈",
          "circleId": "1844924022131912706"}
    p2 = dict(p1, id="222", totalHeatNum=9, circleId="9999999999")
    p3 = dict(p1, id="111", totalHeatNum=7)
    school = cfg["circles"][0]

    ck("摘要去链接并限长", "http" not in summarize(p1["content"], 24)
       and len(summarize(p1["content"], 24)) <= 24)
    ck("摘要保留话题标记", "[校园]" in summarize("#校园# 奶茶好喝", 60))
    ck("标签取 tagList[0].name", tag_of(p1) == "日常求助")
    ck("标签兜底 circleTitle", tag_of({"circleTitle": "浙外校友圈"}) == "浙外校友圈")
    ck("热度字符串转整数", as_int("42") == 42)
    ck("热度异常值归零", as_int(None) == 0 and as_int("abc") == 0)
    ck("作者默认打码", mask_author("张三") == "张**" and mask_author("") == "匿名")
    n1 = normalize(p1, school, cfg)
    ck("字段映射齐全", all(k in n1 for k in CSV_FIELDS))
    ck("学校名写入", n1["school"] == school["name"])
    ck("防串校丢弃不匹配", len(filter_circle([p1, p2], school)) == 1)
    ck("无 circleId 不误杀", len(filter_circle([{"id": "x"}], school)) == 1)
    ck("按 id 去重", len(unique([n1, normalize(p3, school, cfg)])) == 1)
    ck("多校合并去重保留不同 id",
       len(unique([n1, normalize(dict(p1, id="333"), school, cfg)])) == 2)
    ck("正常响应解包", len(unwrap({"code": 200, "data": [p1], "recordsTotal": 1})[0]) == 1)
    ck("空圈子不报错", unwrap({"code": 200, "data": [], "recordsTotal": 0}) == ([], 0))
    ck("裸数组解包", unwrap([p1]) == ([p1], 0))
    try:
        unwrap({"code": 110, "message": "请先登录"})
        ck("110 抛登录异常", False)
    except ForumAuthError:
        ck("110 抛登录异常", True)
    try:
        unwrap({"code": 400, "message": "参数错误"})
        ck("400 抛普通异常", False)
    except ForumError:
        ck("400 抛普通异常", True)
    ck("详情对象解包", unwrap_detail({"code": 200, "data": p1}) == p1)
    ck("提前停止：不足单页", should_stop(3, 50, 3, 3))
    ck("提前停止：已扫满命中数", should_stop(50, 50, 50, 50))
    ck("继续翻页：命中数更多", not should_stop(50, 50, 200, 50))
    ck("别名精确解析", resolve_schools(cfg, "浙科大")[0]["name"] == "浙科")
    ck("别名精确解析 2", resolve_schools(cfg, "浙江工业大学")[0]["name"] == "浙工大")
    ck("circleId 精确解析", resolve_schools(cfg, cfg["circles"][0]["id"])[0]["name"] == cfg["circles"][0]["name"])
    ck("全部学校", len(resolve_schools(cfg, "全部")) == len(cfg["circles"]))
    try:
        resolve_schools(cfg, "不存在的学校xyz")
        ck("未知学校报错", False)
    except ForumError:
        ck("未知学校报错", True)
    ck("配置忽略注释字段", deep_merge({"a": 1}, {"_comment": "x", "a": 2}) == {"a": 2})
    ck("可见副本不改原作者", visible([n1], False)[0]["author"] == "张**"
       and n1["author"] == "张三")
    ck("CSV 表头与行数", csv_bytes([n1], False).count("\n") == 2
       and csv_bytes([n1], False).startswith("id,school"))
    ck("圈子数上限", len(cfg["circles"]) <= 20)
    ck("base 是 http(s)", str(cfg["base"]).startswith("https://"))

    failed = [n for n, ok in checks if not ok]
    lines = ["离线自测：%d 项，通过 %d 项" % (len(checks), len(checks) - len(failed))]
    if failed:
        lines += ["失败项："] + ["  - " + n for n in failed]
    else:
        lines.append("全部通过（未发送任何网络请求）。")
    return make_result("selftest", {"passed": len(checks) - len(failed),
                                    "total": len(checks), "failed": failed}), "\n".join(lines)


COMMANDS = {
    "schools": cmd_schools,
    "latest": cmd_latest,
    "hot": cmd_hot,
    "search": cmd_search,
    "detail": cmd_detail,
    "compare": cmd_compare,
    "report": cmd_report,
    "export": cmd_export,
    "watch": cmd_watch,
    "wechat": cmd_wechat,
    "my": cmd_my,
    "selftest": cmd_selftest,
}


def build_parser():
    p = argparse.ArgumentParser(
        description="豚说论坛只读查询（FKskill / tuntun-forum）。所有参数位置随意。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="命令：" + ", ".join(COMMANDS))
    p.add_argument("command", nargs="?", default="latest", choices=sorted(COMMANDS))
    p.add_argument("--school", default="", help="学校简称/别名/circleId；省略=全部")
    p.add_argument("--limit", type=int, default=None, help="返回条数")
    p.add_argument("--keyword", default="", help="关键词（search/watch/wechat）")
    p.add_argument("--id", default="", help="帖子 ID（detail）")
    p.add_argument("--out", default="", help="CSV 输出路径（export，必填）")
    p.add_argument("--days", type=int, default=None, help="日报取样天数")
    p.add_argument("--pages", type=int, default=None, help="每校最大翻页数")
    p.add_argument("--state", default="", help="预警状态文件路径（watch，可选）")
    p.add_argument("--base", default="", help="覆盖接口域名")
    p.add_argument("--circle", default="", help="临时使用单个自建圈子 ID")
    p.add_argument("--name", default="", help="与 --circle 搭配的学校简称")
    p.add_argument("--timeout", type=int, default=None, help="请求超时秒数")
    p.add_argument("--show-author", action="store_true", help="显示作者原名（默认打码）")
    p.add_argument("--json", action="store_true", help="输出结构化 JSON")
    return p


def output(result, text, args):
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(text)


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args)
        result, text = COMMANDS[args.command](args, cfg)
        output(result, text, args)
        return 0
    except ForumAuthError as e:
        print("需要登录态：%s（本技能应自动降级，检查是否误用了需登录接口）" % e, file=sys.stderr)
        return 2
    except ForumError as e:
        print("错误：%s" % e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
