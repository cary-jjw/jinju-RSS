# 金句 RSS XML · 使用说明

把「1000 条金句素材库」按前面讨论的思路，做成 Dashy rss-feed 每次只显示 1 条、每 5 分钟随机换一条的静态 XML 方案。

## 交付了什么

| 文件 | 作用 |
| --- | --- |
| `feed.xml` | 成品，直接可用。RSS 2.0，`<channel>` 里只有 1 个 `<item>` |
| `生成feed.py` | 随机抽 N 条重写 `feed.xml`，跑一次换一批 |
| `金句池1000条.json` | 结构化池子，1000 条，含 `text` / `source` / `tag` / `volume` |
| `使用说明.md` | 本文件 |

池子按原脚本的分级原则完整复现，去重后正好 1000 条：

| 分卷 | 条数 | 标签 |
| --- | --- | --- |
| 第一卷 · 古典诗文 | 108 | 可考 |
| 第二卷 · 中国现当代作家与作品 | 85 | 可考 |
| 第三卷 · 外国作家与哲人 | 99 | 可考 |
| 第四卷 · 电影与剧集台词 | 66 | 可考 |
| 第五卷 · 人民日报 / 央视等公开文案 | 180 | 媒体 |
| 第六卷 · 网传金句（出处存疑） | 41 | 网传 |
| 第七卷 · 原创仿写 | 421 | 原创 |

合计 可考 358 / 媒体 180 / 网传 41 / 原创 421，去重正文 1000 条。

## feed.xml 为什么长这样

```xml
<?xml version='1.0' encoding='utf-8'?>
<rss version="2.0">
  <channel>
    <title>一句 · 旷野与自由</title>
    <link>https://github.com/你的用户名/你的仓库</link>
    <description>每 5 分钟随机换一条 · 旷野 / 自由 / 热爱 / 平凡 / 治愈</description>
    <language>zh-CN</language>
    <item>
      <title>金句正文</title>
      <description>—— 出处 〔分级〕</description>
    </item>
  </channel>
</rss>
```

三点都是对着 `RssFeed.vue` 的本地解析器设计的：

- 只有 1 个 `<item>`：`processItems()` 从 `items[0]` 取 `limit` 条，XML 里只有一条时连 `limit` 都不用依赖。
- 不写 `<pubDate>`：`formatDate()` 返回空串，界面不会出现日期，也不会让人误以为在按时间线排序。想要日期跑 `python3 生成feed.py --with-date`。
- 不写 `<item><link>`：组件会渲染成 `div` 而不是链接，`continue-reading-btn` 也不生成，widget 里只剩「一行金句 + 一行小字出处」。想要可点链接跑 `--with-link`。

〔可考〕〔媒体〕〔网传〕〔原创〕 是原素材库的分级标签，放在 `<description>` 里以小字显示。看到〔网传〕别署名引用——这正是原脚本反复强调的。

> 池子里已确认不含 `&` `<` `>` `"` `'`，所以标题走文本插值不会出现 `&` 这类字面量。

## Dashy 配置

把 `feed.xml` 推到 GitHub 仓库，然后在 `conf.yml`：

```yaml
sections:
  - name: 一句
    widgets:
      - type: rss-feed
        updateInterval: 300        # 与 type 平级，单位「秒」，不在 options 里
        options:
          rssUrl: https://raw.githubusercontent.com/你的用户名/你的仓库/main/feed.xml?v=1
          parseLocally: true       # 关键：本地解析，保住顺序、不需要 rss2json 的 apiKey
          limit: 1
```

`parseLocally: true` 让 Dashy 直接抓 XML 自己解析；此时 `orderBy` / `orderDirection` 这些参数根本不会拼进请求，`pubDate` 只是显示用的小字，完全不参与排序。

想让 widget 更干净，压一行丢进 `appConfig.customCss`：

```css
.rss-wrapper .meta-container{display:none!important}.rss-wrapper .post-row{border-top:none!important;padding-top:0!important}.rss-wrapper .post-title{font-size:1.1rem!important;line-height:1.6!important;font-weight:500!important}.rss-wrapper .post-date{display:none!important}.rss-wrapper .post-body{margin-top:.35rem!important;font-size:.8rem!important;opacity:.7}
```

效果：只剩一行大字金句 + 一行小字出处，很适合塞在 `photo` 那种小挂件位。

## 换一条的三种方式

### ① 手动（最贴合你说的「手动随机」）

```bash
python3 生成feed.py          # 默认抽 1 条
python3 生成feed.py --n 5    # 想改回 5 条
git add feed.xml && git commit -m "换一条" && git push
```

脚本会读 `.last_id`，自动避开上一次抽中的那条，保证每跑一次一定换。想复现某一批用 `--seed 42`。

### ② 自动（GitHub Actions，每 5 分钟）

`.github/workflows/shuffle.yml`：

```yaml
name: shuffle-quote
on:
  schedule:
    - cron: '*/5 * * * *'
  workflow_dispatch:
permissions:
  contents: write
jobs:
  shuffle:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python3 生成feed.py
      - name: commit & push
        run: |
          git config user.name  "quote-bot"
          git config user.email "quote-bot@users.noreply.github.com"
          git add feed.xml
          git diff --quiet --cached || (git commit -m "chore: shuffle quote" && git push)
```

仓库建议结构：

```text
repo/
├── feed.xml                 ← Dashy 读这个
├── 金句池1000条.json
├── 生成feed.py
└── .github/workflows/shuffle.yml
```

注意 `*/5 * * * *` 已是 GitHub Actions 的最小调度粒度，且官方明示高负载时会延迟甚至丢跑、公共仓库 60 天无活动会静默停掉定时任务——当「偶尔换一换」用没问题，别当精确计时器。

### ③ 立刻生效的两个小技巧

- 改完 XML 把 `rssUrl` 末尾 `?v=1` 改成 `?v=2`，URL 变了就是新的 cache key，CDN 会重新回源。
- 或者直接点 widget 右上角的刷新图标，它直接调 `update()`，不等 300 秒计时器。

## 关于缓存（一定要看）

`raw.githubusercontent.com` 实测响应头：

```http
cache-control: max-age=300
access-control-allow-origin: *
```

正好也是 300 秒，而且它的 Varnish 硬缓存不吃客户端的 `no-store` / `Cache-Control` 请求头。所以叠加起来：

> 脚本换一条 → 最多 5 分钟 CDN 吐新内容 → 最多再 5 分钟 Dashy 轮询 → 最长约 10 分钟才在页面看到。

对「每 5 分钟换一条」完全够用。想彻底消掉这层延迟，把 `feed.xml` 放到自己能设 `Cache-Control: no-store` 的静态服务上，或换同源路径 `/feed.xml`（挂进 Dashy 的 `user-data/`）。

Service Worker 不挡 `.xml`：Workbox 只拦 `.yml` / `.yaml` 和几个本地 API，跨域 XML 走普通网络，不会再多一层缓存。不过你开着 `enableServiceWorker: true`，改完 `conf.yml` 记得 `Ctrl+Shift+R` 硬刷新。

## 别忘了替换

- `使用说明.md` 和 `生成feed.py` 里的 `https://github.com/你的用户名/你的仓库`
- `conf.yml` 里 `rssUrl` 的仓库路径
- `FEED_TITLE`、`FEED_LINK` 在 `生成feed.py` 顶部，可直接改

---

原脚本输出的是 TXT（编号｜正文｜〔标签〕出处）；这里改成输出 RSS XML，分卷、去重、固定种子 `20261105` 生成原创仿写补齐到 1000 条的逻辑全部保留，只是把「写 TXT」换成了「写 JSON 池子 + 随机抽一条写 XML」。
