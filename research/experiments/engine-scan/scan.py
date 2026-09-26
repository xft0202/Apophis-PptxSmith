"""PPTX 引擎候选的 G1–G5 活跃度扫描器。

用途：对候选仓库抓取判定 G1–G5 所需的原始数据（发版、提交分布、贡献者集中度），
输出 JSON 供报告引用与复核。

G1 最近 12 个月有正式发版
G2 最近 6 个月有持续提交（非单人偶发）
G3 issue/PR 有维护者响应
G4 贡献者不集中在 1-2 人
G5 有明确版本策略

用法：python scan.py            # 扫全部候选
      python scan.py --verify   # 校验已保存快照的完整性
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
SNAP = os.path.join(HERE, "g1-g5-snapshot.json")
_OPENER = urllib.request.build_opener(urllib.request.HTTPSHandler())

# 候选池：已知候选 + 扩池搜索得到的新候选
CANDIDATES = {
    "Open XML SDK": "dotnet/Open-XML-SDK",
    "PptxGenJS": "gitbrent/PptxGenJS",
    "python-pptx": "scanny/python-pptx",
    "ShapeCrawler": "ShapeCrawler/ShapeCrawler",
    "unioffice": "unidoc/unioffice",
    "Apache POI": "apache/poi",
    "ppt-master": "hugohe3/ppt-master",
    "pptx-automizer": "singerla/pptx-automizer",
    "officegen": "Ziv-Barber/officegen",
    "PPTist": "pipipi-pikachu/PPTist",
    "Presenton": "presenton/presenton",
}

# 扩池用的搜索查询
SEARCH_QUERIES = [
    "pptx in:name,description,readme stars:>200",
    "openxml in:name,description stars:>100",
    "pptx generator",
    "ooxml",
]


def api(path: str, tries: int = 3) -> Any:
    """调 GitHub API；失败重试后返回错误标记而不抛异常。

    返回值是解析后的 JSON（dict/list），或 {"_error": ...} 标记字典。
    """
    for i in range(tries):
        try:
            req = urllib.request.Request(
                "https://api.github.com" + path,
                headers={"User-Agent": "pptXsmith-research",
                         "Accept": "application/vnd.github+json"})
            if urllib.parse.urlsplit(req.full_url).scheme != "https":
                return {"_error": "非 https 端点"}
            return json.loads(_OPENER.open(req, timeout=30).read().decode())
        except urllib.error.HTTPError as e:
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


def scan_repo(repo: str) -> dict[str, Any]:
    d = api(f"/repos/{repo}")
    if not isinstance(d, dict) or "_error" in d or d.get("message"):
        err = d.get("_error") if isinstance(d, dict) else "非预期响应"
        return {"repo": repo, "error": err or d.get("message")}

    lic = d.get("license")
    out: dict[str, Any] = {
        "repo": repo,
        "stars": d.get("stargazers_count"),
        "forks": d.get("forks_count"),
        "archived": d.get("archived"),
        "open_issues": d.get("open_issues_count"),
        "pushed_at": (d.get("pushed_at") or "")[:10],
        "license": lic.get("spdx_id") if isinstance(lic, dict) else None,
        "language": d.get("language"),
    }

    # G1：最近发版
    rel = api(f"/repos/{repo}/releases?per_page=3")
    out["releases"] = ([{"tag": r.get("tag_name"),
                         "published": (r.get("published_at") or "")[:10]}
                        for r in rel] if isinstance(rel, list) else [])

    # G2：近 180 天提交 + 按月分布
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 180 * 86400))
    recent = api(f"/repos/{repo}/commits?since={since}&per_page=100")
    if isinstance(recent, list):
        authors = Counter(((c.get("author") or {}).get("login") or "?")
                          for c in recent)
        bots = sum(v for k, v in authors.items() if is_bot(k))
        out["commits_180d"] = len(recent)
        out["commits_180d_human"] = len(recent) - bots
        out["commits_180d_authors"] = len(authors)
        out["commits_180d_top_authors"] = dict(authors.most_common(5))

    # 最近提交时间与按月分布（用最近 100 条）
    allc = api(f"/repos/{repo}/commits?per_page=100")
    if isinstance(allc, list) and allc:
        dates = [c["commit"]["author"]["date"][:10] for c in allc]
        out["last_commit"] = dates[0]
        out["monthly"] = dict(sorted(Counter(x[:7] for x in dates).items()))

    # G4：贡献者集中度
    con = api(f"/repos/{repo}/contributors?per_page=30")
    if isinstance(con, list) and con:
        tot = sum(x.get("contributions", 0) for x in con)
        if tot:
            out["contributors_top30_commits"] = tot
            out["top_contributor"] = con[0].get("login")
            out["top_contributor_pct"] = round(con[0]["contributions"] / tot * 100)
            out["top3_pct"] = round(
                sum(x["contributions"] for x in con[:3]) / tot * 100)
    return out


def scan_search() -> dict[str, dict[str, Any]]:
    """扩池：跑搜索查询，记录命中仓库（去重）。"""
    seen: dict[str, dict[str, Any]] = {}
    for q in SEARCH_QUERIES:
        d = api("/search/repositories?q=" + urllib.parse.quote(q)
                + "&sort=stars&per_page=15")
        if not isinstance(d, dict) or "_error" in d:
            continue
        items = d.get("items")
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            full = it.get("full_name")
            if not isinstance(full, str):
                continue
            lic = it.get("license")
            seen.setdefault(full, {
                "stars": it.get("stargazers_count"),
                "pushed_at": (it.get("pushed_at") or "")[:10],
                "archived": it.get("archived"),
                "license": lic.get("spdx_id") if isinstance(lic, dict) else None,
                "language": it.get("language"),
                "description": (it.get("description") or "")[:140],
            })
    return seen


def main() -> int:
    if "--verify" in sys.argv:
        try:
            with open(SNAP, encoding="utf-8") as fh:
                s = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            print(f"快照不可读: {e}", file=sys.stderr)
            return 2
        print(f"快照含 {len(s.get('candidates', {}))} 个候选、"
              f"{len(s.get('search_hits', {}))} 个搜索命中")
        miss = [k for k, v in s.get("candidates", {}).items() if v.get("error")]
        print("扫描失败项:", miss or "无")
        return 0

    result = {"scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "candidates": {}, "search_hits": {}}
    for name, repo in CANDIDATES.items():
        r = scan_repo(repo)
        result["candidates"][name] = r
        if r.get("error"):
            print(f"!! {name:<16} {r['error']}")
        else:
            print(f"{name:<16} last={r.get('last_commit')} "
                  f"180d={r.get('commits_180d')}人={r.get('commits_180d_human')} "
                  f"top={r.get('top_contributor')}:{r.get('top_contributor_pct')}%")
    result["search_hits"] = scan_search()
    print(f"\n扩池命中 {len(result['search_hits'])} 个仓库（去重）")

    try:
        with open(SNAP, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)
    except OSError as e:
        print(f"写快照失败: {e}", file=sys.stderr)
        return 1
    print("快照写入:", os.path.basename(SNAP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
