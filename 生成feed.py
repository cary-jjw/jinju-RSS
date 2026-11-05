#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从「金句池1000条.json」随机抽 N 条，生成 Dashy rss-feed 可直接读取的 RSS 2.0 XML。

用法：
    python3 生成feed.py            # 默认抽 1 条，写 feed.xml
    python3 生成feed.py --n 5      # 抽 5 条
    python3 生成feed.py --seed 42  # 固定随机种子（复现同一批，一般不用）

设计要点（对应 Dashy RssFeed.vue 的本地解析器）：
  - 不写 <pubDate>：formatDate() 返回空串，界面不会出现「按时间线排序」的错觉；
    加 --with-date 可写入生成时刻（parseLocally 下它也不参与排序）。
  - 不写 <item><link>：组件会渲染成 div 而非 a，也不会生成「打开链接」按钮，
    widget 里只剩「一行金句 + 一行小字出处」，最干净；加 --with-link 可写仓库链接。
  - 出处与分级放在 <description>，由 post-body 以小字渲染。
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
FEED_LINK = "https://github.com/你的用户名/你的仓库"


def esc_free_xml(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def build(n: int, seed=None, with_date=False, with_link=False) -> None:
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

    now = format_datetime(datetime.now(timezone.utc)) if with_date else ""
    for q in picked:
        item = ET.SubElement(ch, "item")
        ET.SubElement(item, "title").text = q["text"]
        ET.SubElement(item, "description").text = f"—— {q['source']} 〔{q['tag']}〕"
        if with_link:
            ET.SubElement(item, "link").text = FEED_LINK
        if with_date:
            ET.SubElement(item, "pubDate").text = now

    OUT_FILE.write_text(esc_free_xml(rss) + "\n", encoding="utf-8")
    LAST_FILE.write_text(str(picked[0]["id"]), encoding="utf-8")

    print(f"[ok] 已写入 {OUT_FILE}  抽取 {len(picked)} / {len(pool)} 条")
    for q in picked:
        print(f"  #{q['id']:04d} 〔{q['tag']}〕{q['text']}  —— {q['source']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="生成 Dashy 随机金句 RSS XML")
    ap.add_argument("--n", type=int, default=1, help="抽取条数，默认 1")
    ap.add_argument("--seed", type=int, default=None, help="固定随机种子，默认不固定")
    ap.add_argument("--with-date", action="store_true", help="写入 pubDate")
    ap.add_argument("--with-link", action="store_true", help="为每条写入 link")
    args = ap.parse_args()
    if args.n < 1:
        ap.error("--n 至少为 1")
    build(args.n, args.seed, args.with_date, args.with_link)
