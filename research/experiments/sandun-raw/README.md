# SANDUN 抓取证据（原始数据 · 只读 · 可复现）

本目录是 `research/2026-09-25_SANDUN全量解剖与反超清单.md` 与
`research/2026-09-25_SANDUN全流程实测报告.md` 的**原始证据**。

## 内容

| 路径 | 内容 | 文件数 |
| --- | --- | ---: |
| `*.txt`（根目录） | 其官方文档站 28 页的 Next.js RSC 载荷 | 28 |
| `replay-data/*.json` | **4 份官方案例的完整内部数据**（各约 800KB） | 4 |
| `slides-svg/*.svg` | 从内部数据还原的页面 SVG 源码 | 62 |
| `replays/*.txt` | 回放页外壳的 RSC 载荷 | 4 |
| `covers/*.png` | 首页「生成案例」的四张封面原图（视觉取证实物） | 4 |
| `evidence-hashes.json` | 102 个文件的 bytes 与 sha256 清单，供 `--verify` 核对 | — |

## 工具

| 脚本 | 作用 |
| --- | --- |
| `fetch_evidence.py` | 只读、匿名、仅 https 的可复现抓取器；`--verify` 校验清单 |
| `verify_report_claims.py` | 把两份报告里的每个数字对回原始 JSON，防张冠李戴 |

```bash
E:\Python312\python.exe research/experiments/sandun-raw/fetch_evidence.py
E:\Python312\python.exe research/experiments/sandun-raw/fetch_evidence.py --verify
E:\Python312\python.exe research/experiments/sandun-raw/verify_report_claims.py
```

## 为什么二进制入库（与 `spike-D-fixtures/` 不同）

`.gitignore` 把实验产物分两类：**A 类**可确定性重建、不入库；
**B 类**被报告引用为证据、必须入库。本目录属 B 类——`covers/*.png` 是
「版式骨架一致而配色不同」这个修正结论的取证实物，删掉就无法复核。

`replay-data/*.json` 体积较大（3.1 MB）但**不可替代**：报告的核心结论
（图表是 SVG 自绘、`chartPlans` 全空、阶段序列因输入通道而异）全部由此得出。
若需瘦身，删掉后用 `fetch_evidence.py` 一条命令重取。

## 数据获取方式（可复现）

其前端请求的不是同源 API。真实后端域名从 JS chunk 中提取：

```text
https://agentadmin.sandun.cc
```

**回放数据端点匿名可读**：

```http
GET https://agentadmin.sandun.cc/api/replay/{replayId}   → 200 JSON
```

四个案例的 replayId 见 `fetch_evidence.py` 的 `REPLAYS`。

## 边界声明（重要）

- **只读公开数据**：文档站（公开）与回放分享端点（其产品设计上「任何人无需
  登录即可回看」）。
- **不调用任何生成/写入端点**：不碰 `/api/agent/*`、`/generate`、`/docs-editor`
  （后者亦被其 `robots.txt` 禁止抓取）。
- **不使用账号**：全程匿名请求。
- 抓取产物是其产品的公开输出，仅用于本项目研究比对，**不再分发**。

## 一次真实的事故记录

初版抓取把两个 `replayId` 与案例名对错了，导致：

1. 「小米」与「正泰」的页数、图表数、时间线数字**互换**；
2. 产出 85 个**内容交叉**的 SVG 文件（文件名写「正泰」，内容是小米）。

修复措施（现在都在代码里）：

- `fetch_evidence.py` 抓取时**自校验** `project.title` 必须命中该案例的关键词，
  不匹配就报错跳过；
- `verify_report_claims.py` 把报告数字对回原始数据，并检查报告中**不再残留**
  错配时的旧数字组合。

**教训**：只按标签（文件名）组织数据是不够的，必须让数据**自证身份**
（用内容里的 id/title 校验），否则错配会静默传播到结论层。
