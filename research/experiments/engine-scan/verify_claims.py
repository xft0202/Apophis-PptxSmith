"""核对 G1–G5 筛选报告里的数字是否与快照一致。

沿用 SANDUN 调研的教训：**报告数字必须能对回原始数据**，
否则错配会静默传播到决策层。

用法：python verify_claims.py
退出码：0 = 一致；1 = 不符
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "g1-g5-snapshot.json")
REPORT = os.path.abspath(os.path.join(
    HERE, "..", "..", "2026-09-26_PPTX引擎候选活跃度硬门筛选.md"))

# 报告中的关键断言（候选 -> 必须成立的事实）
EXPECT: dict[str, dict[str, Any]] = {
    "Open XML SDK": {"last_commit": "2026-08-18", "commits_180d": 37,
                     "top_contributor_pct": 55, "verdict": "入场"},
    "PptxGenJS": {"last_commit": "2025-06-26", "commits_180d": 0,
                  "top_contributor_pct": 94, "verdict": "淘汰"},
    "python-pptx": {"last_commit": "2024-08-06", "commits_180d": 0,
                    "top_contributor_pct": 96, "verdict": "淘汰"},
    "ShapeCrawler": {"commits_180d": 66, "top_contributor_pct": 88,
                     "verdict": "淘汰"},
    "ppt-master": {"commits_180d": 100, "top_contributor_pct": 98,
                   "stars": 56399, "verdict": "淘汰"},
    "pptx-automizer": {"top_contributor_pct": 89, "verdict": "淘汰"},
    "unioffice": {"top_contributor_pct": 63, "verdict": "淘汰"},
    "Apache POI": {"commits_180d": 100, "top_contributor_pct": 30,
                   "verdict": "入场"},
    "officegen": {"commits_180d": 0, "verdict": "淘汰"},
}


def main() -> int:
    try:
        with open(SNAP, encoding="utf-8") as fh:
            snap = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(f"快照不可读: {e}", file=sys.stderr)
        return 2
    try:
        with open(REPORT, encoding="utf-8") as fh:
            report = fh.read()
    except OSError as e:
        print(f"报告不可读: {e}", file=sys.stderr)
        return 2

    fails: list[str] = []
    cand = snap.get("candidates", {})

    for name, exp in EXPECT.items():
        got = cand.get(name)
        if not got:
            fails.append(f"{name}: 快照缺失")
            continue
        for field, want in exp.items():
            if field == "verdict":
                continue
            actual = got.get(field)
            if actual != want:
                fails.append(f"{name}.{field}: 快照={actual} 报告={want}")
        if got.get("error"):
            fails.append(f"{name}: 快照含 error={got['error']}")

    # 报告必须体现判定结论
    for name, exp in EXPECT.items():
        v = exp["verdict"]
        # 允许报告写成「— 入场」或「— 淘汰（G4）」等形式
        if not re.search(re.escape(name) + r".{0,80}?" + v, report, re.S):
            fails.append(f"报告未体现 {name} 的判定 {v}")

    # 关键结论词必须在
    for kw in ["活跃度是**入场资格**", "单人维护", "过门",
               "能力对比", "实现语言"]:
        if kw not in report:
            fails.append(f"报告缺少关键表述: {kw!r}")

    print(f"核对 {len(EXPECT)} 个候选 × 快照断言")
    if fails:
        print("\nFAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS 报告数字与快照全部一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
