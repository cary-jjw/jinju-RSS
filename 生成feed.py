#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从「金句池1000条.json」随机抽 N 条，生成一份干净的 RSS 2.0 XML。
同时兼容 Dashy rss-feed 与通用 RSS 阅读器。

用法：
    python3 生成feed.py                       # 默认：抽 1 条，写 guid，不写 pubDate
    python3 生成feed.py --n 5                 # 抽 5 条
    python3 生成feed.py --seed 42             # 固定随机种子，复现同一批
    python3 生成feed.py --guid-mode fixed     # 阅读器里永远只保留 1 条
    python3 生成feed.py --with-date           # 额外写 pubDate（Dashy 会显示日期，一般不推荐）
    python3 生成feed.py --with-link           # 为每条写入 link（Dashy 会多一个按钮）

两个关键取舍：

1) 默认不写 <item><pubDate>
   Dashy 的 RssFeed.vue 会把 pubDate 交给 formatDate()，用
   toLocaleDateString(..., {weekday:'short', day:'numeric', month:'short'})
   渲染成「11月5日周四」这种小字。用户明确不要这行，所以从源头去掉，
   不依赖 CSS 兜底。想要阅读器显示真实时间时才用 --with-date。

2) 默认写 <item><guid isPermaLink="false">
   RSS 阅读器靠 guid 去重。没有它（且没有 link / pubDate）时，每次抓取
   都会被当成新文章，攒出一堆一模一样的卡片。guid 取自金句编号，稳定唯一。
   Dashy 的 RssParser.js 根本不读 guid，所以对 widget 零影响。

其他：
  - channel 的 lastBuildDate 是源级元信息，RssParser.js 不读，不影响 Dashy 显示。
  - <description> 放「—— 出处」小字；池子若带 tag 字段会额外显示〔分级〕，
    用 .get 兼容精简池子（当前池子只有 id / text / source）。
  - 默认避开上一次抽中的条目，保证每跑一次一定换一条。
"""

import argparse
import json
import random
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
POOL_FILE = BASE / "金句池1000条.json"
OUT_FILE = BASE / "feed.xml"
LAST_FILE = BASE / ".last_id"

FEED_TITLE = "一句 · 旷野与自由"
FEED_LINK = "https://github.com/cary-jjw/jinju-RSS/tree/main"

GUID_PREFIX = "jinju-rss-quote-"
GUID_FIXED = "jinju-rss-quote-current"


def render_xml(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def build(n: int, seed=None, guid_mode="by-id", with_date=False, with_link=False) -> None:
    pool = json.loads(POOL_FILE.read_text(encoding="utf-8"))
    rnd = random.Random(seed)

    # 尽量不与上一次重复
    last = LAST_FILE.read_text(encoding="utf-8").strip() if LAST_FILE.exists() else ""
    candidates = [q for q in pool if str(q["id"]) != last] or pool
    picked = rnd.sample(candidates, min(n, len(candidates)))

    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = FEED_TITLE
    ET.SubElement(ch, "link").text = FEED_LINK
    ET.SubElement(ch, "description").text = (
        f"每 5 分钟随机换{'一条' if n == 1 else str(n) + '条'} · 旷野 / 自由 / 热爱 / 平凡 / 治愈"
    )
    ET.SubElement(ch, "language").text = "zh-CN"
    ET.SubElement(ch, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))

    now = format_datetime(datetime.now(timezone.utc)) if with_date else ""
    for q in picked:
        item = ET.SubElement(ch, "item")
        ET.SubElement(item, "title").text = q["text"]
        tag = q.get("tag", "")
        suffix = f" 〔{tag}〕" if tag else ""
        ET.SubElement(item, "description").text = f"—— {q['source']}{suffix}"

        # 稳定唯一标识，供 RSS 阅读器去重。isPermaLink="false" 必须声明，
        # 否则部分阅读器会把 guid 当 URL 打开。
        if guid_mode == "by-id":
            guid = f"{GUID_PREFIX}{q['id']:04d}"
        elif guid_mode == "fixed":
            guid = GUID_FIXED
        else:
            guid = ""
        if guid:
            ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = guid

        if with_link:
            ET.SubElement(item, "link").text = FEED_LINK
        # 默认不写 pubDate —— Dashy 不会显示日期
        if with_date:
            ET.SubElement(item, "pubDate").text = now

    OUT_FILE.write_text(render_xml(rss) + "\n", encoding="utf-8")
    LAST_FILE.write_text(str(picked[0]["id"]), encoding="utf-8")

    print(f"[ok] 已写入 {OUT_FILE}  抽取 {len(picked)} / {len(pool)} 条  "
          f"guid={guid_mode}  pubDate={'有' if with_date else '无（Dashy 不显示日期）'}")
    for q in picked:
        tag = q.get("tag", "")
        mark = f" 〔{tag}〕" if tag else " "
        print(f"  #{q['id']:04d}{mark}{q['text']}  —— {q['source']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="生成随机金句 RSS XML（兼容 Dashy 与通用阅读器）")
    ap.add_argument("--n", type=int, default=1, help="抽取条数，默认 1")
    ap.add_argument("--seed", type=int, default=None, help="固定随机种子，默认不固定")
    ap.add_argument(
        "--guid-mode", choices=["by-id", "fixed", "none"], default="by-id",
        help="by-id(默认)=每句只入库一次；fixed=永远只 1 条；none=不写 guid（会重复，别用）",
    )
    ap.add_argument("--with-date", action="store_true",
                    help="写入 item/pubDate；Dashy 会渲染出日期，默认关闭")
    ap.add_argument("--with-link", action="store_true",
                    help="写入 item/link；Dashy 会多一个「打开链接」按钮，默认关闭")
    args = ap.parse_args()
    if args.n < 1:
        ap.error("--n 至少为 1")
    if args.guid_mode == "fixed" and args.n > 1:
        print("[warn] fixed 模式下多条 item 共用同一 guid，阅读器会去重成 1 条；建议配合 --n 1")
    build(args.n, args.seed, args.guid_mode, args.with_date, args.with_link)
