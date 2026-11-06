# 金句 RSS · 全自动订阅源

一个静态 RSS 2.0 源：每次只放 **1 条金句**，**每 5 分钟自动换一句，全程无人值守**。
既能给 **Dashy 的 `rss-feed` widget** 用，也能给 **Fluent Reader / Feedly 等通用阅读器** 订阅。

仓库：`cary-jjw/jinju-RSS` · 分支 `main` · 公开

**核心分工：随机发生在生成端（GitHub Actions），不在浏览器端。**

```
cron-job.org 每 5 分钟敲门（POST workflow_dispatch）
        ↓
GitHub Actions · jinju-quote-auto（十几秒）
        ↓ 生成feed.py 抽一条 → commit → push
feed.xml 变化
        ↓ ≤ 5 分钟  raw CDN
        ↓ ≤ 5 分钟  Dashy updateInterval
    页面换句
```

刷新按钮只负责「重新抓」，不会替你重新抽签。

---

## 1. 当前状态：自动已生效 ✅

2026-11-06 21:15 CST 实测（GitHub Actions API）：

| 检查项 | 结果 |
| --- | --- |
| `21:10:20` 运行 | `jinju-quote-auto` / `workflow_dispatch` / **success** |
| `21:15:18` 运行 | `jinju-quote-auto` / `workflow_dispatch` / **success** |
| 间隔 | **4 分 58 秒**，与 cron-job.org 的每 5 分钟完全对上 |
| 触发来源 | 外部闹钟自动打的，**没有点任何按钮** |
| 线上 `feed.xml` | 已随每次运行换句，`pubDate` 为空（不显示日期） |

现在什么都不用点，它自己会换。

> **为什么用外部闹钟**：GitHub 自带的 `schedule` 在这个仓库一直没能稳定排上队——旧注册对象 `408141965` 从 2026-11-05 创建起 `updated_at` 就没刷新过，改了七八次 cron 都没被重新读取；新建 `quote-cron.yml` 生成全新注册对象后，跨过 7 个刻度仍是 0 次 Scheduled 运行。而 `workflow_dispatch` 通道 8 次全绿、一次没失手。所以把「闹钟」挪到外面，**生成、commit、push 仍然全部在 GitHub Actions 里**。

---

## 2. 文件清单

### 必须上传到仓库 `main` 根目录

| 文件 | 作用 |
| --- | --- |
| `.github/workflows/quote-cron.yml` | **唯一生效的 workflow**：`name: jinju-quote-auto`，短 job，十几秒结束 |
| `feed.xml` | 成品订阅源，RSS 2.0，`<channel>` 里只有 1 个 `<item>` |
| `生成feed.py` | 随机抽 N 条重写 `feed.xml` |
| `金句池1000条.json` | 数据池，1000 条，字段只有 `id / text / source` |
| `.gitignore` | 排除本地运行产生的 `.last_id`、`__pycache__/` |
| `README.md` | 本文件 |

> ⚠️ **旧的 `shuffle.yml` 已删除，不要放回去**。仓库 `.github/workflows/` 里只应有 `quote-cron.yml` 一个文件。
> ⚠️ `.github` 是**隐藏目录**，解压/网页上传时最容易被处理成 `github`（少一个点）。GitHub Actions 只认带点的那个路径。用网页建最稳：`Add file → Create new file`，文件名逐字符填 `.github/workflows/quote-cron.yml`。

### 本地参考，不用上传

| 文件 | 作用 |
| --- | --- |
| `外部闹钟设定.md` | cron-job.org 逐项填表、TEST RUN、排错、维护 |
| `dashy配置片段.yml` | 可直接复制的 conf.yml 片段（含完整 customCss） |

`备选方案/` 目录里是这一路试过但**最终没采用**的方案（客户端随机、Cloudflare Worker、GitHub 贡献图配置），仅存档，不需要上传、不需要看。

---

## 3. 自动是怎么实现的

### 主通道：cron-job.org → GitHub（已生效）

每 5 分钟向下面这个端点发一次 POST：

```
https://api.github.com/repos/cary-jjw/jinju-RSS/actions/workflows/quote-cron.yml/dispatches
```

- Request method：**POST**
- Request body：`{"ref":"main"}`
- Headers：`Authorization: Bearer <PAT>`、`Accept: application/vnd.github+json`、`Content-Type: application/json`
- 成功返回 **204 No Content**（响应体为空是正常的）

逐项填表见 `外部闹钟设定.md`。cron-job.org 免费版最多 60 次/小时（可每分钟一次），请求超时 30 秒；GitHub dispatch 是异步的，几百毫秒就返回，不会被掐断。

### 兜底：GitHub 自带 `schedule`

`quote-cron.yml` 里保留着 `cron: '2-57/5 * * * *'`（每小时 12 个错峰刻度）。它在这个仓库实测 0 次触发，留着当兜底无害——**两套同时开不会冲突**，只是可能多换几句，短 job 不会撞 push。

想只留一套：删掉 yml 里 `on:` 下的 `schedule:` 两行即可，但**能跑就先别动文件**（每改一次都要重新注册）。

> GitHub 页面上的「Auto-refresh: 5m」下拉只是**网页轮询运行记录列表**，让页面不用手动 F5。它不会执行脚本、不会 commit、不会改 `feed.xml`，别把它当定时开关。

### 工作流内容（`quote-cron.yml`）

```yaml
name: jinju-quote-auto
on:
  schedule:
    - cron: '2-57/5 * * * *'
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
      - name: 抽一条并推送
        run: |
          git config user.name "quote-bot"
          git config user.email "quote-bot@users.noreply.github.com"
          python3 生成feed.py
          git add feed.xml
          git diff --quiet --cached || (git commit -m "chore: shuffle quote" && git push)
```

要点：每次触发**只换一句、十几秒结束**，每次重新 checkout 最新 `main`。旧版那个「每小时叫醒一次 + job 内 `sleep 300` 跑 12 次」的 55 分钟长循环已废弃——它曾因中途 push 冲突报 `exit 1`，是早期红叉的来源。`GITHUB_TOKEN` 的 push 不会递归触发新 workflow。

---

## 4. Dashy 配置

```yaml
sections:
  - name: 一句
    widgets:
      - type: rss-feed
        updateInterval: 300        # widget 层级，单位「秒」，与 type 平级
        options:
          rssUrl: https://raw.githubusercontent.com/cary-jjw/jinju-RSS/main/feed.xml?v=1
          parseLocally: true       # 本地解析，不需要 rss2json 的 apiKey
          limit: 1
```

`updateInterval: 300` 现在**正好匹配生成端每 5 分钟**，不用改。`parseLocally: true` 时 `orderBy / orderDirection` 不会拼进请求，`pubDate` 也不参与排序——组件按 XML 里的物理顺序取前 N 条。

### 字段辨析（这个坑踩过好几次）

| 字段 | 归属 | 单位 | 对 `rss-feed` |
| --- | --- | --- | --- |
| `updateInterval` | **widget 层**，与 `type` 平级 | 秒 | ✅ 正确，就是重新拉取间隔 |
| `refreshInterval` | **API Response（customapi）widget 的 `options`** | 毫秒，默认 10000 | ❌ 写了会被静默忽略 |

`ConfigSchema.json` 里 widget 允许的字段是：`type, updateInterval, timeout, useProxy, allowInsecure, options, label, ignoreErrors`。`refreshInterval` 在 schema 里 **0 次出现**。

### 让 widget 只剩「一行金句 + 一行出处」

压成一行丢进 `appConfig.customCss`：

```css
.rss-wrapper .meta-container{display:none!important}.rss-wrapper .post-date{display:none!important}.rss-wrapper .continue-reading-btn{display:none!important}.rss-wrapper .post-row{border-top:none!important;padding-top:0!important}.rss-wrapper .post-title{font-size:1.1rem!important;line-height:1.6!important;font-weight:500!important}.rss-wrapper .post-body{margin-top:.35rem!important;font-size:.8rem!important;opacity:.7}
```

对应 `RssFeed.vue` 里的真实 class：

| 想去掉的东西 | 选择器 |
| --- | --- |
| 顶部标题栏 | `.meta-container` |
| **「11月5日周四」日期** | `.post-date` |
| 金句上方的虚线 | `.post-row { border-top: 1px dashed ... }` |
| 「打开链接」按钮 | `.continue-reading-btn`（不写 `item/link` 时本来就不生成） |

### 关于日期

`RssFeed.vue` 会把 `sanitized.pubDate` 交给 `formatDate()`，用 `toLocaleDateString(..., {weekday:'short', day:'numeric', month:'short'})` 渲染成「11月5日周四」。**所以脚本默认不写 `<item><pubDate>`**，从源头掐掉；CSS 里的 `.post-date` 是第二道保险（那个 `<p>` 没有 `v-if`，空内容时标签仍在）。

`channel` 级的 `<lastBuildDate>` 保留着，但 `RssParser.js` 不读它，不会变成界面上的日期。

---

## 5. 时间预期

```
每 5 分钟自动换句（已生效）
   ↓ ≤ 5 分钟  raw CDN (max-age=300)
   ↓ ≤ 5 分钟  Dashy updateInterval: 300
页面换句                          → 最长约 10 分钟
```

**想立刻看到**：`rssUrl` 末尾 `?v=1` 改成 `?v=2`（换 cache key，强制回源）→ 点 widget 右上角刷新图标 → `Ctrl+Shift+R` 硬刷（开着 Service Worker）。

判断到底换没换，最可靠的办法是直接打开 raw 链接看 `<item><title>` 那行，比盯着 widget 猜强。

---

## 6. 地址（别混用）

| 用途 | 地址 |
| --- | --- |
| **订阅 / Dashy `rssUrl`** | `https://raw.githubusercontent.com/cary-jjw/jinju-RSS/main/feed.xml?v=1` |
| 等价长形式 | `https://raw.githubusercontent.com/cary-jjw/jinju-RSS/refs/heads/main/feed.xml?v=1` |
| 国内不通时 | `https://cdn.jsdelivr.net/gh/cary-jjw/jinju-RSS@main/feed.xml` |
| 国内不通时（需先开 Pages） | `https://cary-jjw.github.io/jinju-RSS/feed.xml` |
| 给人点的网页地址 | `https://github.com/cary-jjw/jinju-RSS/tree/main`（**只**用于 `FEED_LINK` / `<channel><link>`） |

- 仓库里只有 `feed.xml` 能当订阅源；`.py` 和 `.json` 不是 RSS，加了必报错。它们不用填进任何配置，脚本按同目录相对路径 `POOL_FILE = BASE / "金句池1000条.json"` 读取。
- ⚠️ `/blob/main` 和 `/tree/main` 返回 **HTML 网页**，不是 XML。填进订阅源会报 `A network error has occured.` 或 `Invalid feed XML`。
- `FEED_LINK` 改完要**重跑一次脚本**，`feed.xml` 才会跟着更新；手改 `feed.xml` 会被下次生成覆盖。
- 验证 workflow 内容时用 GitHub 网页或 jsDelivr 按 commit 取；`raw.githubusercontent.com` 有 5 分钟缓存，可能还在吐旧副本。

---

## 7. 通用 RSS 阅读器（去重）

每条都带稳定 guid：

```xml
<guid isPermaLink="false">jinju-rss-quote-0724</guid>
```

阅读器靠它去重，没有它（且没有 `link` / `pubDate`）时会把每次抓取当成新文章，攒出一堆一模一样的卡片、时间全是 `now`。`isPermaLink="false"` 不能省。`RssParser.js` 不读 `guid`，**对 Dashy 零影响**。

| 模式 | 命令 | 效果 |
| --- | --- | --- |
| `by-id`（默认） | `python3 生成feed.py` | 同一句只存一次，每换一句新增一条 → 不重复的历史金句流 |
| `fixed` | `--guid-mode fixed` | 永远只有 1 条，内容随抓取更新 |
| `none` | `--guid-mode none` | 不写 guid，会重复，别用 |

⚠️ 若曾订阅过旧版（无 guid）积了一堆重复卡片：需在阅读器里**删除订阅源**（连带清掉本地文章）→ 重新添加 → 之后同一句只保留一条。只点刷新会看到「旧的 N 条 + 新的 1 条」。

---

## 8. 脚本参数与池子

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--n` | `1` | 抽取条数 |
| `--seed` | 不固定 | 固定随机种子，复现同一批 |
| `--guid-mode` | `by-id` | `by-id` / `fixed` / `none` |
| `--with-date` | 关 | 写 `item/pubDate`；**Dashy 会显示日期，别开** |
| `--with-link` | 关 | 写 `item/link`；Dashy 会多一个「打开链接」按钮 |

本地手动换一条（正常不用）：

```bash
python3 生成feed.py
git add feed.xml && git commit -m "换一条" && git push
```

脚本用 `.last_id` 记住上一次编号，手动跑会避开上一条。Actions 每次是干净 checkout，`.last_id` 不跨次保留，所以自动模式是纯随机，偶尔连着两次同一句属正常（概率 1/1000）。

**池子口径**（只是说明，不是 JSON 字段）：来源 `励志开悟名句1000条.txt`，仅收真实可核查的中外经典名人名句，不含佛道典籍原文、不含网络仿写与伪名言。每条拆成 `text`（名句）与 `source`（`朝代/国别·作者《篇名或书名》`）。**1000 条、编号 1~1000 连续、正文零重复、出处 1000/1000 都带《》**。全部有明确出处，可直接署名引用。

> 想改 feed 标题或 channel 描述文案：编辑 `生成feed.py` 里的 `FEED_TITLE`（第 48 行）和 `ET.SubElement(ch, "description")` 那行（第 73~75 行），然后重跑一次。当前标题仍是「一句 · 旷野与自由」，描述已对齐「每 5 分钟随机换一条」。

---

## 9. 问题速查

| 现象 | 原因 | 怎么办 |
| --- | --- | --- |
| 页面一句不动 | CDN ≤5 分钟 + Dashy 轮询 ≤5 分钟 | 改 `?v=2` → 点刷新图标 → `Ctrl+Shift+R` |
| 显示「11月5日周四」 | 用了带 `pubDate` 的旧 feed 或 `--with-date` | 覆盖新版 `feed.xml`；CSS `.post-date` 兜底 |
| Actions 全是 `workflow_dispatch` 没有 `Scheduled` | **正常**，外部闹钟走的就是 dispatch | 不用管 |
| 自动停了 | PAT 过期 / 被 Regenerate，或 cron-job.org 连续失败自动停用 | 看 job history 的状态码，更新 Header 或重新启用任务 |
| `401` | token 无效 / 没填 / 过期 | 重新生成 PAT，更新 `Authorization` |
| `403` | PAT 的 **Actions 权限没选 Read and write** | 回 token 设置改权限（最常见） |
| `404` | PAT 没勾 `jinju-RSS`，或 URL 里 workflow 文件名写错 | 必须是 **`quote-cron.yml`** |
| `422` | yml 里没有 `workflow_dispatch:`，或 ref 不是 `main` | 检查 `on:` 段 |
| `204` 但 Actions 没动静 | workflow 被 Disable | Actions 页 Enable workflow |
| 阅读器一堆重复卡片 | 旧 feed 无 `guid` | 覆盖新版 + 删源重加 |
| widget 空白 / `Invalid feed XML` | `rssUrl` 用了网页地址或 `.py`/`.json` | 换 raw 的 `feed.xml` |
| `KeyError: 'tag'` | 旧脚本配精简 JSON | 用本仓库的 `生成feed.py`（已用 `.get("tag")` 兼容） |
| Actions 里看不到工作流 | `.github` 少了前导点 | 路径必须是 `.github/workflows/quote-cron.yml` |
| 改完没反应 | Service Worker 缓存 | `Ctrl+Shift+R` 硬刷新 |
| 「自动刷新」下拉没用 | 它只刷网页运行列表 | 正常，不参与换句 |

---

## 10. 维护与安全

- **PAT 是最关键的一环**：Fine-grained token，只勾 `jinju-RSS`，**Actions: Read and write**（创建页右侧下拉默认 Read-only，必须手动改）。当前选的是 No expiration，不会突然 401 停掉，但泄漏后没有自动失效期限。
- ⚠️ **如果 PAT 曾以明文出现在截图或对话里，建议去 tokens 列表 `Regenerate token`**，把新串同步更新到 cron-job.org 的 `Authorization` Header（30 秒，其它都不用动）。**永远不要把 token 提交进仓库、贴进聊天或写进 conf.yml**。
- cron-job.org 请求超时 30 秒、连续失败多次会自动停用任务；**打开「在任务历史中保存响应」**能在出问题时直接看到 401/403/204，不用瞎猜。
- 想暂停自动：在 cron-job.org 把 `Enable job` 关掉即可，比改 GitHub 文件干净。
- GitHub 仓库 `Settings → Actions → General → Workflow permissions` 要保持 **Read and write permissions**，否则 `git push` 会失败。
- `feed.xml` 是生成产物，**别手改**（下次运行会覆盖）。要改 channel 元信息就改脚本。

---

原始素材是一份编号 1~1000 的 TXT 名句清单；按「最后一个空格前为正文、之后为出处」拆成 `id / text / source` 三字段的 JSON 池子，再由 `生成feed.py` 随机抽一条写 XML，最后由 cron-job.org 每 5 分钟触发 GitHub Actions 自动重跑。
