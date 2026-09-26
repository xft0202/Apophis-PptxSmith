"""吸收分类自检 —— 把「博采众长」原则变成可检查的字段。

原则（CONTEXT.md / 票 13 / 地图 Notes）：
  每个候选比较、每个外部样本、每张研究票的产出，
  **必须逐项标注吸收分类**，缺这项即视为未完成。

五个取值：
  可直接复用 / 适合二开 / 仅可借鉴 / 必须隔离 / 应当淘汰

本脚本扫描「比较类」研究报告，检查是否出现该字段。
它只做**存在性检查**，不判断标注是否正确——正确性由人复核。

用法：python check_absorption.py
退出码：0 = 全部具备；1 = 有缺失；2 = 找不到报告
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# 吸收分类的五个固定口径
CATEGORIES = ["可直接复用", "适合二开", "仅可借鉴", "必须隔离", "应当淘汰"]

# 「比较类」报告：对多个候选/外部样本做横向比较，必须带吸收分类
# 判定方式：文件名或正文含比较特征，且列出多个候选
COMPARISON_MARKERS = [
    r"候选", r"横向比较", r"对照", r"筛选", r"竞品", r"反超",
]

# 明确的豁免（非比较类产出）
# 收紧规则：只保留「确实是候选比较」的对象，避免把 README / 纯记录当噪声
EXEMPT_PATTERNS = [
    r"fixture-manifest",        # 输入契约，非候选比较
    r"README\.md$",             # 目录说明，非报告
    r"仓库全量审查",             # 内部审查
    r"企业级工程流程",           # 流程文档
    r"spike-[A-E]_实测记录",     # 单次实验记录：验证「能否做到」，不比较候选
    r"spike-[A-E]_实测报告",
    r"SANDUN与竞品体验基准",     # 体验基准汇总，非技术候选比较
]


def collect_reports() -> list[str]:
    """收集 research/ 下的 markdown 报告。"""
    root = os.path.join(REPO, "research")
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith(".md"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def is_comparison(path: str, text: str) -> bool:
    """判定是否为「对多个候选做横向比较」的报告。

    收紧口径：必须**标题或开头**就体现比较意图，
    避免正文里偶然出现「候选」「对照」等词就被判为比较类。
    """
    name = os.path.basename(path)
    head = text[:600]
    if any(re.search(p, name) or re.search(p, head) for p in EXEMPT_PATTERNS):
        return False
    return any(re.search(m, head) for m in COMPARISON_MARKERS)


def main() -> int:
    reports = collect_reports()
    if not reports:
        print("未找到 research/ 下的报告", file=sys.stderr)
        return 2

    checked = 0
    missing = []
    for p in reports:
        try:
            with open(p, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as e:
            print(f"  读取失败 {p}: {e}", file=sys.stderr)
            continue
        if not is_comparison(p, text):
            continue
        checked += 1
        found = [c for c in CATEGORIES if c in text]
        rel = os.path.relpath(p, REPO)
        if len(found) >= 2:          # 至少落位两个分类才算做了分层
            print(f"  OK   {rel}   分类出现 {len(found)}: {', '.join(found)}")
        else:
            missing.append(rel)
            print(f"  MISS {rel}   仅出现 {len(found)} 个分类")

    print()
    print(f"检查了 {checked} 份比较类报告")
    if missing:
        print("缺少吸收分类（视为未完成）：")
        for m in missing:
            print("  -", m)
        return 1
    print("PASS 全部比较类报告均带吸收分类")
    return 0


if __name__ == "__main__":
    sys.exit(main())
