#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从「金句池1000条.json」随机抽 N 条，生成 RSS 2.0 XML。
同时兼容 Dashy rss-feed 与通用 RSS 阅读器（Fluent Reader / Feedly 等）。

用法：
    python3 生成feed.py                    # 默认抽 1 条，guid 按金句 id
    python3 生成feed.py --n 5              # 抽 5 条
    python3 生成feed.py --seed 42          # 固定随机种子（复现同一批，一般不用）
    python3 生成feed.py --guid-mode fixed  # 固定 guid，阅读器里永远只有 1 条
    python3 生成feed.py --guid-mode none   # 回到旧行为：不写 guid / pubDate（仅供 Dashy）
    python3 生成feed.py --no-date          # 写 guid 但不写 pubDate

为什么必须有 guid（重要）：
    RSS 阅读器靠 <guid> 给条目去重。之前只有 1 个 <item> 且没写 guid / link /
    pubDate，阅读器每次抓取都把同一句当成「新文章」插进本地库，结果就是刷出
    十几张一模一样的卡片、时间全显示 now。Dashy 的 widget 每次拉一次覆盖渲染、
    没有历史库，所以不受影响 —— 这是通用阅读器才暴露出来的问题。

guid 两种模式的取舍：
    by-id  (默认) guid = jinju-rss-quote-0473：同一句无论抓多少次只入库一次，
                   换一句才新增一条，形成不重复的历史金句流。最稳，不依赖
                   阅读器是否实现了「同 guid 更新内容」。
    fixed       guid = jinju-rss-quote-current：阅读器里永远只有 1 条，内容随
                   抓取更新，最贴近「只显示 1 条」的初衷。但少数阅读器不实现
                   upsert，可能一直停在旧句子 —— 遇到这种情况改用 by-id。
                   fixed 模式请配合 --n 1。

其他设计要点（对应 Dashy RssFeed.vue 的本地解析器）：
  - <pubDate> 只影响阅读器显示时间和去重辅助；parseLocally 下它不参与排序。
    Dashy 会多渲染一行日期，用 customCss 隐藏 .post-date 即可。
  - 不写 <item><link>：组件会渲染成 div 而非 a，也不会生成「打开链接」按钮，
    widget 里只剩「一行金句 + 一行小字出处」；加 --with-link 可写仓库链接。
  - 出处放在 <description>，由 post-body 以小字渲染；池子若带 tag 字段则
    额外显示〔分级〕，不带也不影响（用 .get 兼容两种池子）。
  - Dashy 的 RssParser.js 不读取 <guid>，加这个字段对它零影响。
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


def build(n: int, seed=None, guid_mode="by-id", no_date=False, with_link=False) -> None:
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

    write_date = guid_mode != "none" and not no_date
    now = format_datetime(datetime.now(timezone.utc)) if write_date else ""
    for q in picked:
        item = ET.SubElement(ch, "item")
        ET.SubElement(item, "title").text = q["text"]
        tag = q.get("tag", "")
        suffix = f" 〔{tag}〕" if tag else ""
        ET.SubElement(item, "description").text = f"—— {q['source']}{suffix}"

        # 关键：稳定且唯一的条目标识，供 RSS 阅读器去重
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
        if write_date:
            ET.SubElement(item, "pubDate").text = now

    OUT_FILE.write_text(render_xml(rss) + "\n", encoding="utf-8")
    LAST_FILE.write_text(str(picked[0]["id"]), encoding="utf-8")

    print(f"[ok] 已写入 {OUT_FILE}  抽取 {len(picked)} / {len(pool)} 条  guid={guid_mode}  pubDate={'有' if write_date else '无'}")
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
        help="by-id(默认)=每句只入库一次；fixed=永远只 1 条；none=旧行为仅供 Dashy",
    )
    ap.add_argument("--no-date", action="store_true", help="不写 pubDate（应对把时间算进去重指纹的阅读器）")
    ap.add_argument("--with-link", action="store_true", help="为每条写入 link")
    args = ap.parse_args()
    if args.n < 1:
        ap.error("--n 至少为 1")
    if args.guid_mode == "fixed" and args.n > 1:
        print("[warn] fixed 模式下多条 item 共用同一 guid，阅读器会去重成 1 条；建议配合 --n 1")
    build(args.n, args.seed, args.guid_mode, args.no_date, args.with_link)
