#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从「金句池1000条.txt」随机抽 N 条，生成一份干净的 RSS 2.0 XML。
同时兼容 Dashy rss-feed 与通用 RSS 阅读器。

★ 唯一数据源就是 TXT，没有第二份池子。
   改内容 → 只编辑 金句池1000条.txt → commit / push
   GitHub Actions 每次运行都会重新读这份 TXT，定时配置一行都不用改。

TXT 格式：一行一条「金句 + 出处」，下面几种分隔都认（按优先级）：
    金句 | 出处              ← 推荐
    金句<Tab>出处            ← Excel 复制两列直接粘贴
    金句  出处               ← 两个以上空格
    金句 —— 出处             ← 破折号前后带空格
    金句 出处                ← 单个空格（按最后一个空格切）
   · 以 # 开头的是注释，空行忽略，随便写备注
   · 不写编号：按行序自动生成 id，加行 / 删行 / 改行都不用手调
   · 正文里别出现竖线；出处尽量带《篇名或书名》

用法：
    python3 生成feed.py                       # 默认：抽 1 条，写 guid，不写 pubDate
    python3 生成feed.py --check               # 只校验 TXT，不写任何文件（改完先自查）
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
   都会被当成新文章，攒出一堆一模一样的卡片。guid 取自行号，稳定唯一。
   Dashy 的 RssParser.js 根本不读 guid，所以对 widget 零影响。
   ⚠️ 因此改 TXT 时尽量追加到末尾，别在中间插行（会让后面 guid 整体位移）。

其他：
  - channel 的 lastBuildDate 是源级元信息，RssParser.js 不读，不影响 Dashy 显示。
  - <description> 放「—— 出处」小字。
  - 默认避开上一次抽中的条目，保证每跑一次一定换一条。
"""

import argparse
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
TXT_FILE = BASE / "金句池1000条.txt"
OUT_FILE = BASE / "feed.xml"
LAST_FILE = BASE / ".last_id"

FEED_TITLE = "一句 · 旷野与自由"
FEED_LINK = "https://github.com/cary-jjw/jinju-RSS/tree/main"

GUID_PREFIX = "jinju-rss-quote-"
GUID_FIXED = "jinju-rss-quote-current"


def render_xml(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def read_txt(path: Path) -> str:
    """兼容 Excel 另存的 UTF-8 BOM / GBK 文本。"""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def split_line(line: str):
    """按优先级识别分隔符，返回 (正文, 出处, 分隔符名)。"""
    if "|" in line:
        parts = line.split("|", 1)
        return parts[0].strip(), parts[1].strip(), "|"
    if "\t" in line:
        parts = line.split("\t", 1)
        return parts[0].strip(), parts[1].strip(), "Tab"
    if re.search(r" {2,}", line):
        parts = re.split(r" {2,}", line, maxsplit=1)
        return parts[0].strip(), parts[1].strip(), "多空格"
    if " —— " in line or " -- " in line:
        parts = re.split(r" —— | -- ", line, maxsplit=1)
        return parts[0].strip(), parts[1].strip(), "破折号"
    if " " in line:
        head, tail = line.rsplit(" ", 1)
        return head.strip(), tail.strip(), "单空格"
    return None, None, None


def parse_txt(path: Path):
    """一行一条。返回 (池子, 警告列表, 分隔符统计)。"""
    pool, warnings, seps = [], [], {}
    for line_no, raw in enumerate(read_txt(path).splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        text, source, sep = split_line(line)
        if sep is None:
            warnings.append(f"第 {line_no} 行没找到分隔符，已跳过：{line[:30]}")
            continue
        if not text or not source:
            warnings.append(f"第 {line_no} 行正文或出处为空，已跳过：{line[:30]}")
            continue
        seps[sep] = seps.get(sep, 0) + 1
        if "|" in text or "|" in source:
            warnings.append(f"第 {line_no} 行正文/出处里含竖线，可能被截断")
        if "《" not in source:
            warnings.append(f"第 {line_no} 行出处没带《》：{source[:30]}（仅提示，已保留）")
        if " " in source:
            warnings.append(f"第 {line_no} 行出处含空格，空格分隔可能切歪：{source[:30]}")
        pool.append({"id": len(pool) + 1, "text": text, "source": source})
    return pool, warnings, seps


def validate_pool(pool):
    seen, dup = set(), []
    for q in pool:
        if q["text"] in seen:
            dup.append(q["id"])
        seen.add(q["text"])
    return {
        "条数": len(pool),
        "编号连续": [q["id"] for q in pool] == list(range(1, len(pool) + 1)),
        "正文重复编号": dup,
        "出处空值": sum(not q["source"] for q in pool),
        "出处带书名号": sum("《" in q["source"] for q in pool),
    }


def load_pool():
    """只有 TXT 一个数据源；缺文件直接给明确报错。"""
    if not TXT_FILE.exists():
        raise SystemExit(
            f"[error] 找不到 {TXT_FILE.name} —— 它是唯一要维护的文件，"
            "请确认已上传到仓库根目录"
        )
    return parse_txt(TXT_FILE)


def check():
    """只校验，不写任何文件。"""
    pool, warnings, seps = load_pool()
    report = validate_pool(pool)
    print(f"数据源：{TXT_FILE.name}  （{TXT_FILE.stat().st_size} 字节，唯一数据源）")
    print(f"有效条目：{report['条数']} 条")
    print(f"编号连续：{'是' if report['编号连续'] else '否'}   "
          f"出处带《》：{report['出处带书名号']}/{report['条数']}   "
          f"出处空值：{report['出处空值']}")
    print("分隔符统计：" + " / ".join(f"{k} {v} 行" for k, v in sorted(seps.items())))
    if report["正文重复编号"]:
        print(f"⚠️ 正文重复（行号）：{report['正文重复编号'][:20]}")
    for w in warnings[:30]:
        print(f"⚠️ {w}")
    if len(warnings) > 30:
        print(f"⚠️ 另有 {len(warnings) - 30} 条提示未列出")
    ok = not warnings and not report["正文重复编号"] and not report["出处空值"]
    print(f"校验：{'通过 ✅' if ok else '有提示，见上方（不阻断运行）'}")
    print("\n[check] 未写入任何文件")
    return pool


def build(n: int, seed=None, guid_mode="by-id", with_date=False, with_link=False) -> None:
    pool, warnings, _ = load_pool()
    if not pool:
        raise SystemExit("[error] 池子为空：检查 TXT 格式（每行要有正文 + 出处）")
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
        ET.SubElement(item, "description").text = f"—— {q['source']}"

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

    print(f"[ok] 数据源 {TXT_FILE.name}（唯一） | 已写入 {OUT_FILE}  "
          f"抽取 {len(picked)} / {len(pool)} 条  "
          f"guid={guid_mode}  pubDate={'有' if with_date else '无（Dashy 不显示日期）'}")
    for q in picked:
        print(f"  #{q['id']:04d} {q['text']}  —— {q['source']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="从 TXT 随机抽金句生成 RSS（兼容 Dashy 与通用阅读器）")
    ap.add_argument("--check", action="store_true", help="只校验 TXT，不写任何文件")
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

    if args.check:
        check()
        raise SystemExit(0)

    if args.n < 1:
        ap.error("--n 至少为 1")
    if args.guid_mode == "fixed" and args.n > 1:
        print("[warn] fixed 模式下多条 item 共用同一 guid，阅读器会去重成 1 条；建议配合 --n 1")
    build(args.n, args.seed, args.guid_mode, args.with_date, args.with_link)
