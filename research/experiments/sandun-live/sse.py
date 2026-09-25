"""通过 SSE 读取 SANDUN 项目的实时状态与对话。

SANDUN 的对话与阶段推进走 SSE（`/sse/agent/{projectId}?token=...`），
REST 侧没有消息/草稿读取端点。本脚本连上 SSE，把事件流落成 jsonl 便于分析。

用法：python sse.py [秒数]   默认 60 秒
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "sse-raw.jsonl")


def main(seconds: int = 60) -> int:
    t = flow.token()
    pid = flow.load(flow.PROJ)["project_id"]
    url = f"{flow.BASE}/sse/agent/{pid}?token={urllib.parse.quote(t)}"
    if urllib.parse.urlsplit(url).scheme != "https":
        print("拒绝非 https", file=sys.stderr)
        return 2

    print(f"连接 SSE: {flow.BASE}/sse/agent/{pid[:8]}…  持续 {seconds}s")
    req = urllib.request.Request(url,  # noqa: S310 (scheme 已在上方校验)
                                 headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/event-stream",
        "Origin": "https://sandun.cc",
        "Referer": "https://sandun.cc/",
    })
    deadline = time.time() + seconds
    try:
        resp = urllib.request.urlopen(req, timeout=seconds + 10)  # noqa: S310
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read()[:300]}")
        return 1
    except (urllib.error.URLError, OSError) as e:
        print(f"连接失败: {e}")
        return 1

    try:
        _consume(resp, deadline, seconds)
    except OSError as e:
        print(f"写日志失败 {RAW}: {e}", file=sys.stderr)
        return 1
    return 0


def _open_log(path: str):
    """打开日志文件，失败时给出明确错误。"""
    try:
        return open(path, "a", encoding="utf-8")
    except OSError as e:
        print(f"无法打开日志 {path}: {e}", file=sys.stderr)
        raise


def _consume(resp, deadline: float, seconds: int) -> None:
    """读事件流并落盘（用 contextlib.closing 保证句柄释放）。"""
    n = 0
    with contextlib.closing(_open_log(RAW)) as fh:
        for raw in resp:
            if time.time() > deadline:
                break
            line = raw.decode("utf-8", "ignore").rstrip("\n")
            if not line:
                continue
            n += 1
            fh.write(json.dumps({"at": time.strftime("%H:%M:%S"),
                                 "line": line}, ensure_ascii=False) + "\n")
            fh.flush()
            if line.startswith("event:"):
                print(f"  {line}")
            elif line.startswith("data:"):
                print(f"    data: {line[5:].strip()[:240]}")
            else:
                print(f"  {line[:200]}")
    print(f"\n共收到 {n} 行，原始流写入 {os.path.basename(RAW)}")
    print(f"（连接时长上限 {seconds}s）")


if __name__ == "__main__":
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    sys.exit(main(secs))
