"""SANDUN 证据抓取器 —— 可复现、只读、匿名。

用途：重新抓取本目录下全部 SANDUN 证据（文档站 RSC 载荷、回放内部数据、
案例封面、页面 SVG），使 `sandun-raw/` 下的大文件可随时重建。

边界声明：
- **只读取公开数据**：其文档站（公开）与回放分享端点（其产品设计上"任何人无需
  登录即可回看"，见 docs/export/replay）。
- **不调用任何生成/写入端点**：不碰 /api/agent/*、/generate、/docs-editor
  （后者亦被其 robots.txt 禁止抓取）。
- **不使用账号**：全程匿名请求。
- 抓取产物是其产品的公开输出，仅用于本项目研究比对，不再分发。

运行：python research/experiments/sandun-raw/fetch_evidence.py [--verify]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# 文档站路径（其 sitemap.xml 公开列出）
DOC_PATHS = [
    "quickstart",
    "workflow/outline", "workflow/research", "workflow/planning",
    "workflow/draft", "workflow/final-design", "workflow/chat",
    "create/one-sentence", "create/requirement-doc", "create/reference-pdf",
    "create/beautify",
    "design/render-modes", "design/style-selection", "design/style-library",
    "editing/canvas", "editing/page-editor", "editing/images-charts",
    "editing/layers", "editing/history", "editing/animation",
    "export/export", "export/fonts", "export/replay",
    "account/profile", "account/billing", "account/invite",
    "help/faq", "help/contact",
]

# 首页「生成案例」的公开回放（其首页直接展示，链接在其 JS chunk 中）
# 注意：键必须与回放数据里 `project.title` 的题材一致。抓取时会做自校验，
# 不匹配就报错——之前曾因为把 replayId 与案例名对错，产出内容交叉的脏数据。
REPLAYS = {
    "北京5日游攻略": "9c0a0449ccb6559114e5ccab190e2f3d3eaa5f728f66556094a1df5dca1b4d3b",
    "小米2025Q3业绩报告": "398f4c8d6feaa3aadcf00e27aa28fb225693fe6d29a290ee8f747131a2fa16a9",
    "Dify产品技术架构": "a8b740b9031a3c0d461c07fcd40fdbd346322cb43d5f26e9c227b9ba405d4b76",
    "正泰电器企业介绍": "ca539c0bd5090eee88f206828120e3234b8791e0baf57b5515f1a13dc179822a",
}

# 每个键必须命中的 project.title 关键词（防错配）
REPLAY_EXPECT = {
    "北京5日游攻略": ["北京", "攻略"],
    "小米2025Q3业绩报告": ["小米"],
    "Dify产品技术架构": ["Dify"],
    "正泰电器企业介绍": ["正泰"],
}

COVERS = [
    "cover01-mqp8lfzp.png", "cover02-mqp8ll6m.png",
    "cover03-mqp8lolo.png", "replay-cover-mqp8lrlm.png",
]
COVER_BASE = "https://aiphoto.sandunppt.com/public/uploads/superppt/docs/2026/06/22/"

REPLAY_API = "https://agentadmin.sandun.cc/api/replay/"


# 只允许 https：opener 不挂 FileHandler/FTPHandler 等，从源头排除非 https scheme
_OPENER = urllib.request.build_opener(urllib.request.HTTPSHandler())


def fetch_bytes(url: str) -> bytes:
    """只允许 https 下载。

    scheme 与 host 已显式校验（S310 无法识别这种先校验后调用的模式，故内联抑制）：
    非 https 或缺少 host 时直接拒绕，opener 也只挂 HTTPSHandler。
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() != "https" or not parts.netloc:
        raise ValueError(f"拒绝非 https 地址: {url}")
    safe_url = urllib.parse.urlunsplit(
        ("https", parts.netloc, parts.path, parts.query, ""))
    req = urllib.request.Request(safe_url,  # noqa: S310 (scheme 已校验为 https)
                                 headers={"User-Agent": UA})
    return _OPENER.open(req, timeout=60).read()  # noqa: S310


def rsc_blob(html: str) -> str:
    """从 Next.js App Router 页面中解出 RSC 流式载荷。"""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', html)
    out = []
    for c in chunks:
        try:
            out.append(json.loads('"' + c + '"'))
        except json.JSONDecodeError as e:
            print(f"  (跳过无法解析的 RSC 块: {e})", file=sys.stderr)
    return "".join(out)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _safe_read_bytes(path: str) -> bytes | None:
    """读文件，失败返回 None（不中断校验流程）。"""
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as e:
        print(f"  (读取失败 {path}: {e})", file=sys.stderr)
        return None


def _safe_load_json(path: str):
    """读 JSON，失败返回 None。"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"读取清单失败 {path}: {e}", file=sys.stderr)
        return None


def _safe_makedirs(path: str) -> bool:
    """建目录，失败返回 False。"""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as e:
        print(f"建目录失败 {path}: {e}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true",
                    help="只校验现有文件的 sha256，不重新抓取")
    args = ap.parse_args()

    manifest_path = os.path.join(HERE, "evidence-hashes.json")

    if args.verify:
        rec = _safe_load_json(manifest_path)
        if rec is None:
            return 2
        bad = []
        for item in rec.get("files", []):
            rel = item.get("path", "")
            # 防路径穿越：只允许本目录下的相对路径
            p = os.path.normpath(os.path.join(HERE, rel))
            if not p.startswith(os.path.normpath(HERE) + os.sep):
                bad.append(rel + ":unsafe-path")
                continue
            blob = _safe_read_bytes(p)
            if blob is None:
                bad.append(rel + ":missing")
                continue
            if sha256(blob) != item.get("sha256"):
                bad.append(rel + ":mismatch")
        n = len(rec.get("files", []))
        print(f"校验 {n} 个文件：{'全部一致' if not bad else '不一致 -> ' + str(bad)}")
        return 1 if bad else 0

    for sub in ("replay-data", "covers", "replays", "slides-svg"):
        if not _safe_makedirs(os.path.join(HERE, sub)):
            return 3

    files = []

    def save(rel: str, data: bytes) -> None:
        p = os.path.normpath(os.path.join(HERE, rel))
        if not p.startswith(os.path.normpath(HERE) + os.sep):
            print(f"  拒绝写入越界路径: {rel}", file=sys.stderr)
            return
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(data)
        except OSError as e:
            print(f"  写入失败 {rel}: {e}", file=sys.stderr)
            return
        files.append({"path": rel, "bytes": len(data), "sha256": sha256(data)})
        print(f"  {len(data):>9} B  {rel}")

    # 1) 文档站
    print("== 文档站 RSC 载荷 ==")
    for path in DOC_PATHS:
        try:
            html = fetch_bytes(f"https://sandun.cc/docs/{path}").decode("utf-8", "ignore")
            save(f"{path.replace('/', '__')}.txt", rsc_blob(html).encode("utf-8"))
        except Exception as e:
            print(f"  ERR {path}: {e}")

    # 2) 回放内部数据（公开端点）
    print("== 回放内部数据 ==")
    for name, rid in REPLAYS.items():
        try:
            raw = fetch_bytes(REPLAY_API + rid)
            data = json.loads(raw.decode("utf-8"))
            # 自校验：project.title 必须命中该键的关键词，否则说明 replayId 对错了
            title = (data.get("project") or {}).get("title") or ""
            expect = REPLAY_EXPECT.get(name, [])
            missing = [kw for kw in expect if kw not in title]
            if missing:
                print(f"  ERR {name}: project.title 与预期不符 -> "
                      f"实际为 {title!r}，缺少关键词 {missing}", file=sys.stderr)
                continue
            print(f"  [{name}] 自校验通过: project.title = {title!r}")
            save(f"replay-data/{name}.json",
                 json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))
            # 3) 页面 SVG
            for s in data.get("slides", []):
                c = s.get("content") or ""
                if c.startswith("<svg"):
                    slug = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", s.get("page_title", ""))[:60]
                    save(f"slides-svg/{name}_{s.get('page_key')}_{slug}.svg",
                         c.encode("utf-8"))
            # 4) 回放页外壳
            try:
                h = fetch_bytes(f"https://sandun.cc/replay/{rid}").decode("utf-8", "ignore")
                save(f"replays/{name}.txt", rsc_blob(h).encode("utf-8"))
            except Exception as e:
                print(f"    (replay shell ERR {e})")
        except Exception as e:
            print(f"  ERR {name}: {e}")

    # 5) 案例封面
    print("== 案例封面 ==")
    for c in COVERS:
        try:
            save(f"covers/{c}", fetch_bytes(COVER_BASE + c))
        except Exception as e:
            print(f"  ERR {c}: {e}")

    rec = {"source": "public SANDUN endpoints (read-only, anonymous)",
           "fetchedAt": None, "fileCount": len(files), "files": files}
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
    except OSError as e:
        print(f"写清单失败: {e}", file=sys.stderr)
        return 4
    print(f"\n共 {len(files)} 个文件，清单写入 evidence-hashes.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
