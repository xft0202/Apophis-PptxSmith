"""核对 SANDUN 实测报告中的每个数字是否与原始数据一致。

教训背景：初版报告因 replayId 与案例名错配，把「小米」与「正泰」的
页数/图表数/时间线数字张冠李戴。本脚本把报告断言逐个对回原始 JSON，
防止同类错误再次发生。

用法：python verify_report_claims.py
退出码：0 = 全部一致；1 = 有不符
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "replay-data")
REPORT = os.path.abspath(os.path.join(
    HERE, "..", "..", "2026-09-25_SANDUN全流程实测报告.md"))
if not os.path.exists(REPORT):
    raise SystemExit(f"报告路径不存在，请核对目录结构: {REPORT}")

# 期望值（从原始数据独立计算得出，写入前先人工确认）
EXPECT = {
    "Dify产品技术架构": {"slides": 12, "timeline": 190, "charts": 2,
                        "chart_types": {"progress": 1, "horizontal-bar": 1},
                        "svg_len": 94902, "rect": 149},
    "北京5日游攻略": {"slides": 14, "timeline": 208, "charts": 3,
                     "chart_types": {"donut": 2, "horizontal-bar": 1},
                     "svg_len": 114574, "rect": 209},
    "小米2025Q3业绩报告": {"slides": 23, "timeline": 305, "charts": 19,
                          "chart_types": {"bar": 14, "line": 3, "pie": 2},
                          "svg_len": 179529, "rect": 297},
    "正泰电器企业介绍": {"slides": 13, "timeline": 269, "charts": 6,
                        "chart_types": {"bar": 6},
                        "svg_len": 98800, "rect": 136},
}

# 每个案例的 project.title 必须包含的关键词（防 replayId 错配）
TITLE_EXPECT = {
    "Dify产品技术架构": ["Dify"],
    "北京5日游攻略": ["北京", "攻略"],
    "小米2025Q3业绩报告": ["小米"],
    "正泰电器企业介绍": ["正泰"],
}


def _load_json(path: str) -> dict | None:
    """读 JSON，失败时打印原因并返回 None。"""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as e:
        print(f"  读取失败 {path}: {e}", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"  JSON 解析失败 {path}: {e}", file=sys.stderr)
    return None


def _load_text(path: str) -> str | None:
    """读文本，失败时打印原因并返回 None。"""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as e:
        print(f"  读取失败 {path}: {e}", file=sys.stderr)
        return None


def main() -> int:
    fails: list[str] = []
    report = _load_text(REPORT)
    if report is None:
        return 2

    for name, exp in EXPECT.items():
        p = os.path.join(DATA, name + ".json")
        j = _load_json(p)
        if j is None:
            fails.append(f"{name}: 数据文件缺失或不可读")
            continue
        title = (j.get("project") or {}).get("title", "")
        svg = "\n".join((s.get("content") or "") for s in j["slides"])
        slots = re.findall(
            r'data-chart-slot-id="[^"]+"\s+data-chart-type="([^"]+)"', svg)
        got = {
            "slides": len(j["slides"]),
            "timeline": len(j["timeline"]),
            "charts": len(slots),
            "chart_types": dict(Counter(slots)),
            "svg_len": len(svg),
            "rect": len(re.findall(r"<rect", svg)),
        }
        # 标题防错配
        for kw in TITLE_EXPECT[name]:
            if kw not in title:
                fails.append(f"{name}: project.title 缺少关键词 {kw}（实际 {title!r}）")
        for k, v in exp.items():
            if got[k] != v:
                fails.append(f"{name}.{k}: 数据={got[k]} 报告={v}")
        print(f"  {name:<20} title={title[:34]:<36} "
              f"slides={got['slides']:>3} charts={got['charts']:>2}")

    # 报告里不得再出现错配时的旧数字组合
    stale = [
        ("| 小米 2025Q3 业绩 | 6 |", "旧表中「小米 6 个图表」的错配值"),
        ("| 正泰电器企业介绍 | 19 |", "旧表中「正泰 19 个图表」的错配值"),
        ("从 `timeline` 的 269 条事件中提取", "把正泰的 timeline 数写成小米的"),
        ("一份 13 页的稿子（小米 Q3）", "把正泰的页数写成小米的"),
    ]
    for pat, why in stale:
        if pat in report:
            fails.append(f"报告仍含旧错配内容：{why} -> {pat!r}")

    # 关键结论必须仍在报告中
    must_have = [
        "chartPlans", "imagePlans", "diagramPlans",
        "data-chart-slot-id", "不存在可编辑的数据模型",
        "版式骨架", "HarmonyOS",
    ]
    for m in must_have:
        if m not in report:
            fails.append(f"报告缺少关键结论词：{m!r}")

    print()
    if fails:
        print("FAIL 以下断言不成立：")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS 报告断言与原始数据全部一致，且无误配残留")
    return 0


if __name__ == "__main__":
    sys.exit(main())
