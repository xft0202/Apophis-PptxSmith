"""G1–G5 门槛扫描（第二轮）—— 覆盖去框化调研新发现的候选。

第一轮扫的是「已知的 6 个库」，漏掉了整个 Rust 生态、模板填充路线、
解析路线。本脚本补充新发现候选的门槛判定。

配额说明：GitHub 未认证 API 每小时 60 次 core 调用；每个候选消耗约 5 次
（repo / releases / commits since / contributors / commits recent）。
故每轮约可扫 12 个候选，超限会返回 403，需等重置。

用法：python scan2.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "g1-g5-snapshot-round2.json")
_OPENER = urllib.request.build_opener(urllib.request.HTTPSHandler())

# 按「决策价值」排序：能推翻既有结论的排前面
CANDIDATES = {
    # ---- A. 原生 OOXML 引擎（Rust 生态，可能推翻「Rust 不成熟」的判断）----
    "betteroffice": "openooxml/betteroffice",
    "office_oxide": "yfedoseev/office_oxide",
    "ppt-rs": "yingkitw/ppt-rs",
    # ---- B. 模板填充路线（此前完全遗漏的形态）----
    "pptx-template": "m3dev/pptx-template",
    # ---- C. 解析路线参照（服务 C1–C4 对象清单与关系闭包）----
    "pptxtojson": "pipipi-pikachu/pptxtojson",
    "undoc": "iyulab/undoc",
    # ---- D. 整产品参照（同类产品实际做到什么程度）----
    "genoffice": "genspark-ai/genoffice",
    "ai-to-pptx": "SmartSchoolAI/ai-to-pptx",
    # ---- E. 商业 SDK（能力上限参照；必须隔离但需评估能力）----
    "aspose-foss-py": "aspose-slides-foss/Aspose.Slides-FOSS-for-Python",
    # ---- F. 其它原生引擎补位 ----
    "ppt-rs-alt": "yingkitw/ppt-rs",
    "html2pptx": "abdelkrimkr/html2pptx",
    "pptx-designer": "sunchaokun/pptx-designer",
}


def api(path: str, tries: int = 2):
    """调 GitHub API。403（限流）不重试——重试也没用，需等重置。"""
    for i in range(tries):
        try:
            req = urllib.request.Request(
                "https://api.github.com" + path,
                headers={"User-Agent": "pptXsmith-research",
                         "Accept": "application/vnd.github+json"})
            if urllib.parse.urlsplit(req.full_url).scheme != "https":
                return {"_error": "非 https"}
            return json.loads(_OPENER.open(req, timeout=30).read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                return {"_error": f"限流 HTTP {e.code}"}
            if e.code == 404:
                return {"_error": "404 未找到"}
            if i == tries - 1:
                return {"_error": f"HTTP {e.code}"}
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            if i == tries - 1:
                return {"_error": str(e)}
        time.sleep(2)
    return {"_error": "重试耗尽"}


def is_bot(login: str) -> bool:
    low = (login or "").lower()
    return low.endswith("[bot]") or "dependabot" in low or "copilot" in low


def scan(repo: str) -> dict[str, Any]:
    d = api(f"/repos/{repo}")
    if not isinstance(d, dict) or "_error" in d or d.get("message"):
        err = d.get("_error") if isinstance(d, dict) else "非预期响应"
        return {"repo": repo, "error": err}

    lic = d.get("license")
    out: dict[str, Any] = {
        "repo": repo,
        "stars": d.get("stargazers_count"),
        "archived": d.get("archived"),
        "open_issues": d.get("open_issues_count"),
        "created_at": (d.get("created_at") or "")[:10],
        "pushed_at": (d.get("pushed_at") or "")[:10],
        "license": lic.get("spdx_id") if isinstance(lic, dict) else None,
        "language": d.get("language"),
        "description": (d.get("description") or "")[:200],
    }

    # G1 发版
    rel = api(f"/repos/{repo}/releases?per_page=3")
    out["releases"] = ([{"tag": r.get("tag_name"),
                         "published": (r.get("published_at") or "")[:10]}
                        for r in rel] if isinstance(rel, list) else [])

    # G2 近 180 天提交
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 180 * 86400))
    rc = api(f"/repos/{repo}/commits?since={since}&per_page=100")
    if isinstance(rc, list):
        authors = Counter(((c.get("author") or {}).get("login") or "?") for c in rc)
        bots = sum(v for k, v in authors.items() if is_bot(k))
        out["commits_180d"] = len(rc)
        out["commits_180d_human"] = len(rc) - bots
        out["commits_180d_authors"] = len(authors)
        out["top_author_180d"] = dict(authors.most_common(3))

    # 最后提交时间
    allc = api(f"/repos/{repo}/commits?per_page=1")
    if isinstance(allc, list) and allc:
        out["last_commit"] = allc[0]["commit"]["author"]["date"][:10]

    # G4 贡献者集中度
    con = api(f"/repos/{repo}/contributors?per_page=30")
    if isinstance(con, list) and con:
        tot = sum(x.get("contributions", 0) for x in con)
        if tot:
            out["top_contributor"] = con[0].get("login")
            out["top_contributor_pct"] = round(con[0]["contributions"] / tot * 100)
            out["top3_pct"] = round(
                sum(x["contributions"] for x in con[:3]) / tot * 100)
            out["contributors_count"] = len(con)
    return out


def verdict(r: dict[str, Any]) -> str:
    """按 G1–G5 给门槛判定（预判定，供人复核）。

    ⚠️ 2026-09-26 修正：此前额外加了一条「创建不足 1 年 → 淘汰」，
    但票 13 的 G1–G5 定义里**根本没有这条**——它是我在脚本里自造的规则，
    结果误杀了 betteroffice / office_oxide / genoffice 三个
    「新但极活跃」（近 180 天 91–100 条提交）的候选。

    正确的做法：维护性由**活跃度**判断，不由**年龄**判断。
    新项目归入「观察」，不直接淘汰。
    """
    if r.get("error"):
        return f"无法判定（{r['error']}）"
    fails = []
    fails_hard = []

    # G1：12 个月内有发版
    rels = r.get("releases") or []
    if not rels:
        fails_hard.append("G1无发版")
    else:
        import datetime as _dt
        try:
            pub = _dt.date.fromisoformat(rels[0]["published"])
            if (_dt.date(2026, 9, 26) - pub).days > 365:
                fails_hard.append("G1发版超12月")
        except (ValueError, KeyError):
            fails_hard.append("G1日期异常")

    # G2：近 180 天有提交
    if not r.get("commits_180d"):
        fails_hard.append("G2近180天无提交")

    # G4：头号贡献者
    pct = r.get("top_contributor_pct")
    if pct is None:
        fails.append("G4无数据")
    elif pct >= 80:
        fails.append(f"G4头号{pct}%")

    # 新项目 → 观察（不是淘汰）
    ca = r.get("created_at") or ""
    young = ca >= "2026-01-01"

    if fails_hard:
        return "淘汰（" + "、".join(fails_hard) + "）"
    if young:
        note = "观察（新项目"
        if r.get("commits_180d", 0) >= 30:
            note += "但极活跃"
        if fails:
            note += "；" + "、".join(fails)
        return note + "）"
    if fails:
        return "降级/隔离（" + "、".join(fails) + "）"
    return "过门"


def main() -> int:
    result: dict[str, Any] = {"scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                             "candidates": {}}
    for name, repo in CANDIDATES.items():
        r = scan(repo)
        r["verdict"] = verdict(r)
        result["candidates"][name] = r
        if r.get("error"):
            print(f"!! {name:<16} {r['error']}")
        else:
            print(f"{name:<16} {r['verdict']}")
            print(f"     ★{r.get('stars')} {r.get('language')} {r.get('license')} "
                  f"创建={r.get('created_at')} 最后提交={r.get('last_commit')}")
            print(f"     近180天提交={r.get('commits_180d')} "
                  f"贡献者集中度={r.get('top_contributor_pct')}%")
        time.sleep(0.5)

    try:
        with open(SNAP, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)
        print(f"\n快照写入 {os.path.basename(SNAP)}")
    except OSError as e:
        print(f"写快照失败: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
