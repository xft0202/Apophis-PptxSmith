"""断链检查器 —— 确保文档里的相对链接都指向真实存在的文件。

为什么需要它：2026-09-26 做过一次归档与删除（过期 v1 报告、被重画的票、
失去决策价值的规格），当时有 11 个文件留下 15 处断链。
断链会让后续会话读到「指向空气」的引用，正是「扰乱视线」的一种。

用法：python check_links.py
退出码：0 = 无断链；1 = 有断链
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import unquote

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# 扫描范围：仓库内的 markdown
SCAN_GLOBS = [".scratch", "docs", "research", "."]

# 跳过目录
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".ruff_cache"}

# markdown 链接：[文本](目标)；跳过 http(s)、mailto、纯锚点
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def iter_markdown() -> list[str]:
    out = []
    for rel in SCAN_GLOBS:
        root = os.path.join(REPO, rel)
        if not os.path.exists(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".md"):
                    out.append(os.path.join(dirpath, fn))
    return sorted(set(out))


def main() -> int:
    files = iter_markdown()
    broken: list[tuple[str, str]] = []
    checked = 0

    for fp in files:
        try:
            with open(fp, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as e:
            print(f"  读取失败 {fp}: {e}", file=sys.stderr)
            continue
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if not target or target.startswith(
                    ("http://", "https://", "mailto:", "#", "file:")):
                continue
            # 去掉锚点与查询串
            clean = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not clean:
                continue
            checked += 1
            resolved = os.path.normpath(os.path.join(os.path.dirname(fp), clean))
            if not os.path.exists(resolved):
                broken.append((os.path.relpath(fp, REPO), target))

    print(f"检查 {len(files)} 份 markdown，{checked} 个相对链接")
    if broken:
        print(f"\n断链 {len(broken)} 处：")
        for f, t in broken:
            print(f"  {f}\n      -> {t}")
        return 1
    print("PASS 无断链")
    return 0


if __name__ == "__main__":
    sys.exit(main())
