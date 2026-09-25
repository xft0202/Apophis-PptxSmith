"""SANDUN 真实流程：SSE 全量抓取 + 进度分析。

把事件流完整落盘（jsonl），并按事件类型汇总，输出可读的进度报告。
用于记录真实生成过程的每一步（含耗时、页数、计费、阶段推进）。

用法：python capture.py [秒数]        默认 600 秒（10 分钟）
      python capture.py analyze       只分析已有事件流
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "sse-raw.jsonl")
SNAPSHOT = os.path.join(HERE, "state-snapshots.jsonl")


def _fmt_ts(v) -> str:
    """兼容两种时间戳：早期写入用 epoch 浮点，后改成字符串。"""
    if isinstance(v, (int, float)):
        return time.strftime("%H:%M:%S", time.localtime(v))
    return str(v)[:8]


def _open_log(path: str):
    """打开日志文件（追加），失败时给出明确错误。"""
    try:
        return open(path, "a", encoding="utf-8")
    except OSError as e:
        print(f"无法打开 {path}: {e}", file=sys.stderr)
        raise


def connect(seconds: int) -> int:
    t = flow.token()
    pid = flow.load(flow.PROJ)["project_id"]
    url = f"{flow.BASE}/sse/agent/{pid}?token={urllib.parse.quote(t)}"
    if urllib.parse.urlsplit(url).scheme != "https":
        print("拒绝非 https", file=sys.stderr)
        return 2

    print(f"连接 SSE，持续 {seconds}s（Ctrl+C 可中断）")
    req = urllib.request.Request(url,  # noqa: S310 (scheme 已校验)
                                headers={"User-Agent": "Mozilla/5.0",
                                         "Accept": "text/event-stream",
                                         "Origin": "https://sandun.cc",
                                         "Referer": "https://sandun.cc/"})
    deadline = time.time() + seconds
    n = 0
    with contextlib.closing(_open_log(RAW)) as fh:
        try:
            resp = urllib.request.urlopen(req, timeout=seconds + 15)  # noqa: S310
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code}: {e.read()[:200]}")
            return 1
        except (urllib.error.URLError, OSError) as e:
            print(f"连接失败: {e}")
            return 1
        for raw in resp:
            if time.time() > deadline:
                break
            line = raw.decode("utf-8", "ignore").rstrip("\n")
            if not line:
                continue
            n += 1
            fh.write(json.dumps({"at": time.time(), "line": line},
                                ensure_ascii=False) + "\n")
            fh.flush()
            if line.startswith("data:"):
                try:
                    d = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                ty = d.get("type")
                if ty == "task_progress":
                    dd = d.get("data", {})
                    print(f"  [{time.strftime('%H:%M:%S')}] "
                          f"{dd.get('message')}  (task={dd.get('task_key')})")
                elif ty == "cost_update":
                    dd = d.get("data", {})
                    print(f"      成本 {dd.get('project_cost')} 余 {dd.get('total_available')}")
                elif ty in ("phase_start", "phase_complete", "phase_transition"):
                    print(f"  >>> {ty}: {json.dumps(d.get('data'), ensure_ascii=False)[:160]}")
                elif ty == "awaiting_confirm":
                    print(f"  ⏸ awaiting_confirm: "
                          f"{json.dumps(d.get('data'), ensure_ascii=False)[:200]}")
                elif ty == "style_recommendations_ready":
                    print("  🎨 风格推荐就绪")
    print(f"\n共 {n} 行 -> {os.path.basename(RAW)}")
    return 0


def _read_lines(path: str):
    """逐行读文件，失败时给出明确错误。"""
    try:
        return open(path, encoding="utf-8")
    except OSError as e:
        print(f"无法读 {path}: {e}", file=sys.stderr)
        raise


def analyze() -> int:
    if not os.path.exists(RAW):
        print("没有事件流文件", file=sys.stderr)
        return 1
    types = Counter()
    progresses, costs, phases, confirms = [], [], [], []
    page_status = {}
    with contextlib.closing(_read_lines(RAW)) as fh:
        for ln in fh:
            try:
                o = json.loads(ln)
            except json.JSONDecodeError:
                continue
            line = o.get("line", "")
            if not line.startswith("data:"):
                continue
            try:
                d = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            ty = d.get("type") or "(snapshot)"
            types[ty] += 1
            dd = d.get("data") or {}
            if ty == "task_progress":
                progresses.append((o["at"], dd.get("current"), dd.get("total"),
                                   dd.get("task_key")))
            elif ty == "cost_update":
                costs.append((o["at"], dd.get("project_cost"), dd.get("total_available")))
            elif ty in ("phase_start", "phase_complete", "phase_transition"):
                phases.append((o["at"], ty, dd.get("phase")))
            elif ty == "awaiting_confirm":
                confirms.append((o["at"], json.dumps(dd, ensure_ascii=False)[:200]))
            elif (ty == "artifact_updated" and "status" in dd
                  and "page_key" in dd):
                page_status[dd["page_key"]] = dd["status"]
    print("=== 事件类型统计 ===")
    for k, v in types.most_common():
        print(f"  {k:<32} {v}")

    if not os.path.exists(SNAPSHOT) and not os.path.exists(RAW):
        pass

    if phases:
        print("\n=== 阶段推进 ===")
        for at, ty, ph in phases:
            print(f"  {_fmt_ts(at)} {ty:<18} {ph}")

    if progresses:
        print("\n=== 页进度 ===")
        for at, cur, tot, key in progresses:
            print(f"  {_fmt_ts(at)} {cur}/{tot}  {key}")

    if costs:
        print(f"\n=== 计费（{len(costs)} 次）===")
        print(f"  起步 {costs[0][1]}  末尾 {costs[-1][1]}  余量 {costs[-1][2]}")

    if page_status:
        print(f"\n=== 页面状态（{len(page_status)} 页）===")
        c = Counter(page_status.values())
        print("  ", dict(c))
        for k, v in list(page_status.items())[:20]:
            print(f"    {k:<28} {v}")

    if confirms:
        print(f"\n=== 待确认（{len(confirms)} 次）===")
        for at, s in confirms:
            print(f"  {_fmt_ts(at)} {s}")
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "600"
    if arg == "analyze":
        sys.exit(analyze())
    sys.exit(connect(int(arg)))
