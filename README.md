# 金句 RSS · 金句自动订阅源

一个静态 RSS 2.0 源：每次只放 **1 条金句**，**GitHub Actions 自动每 5 分钟换一句**，无需手动干预。
既能给 **Dashy 的 `rss-feed` widget** 用，也能给 **Fluent Reader / Feedly 等通用阅读器** 订阅。

仓库：`cary-jjw/jinju-RSS`，分支 `main`，公开。

**核心分工：随机发生在生成端（GitHub Actions），不在浏览器端。**

```
Actions 每 5 分钟抽一条 → 重写 feed.xml → commit/push
        ↓ 最多 5 分钟（CDN）
        ↓ 最多 5 分钟（Dashy 轮询）
    页面显示新句子
```

刷新按钮只负责「重新抓」，不会替你重新抽签。

---

## 1. 当前状态：自动已生效 ✅

线上已确认（2026-11-06 05:29 CST 实测）：

| 检查项 | 结果 |
| --- | --- |
| `.github/workflows/shuffle.yml` | 已启用，`event = schedule` 运行已出现 |
| 自动提交 | 连续 **7 条** `quote-bot / chore: shuffle quote`，间隔约 5 分 01 秒 |
| 时间线 | `20:58:49 → 21:03:51 → 21:08:52 → 21:13:53 → 21:18:54 → 21:23:56 → 21:28:57 UTC` |
| `feed.xml` | 已随每次自动提交换句，`pubDate` 为空（**不显示日期**） |

所以「为什么刷新还是同一句」「要不要手动跑」这类问题已经翻篇——**现在什么都不用点，它自己会换**。

---

## 2. 自动是怎么实现的

当前用的是**低频调度 + 内部循环版**工作流：GitHub 每小时只需排 1 次队，job 内每 5 分钟换一句、跑满 12 次。这样比 `*/5` 高频 cron 更容易被调度器排上，而换句频率仍是 5 分钟。

```yaml
name: shuffle-quote
on:
  schedule:
    - cron: '7 * * * *'        # 每小时第 7 分（UTC）触发一轮，避开整点高峰
  workflow_dispatch:            # 保留手动按钮，随时可点
permissions:
  contents: write
concurrency:                    # 防止两轮撞车导致 push 冲突
  group: shuffle-quote
  cancel-in-progress: true
jobs:
  shuffle:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: 每小时跑一轮，每 5 分钟换一条（共 12 次）
        run: |
          git config user.name "quote-bot"
          git config user.email "quote-bot@users.noreply.github.com"
          for i in $(seq 1 12); do
            python3 生成feed.py
            git add feed.xml
            git diff --quiet --cached || (git commit -m "chore: shuffle quote" && git push)
            if [ "$i" -lt 12 ]; then sleep 300; fi
          done
```

几个要点：

- 单轮 job 约 55 分钟，远低于 6 小时上限；12 次里最后一次不再 `sleep`。
- 每轮结束后到下一小时 `:07` 之间约有 5~10 分钟空档，属正常，不必以为停了。
- `GITHUB_TOKEN` 的 push 不会递归触发新 workflow，所以循环不会被自己打断。
- `workflow_dispatch` 保留：想立刻换一句，Actions → `shuffle-quote` → **Run workflow** → `main` → Run，7~18 秒出结果。

> ⚠️ GitHub 页面那个「自动刷新：30 秒 / 1 分钟 / 5 分钟 / 离开 / 立即刷新」下拉，只是**网页轮询运行记录列表**，让页面不用手动 F5。它不会执行脚本、不会 commit、不会改 `feed.xml`。别把它当成定时任务开关。

---

## 3. 文件清单

| 文件 | 作用 |
| --- | --- |
| `.github/workflows/shuffle.yml` | **自动换句的工作流**（隐藏目录，最容易漏传） |
| `feed.xml` | 成品订阅源，RSS 2.0，`<channel>` 里只有 1 个 `<item>` |
| `生成feed.py` | 随机抽 N 条重写 `feed.xml` |
| `金句池1000条.json` | 数据池，1000 条，字段只有 `id / text / source` |
| `.gitignore` | 排除本地运行产生的 `.last_id`、`__pycache__/` |
| `README.md` | 本文件 |

池子来源构成（**只是说明，不是 JSON 字段**）：古典 108 / 现当代 85 / 外国 99 / 影视 66 / 媒体 180 / 网传 41 / 原创 421，去重后正好 1000 条。`source` 文字本身带「网传 / 出处存疑 / 常见转述 / 本素材库原创仿写」等提示，看到这些别署名引用。

---

## 4. Dashy 配置

```yaml
sections:
  - name: 一句
    widgets:
      - type: rss-feed
        updateInterval: 300        # 与 type 平级，单位「秒」，不在 options 里
        options:
          rssUrl: https://raw.githubusercontent.com/cary-jjw/jinju-RSS/refs/heads/main/feed.xml?v=1
          parseLocally: true       # 本地解析，保住顺序，不需要 rss2json 的 apiKey
          limit: 1
```

`parseLocally: true` 时 `orderBy / orderDirection` 不会拼进请求，`pubDate` 也不参与排序——组件就是按 XML 里的物理顺序取前 N 条。

### 让 widget 只剩「一行金句 + 一行出处」

把这段压成一行丢进 `appConfig.customCss`：

```css
.rss-wrapper .meta-container{display:none!important}.rss-wrapper .post-date{display:none!important}.rss-wrapper .continue-reading-btn{display:none!important}.rss-wrapper .post-row{border-top:none!important;padding-top:0!important}.rss-wrapper .post-title{font-size:1.1rem!important;line-height:1.6!important;font-weight:500!important}.rss-wrapper .post-body{margin-top:.35rem!important;font-size:.8rem!important;opacity:.7}
```

对应 `RssFeed.vue` 里的真实 class（已核对源码）：

| 想去掉的东西 | 选择器 |
| --- | --- |
| 顶部「一句 · 旷野与自由」标题栏 | `.meta-container` |
| **「11月5日周四」日期** | `.post-date` |
| 金句上方的虚线 | `.post-row { border-top: 1px dashed ... }` |
| 「打开链接」按钮 | `.continue-reading-btn`（不写 `item/link` 时本来就不生成） |

### 关于日期

`RssFeed.vue` 会把 `sanitized.pubDate` 交给 `formatDate()`，用
`toLocaleDateString(navigator.language, {weekday:'short', day:'numeric', month:'short'})`
渲染成「11月5日周四」。

**所以最终版默认不写 `<item><pubDate>`**，从源头掐掉，不靠 CSS 兜底；CSS 里的 `.post-date` 是第二道保险（那个 `<p>` 没有 `v-if`，空内容时标签仍在）。

`channel` 级的 `<lastBuildDate>` 保留着，但 `RssParser.js` 只读 `title / link / description / author / image`，不会读它，所以不会变成界面上的日期。

---

## 5. 时间预期

自动跑起来之后，页面看到新句的最长滞后约 **10 分钟**：

```
Actions 每 5 分钟重写 feed.xml   ← 已生效
   ↓ 最多 5 分钟  raw CDN (max-age=300)
   ↓ 最多 5 分钟  Dashy updateInterval: 300
页面换句子
```

**想立刻看到**：把 `rssUrl` 末尾 `?v=1` 改成 `?v=2`（换 cache key，强制回源）→ 点 widget 右上角刷新图标 → `Ctrl+Shift+R` 硬刷（开着 Service Worker）。

判断到底换没换，最可靠的办法是直接打开 raw 链接看 `<item><title>` 那行，比盯着 widget 猜强。

> GitHub Actions 的 `schedule` 是尽力而为，高负载时可能延迟甚至丢跑；公共仓库 60 天无活动会静默停调度。哪天发现半天没换，去 Actions 页看最近一条运行的 event，必要时手动 Run workflow 一次即可重新接上。

---

## 6. 通用 RSS 阅读器（去重）

每条都带稳定 guid：

```xml
<guid isPermaLink="false">jinju-rss-quote-0274</guid>
```

阅读器靠它去重，没有它（且没有 `link` / `pubDate`）时会把每次抓取当成新文章，攒出一堆一模一样的卡片、时间全是 `now`。`isPermaLink="false"` 不能省，否则部分阅读器会拿它当 URL 打开。`RssParser.js` 不读 `guid`，**对 Dashy 零影响**。

| 模式 | 命令 | 阅读器里的效果 |
| --- | --- | --- |
| `by-id`（默认） | `python3 生成feed.py` | 同一句只存一次，每换一句新增一条 → 不重复的历史金句流 |
| `fixed` | `python3 生成feed.py --guid-mode fixed` | 永远只有 1 条，内容随抓取更新，最贴近「显示1条」 |
| `none` | `--guid-mode none` | 不写 guid，会重复，别用 |

`fixed` 请配合 `--n 1`；少数阅读器不实现「同 guid 更新内容」，会一直停在旧句子，遇到就换回默认 `by-id`。

⚠️ 若曾订阅过旧版（无 guid）而积了一堆重复卡片：新 guid 只对之后的抓取生效，需在阅读器里**删除这个订阅源**（连带清掉本地文章）→ 重新添加 → 之后同一句只保留一条。只点刷新会看到「旧的 N 条 + 新的 1 条」。

---

## 7. 地址（别混用）

| 用途 | 地址 |
| --- | --- |
| **订阅 / Dashy `rssUrl`** | `https://raw.githubusercontent.com/cary-jjw/jinju-RSS/refs/heads/main/feed.xml?v=1` |
| 等价短形式 | `https://raw.githubusercontent.com/cary-jjw/jinju-RSS/main/feed.xml?v=1` |
| 国内不通时的 CDN | `https://cdn.jsdelivr.net/gh/cary-jjw/jinju-RSS@main/feed.xml` |
| 国内不通时的 Pages | `https://cary-jjw.github.io/jinju-RSS/feed.xml`（Settings → Pages → main / root） |
| 给人点的网页地址 | `https://github.com/cary-jjw/jinju-RSS/tree/main`（**只**用于 `FEED_LINK` / `<channel><link>`） |

- 仓库里三个 `refs/heads/main` 文件地址都有效，但 **只有 `feed.xml` 能当订阅源**；`.py` 和 `.json` 不是 RSS，加了必报错。它们不用填进任何配置，脚本按同目录相对路径 `POOL_FILE = BASE / "金句池1000条.json"` 读取。
- 中文文件名的百分号编码（`%E7%94%9F...`）是对的，别手动解码回中文再粘。
- ⚠️ `/blob/main` 和 `/tree/main` 返回的是 **HTML 网页**，不是 XML。填进订阅源会报 `A network error has occured.` 或 `Invalid feed XML`。
- `FEED_LINK` 改完要**重跑一次脚本**，`feed.xml` 才会跟着更新；手改 `feed.xml` 会被下次生成覆盖。
- 验证 workflow 内容时用 GitHub 网页或 jsDelivr 按 commit 取；`raw.githubusercontent.com` 有 5 分钟缓存，可能还在吐旧副本。

---

## 8. 脚本参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--n` | `1` | 抽取条数 |
| `--seed` | 不固定 | 固定随机种子，复现同一批 |
| `--guid-mode` | `by-id` | `by-id` / `fixed` / `none` |
| `--with-date` | 关 | 写 `item/pubDate`；**Dashy 会显示日期，别开** |
| `--with-link` | 关 | 写 `item/link`；Dashy 会多一个「打开链接」按钮 |

本地手动换一条：

```bash
python3 生成feed.py
git add feed.xml && git commit -m "换一条" && git push
```

脚本用 `.last_id` 记住上一次编号，手动跑会主动避开上一条。Actions 每次是干净 checkout，`.last_id` 不跨次保留，所以自动模式是纯随机，偶尔连着两次同一句属正常（概率 1/1000）。

---

## 9. 问题速查

| 现象 | 原因 | 怎么办 |
| --- | --- | --- |
| 页面一句不动 | CDN 5 分钟 + Dashy 轮询 5 分钟 | 改 `?v=2` → 点刷新图标 → `Ctrl+Shift+R` |
| 显示「11月5日周四」 | 用了带 `pubDate` 的旧 feed 或 `--with-date` | 覆盖新版 `feed.xml`；CSS `.post-date` 兜底 |
| 半天没换句 | `schedule` 延迟 / 丢跑 | Actions 页看 event，必要时手动 Run workflow 一次 |
| 「自动刷新」下拉没用 | 它只刷网页运行列表 | 正常，不参与换句；自动靠 `.github/workflows/shuffle.yml` |
| 阅读器一堆重复卡片 | 旧 feed 无 `guid` | 覆盖新版 + 删除订阅源重新添加 |
| widget 空白 / `Invalid feed XML` | `rssUrl` 用了网页地址或 `.py`/`.json` | 换 raw 的 `feed.xml` |
| `A network error has occured.` | 国内连不上 raw | 换 jsDelivr 或 GitHub Pages |
| `KeyError: 'tag'` | 旧脚本配精简 JSON | 用本仓库的 `生成feed.py`（已用 `.get("tag")` 兼容） |
| Actions 里看不到工作流 | `.github` 少了前导点，传成了 `github/` | 路径必须是 `.github/workflows/shuffle.yml` |
| 改完没反应 | Service Worker 缓存 | `Ctrl+Shift+R` 硬刷新 |

---

原始素材是个 TXT 生成器；这里保留它的分卷、去重、固定种子 `20261105` 补齐原创到 1000 条的逻辑，把「写 TXT」改成「写 JSON 池子 + 随机抽一条写 XML」，再由 GitHub Actions 每 5 分钟自动重跑。

原脚本输出的是 TXT（编号｜正文｜〔标签〕出处）；这里改成输出 RSS XML，分卷、去重、固定种子 `20261105` 生成原创仿写补齐到 1000 条的逻辑全部保留，只是把「写 TXT」换成了「写 JSON 池子 + 随机抽一条写 XML」。
