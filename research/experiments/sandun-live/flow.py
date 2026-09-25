"""SANDUN 真实流程驱动：建项目 → 启动 → 提交需求 → 推进到导出。

对 SANDUN 做**实测**（非文档阅读）：用真实账号走完整链路，记录每步真实行为。

边界：
- 所有者授权使用测试账号，明确要求走一次真实流程。
- 会话 token 存 sandun-live/session.json，已 gitignore，**永不入库**。
- 属 research/experiments/ 可丢弃实验物，不进生产。
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://agentadmin.sandun.cc"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "session.json")

CRED = os.path.join(HERE, "credentials.json")


def _load_credentials() -> tuple[str, str]:
    """从本机凭据文件读取账号密码。

    凭据**不进仓库**（见 .gitignore 的 credentials.json 规则）。
    可用环境变量覆盖，便于在不同机器上运行：
      SANDUN_ACCOUNT / SANDUN_PASSWORD
    """
    acct = os.environ.get("SANDUN_ACCOUNT")
    pwd = os.environ.get("SANDUN_PASSWORD")
    if acct and pwd:
        return acct, pwd
    try:
        with open(CRED, encoding="utf-8") as fh:
            c = json.load(fh)
        return c["account"], c["password"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise SystemExit(
            f"缺少凭据：请在 {CRED} 写入 {{\"account\": ..., \"password\": ...}} "
            f"或设置 SANDUN_ACCOUNT / SANDUN_PASSWORD 环境变量（原因：{e}）") from e
PROJ = os.path.join(HERE, "project.json")
LOG = os.path.join(HERE, "flow-log.jsonl")
_OPENER = urllib.request.build_opener(urllib.request.HTTPSHandler())


# ------------------------------------------------------------------ 基础
def req(path: str, payload=None, method="GET", token=None, timeout=90):
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://sandun.cc",
        "Referer": "https://sandun.cc/",
    }
    if token:
        h["Authorization"] = "Bearer " + token
    data = json.dumps(payload).encode() if payload is not None else None
    url = BASE + path
    if urllib.parse.urlsplit(url).scheme != "https":
        return "ERR", f"拒绝非 https: {url}"
    r = urllib.request.Request(url,  # noqa: S310 (scheme 已校验)
                               data=data, headers=h, method=method)
    try:
        resp = _OPENER.open(r, timeout=timeout)
        return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except (urllib.error.URLError, OSError) as e:
        return "ERR", str(e)


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def save(path, obj):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
    except OSError as e:
        print(f"  保存失败 {path}: {e}", file=sys.stderr)


def log(event: dict) -> None:
    event["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass


def token() -> str:
    t = load(STATE).get("token")
    if not t:
        raise SystemExit("未登录，先跑 login")
    return t


def show(label: str, body: str, limit: int = 1200) -> None:
    try:
        print(f"{label} {json.dumps(json.loads(body), ensure_ascii=False)[:limit]}")
    except json.JSONDecodeError:
        print(f"{label} {body[:limit]}")


# ------------------------------------------------------------------ 步骤
def login() -> str:
    s, b = req("/api/v1/auth/login/password",
               dict(zip(("account", "password"), _load_credentials())), "POST")
    print("login:", s)
    try:
        d = json.loads(b)["data"]
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  登录失败: {e} {b[:200]}", file=sys.stderr)
        raise SystemExit(3) from e
    save(STATE, {"token": d["token"], "refresh_token": d.get("refresh_token"),
                 "obtained_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    return d["token"]


def create(t: str) -> str:
    topic = "2026年A股半导体设备行业投资价值分析"
    s, b = req("/api/projects/save",
               {"topic": topic, "project_mode": "normal"}, "POST", t)
    print("projects/save:", s)
    show("  ", b)
    try:
        j = json.loads(b)
    except json.JSONDecodeError:
        return ""
    d = j.get("data") if isinstance(j.get("data"), dict) else j
    pid = d.get("projectId") or d.get("project_id") or d.get("id") or ""
    if pid:
        save(PROJ, {"project_id": pid, "topic": topic})
        print("  project_id =", pid)
    return pid


def status(t: str) -> dict:
    """从项目列表读当前状态（列表里有 current_phase / phase_status）。"""
    pid = load(PROJ).get("project_id")
    s, b = req("/api/projects/list", None, "GET", t)
    try:
        for pr in (json.loads(b).get("projects") or []):
            if pr.get("id") == pid:
                return pr
    except json.JSONDecodeError:
        pass
    return {}


def start(t: str) -> None:
    p = load(PROJ)
    s, b = req("/api/agent/start",
               {"project_id": p["project_id"], "topic": p["topic"]}, "POST", t)
    print("agent/start:", s)
    show("  ", b)
    log({"event": "start", "status": s})


def message(t: str, text: str, extra: dict | None = None) -> None:
    """发一条对话消息（也用于提交需求单确认）。"""
    p = load(PROJ)
    payload = {"project_id": p["project_id"], "message": text}
    if extra:
        payload.update(extra)
    s, b = req("/api/agent/message", payload, "POST", t)
    print("agent/message:", s)
    show("  ", b, 800)
    log({"event": "message", "text": text, "status": s, "extra": extra or {}})


def watch(t: str, rounds: int = 30, gap: int = 10) -> None:
    """看状态推进，停在需要人工确认处。"""
    for i in range(rounds):
        st = status(t)
        if not st:
            print(f"[{i:>2}] 读不到状态")
        else:
            print(f"[{i:>2}] status={st.get('status')} "
                  f"phase={st.get('current_phase')} "
                  f"phase_status={st.get('phase_status')} "
                  f"updated={str(st.get('updated_at'))[11:19]}")
        if st.get("phase_status") == "awaiting_confirm":
            print("     ⏸ 等待确认，阶段:", st.get("current_phase"))
            return
        time.sleep(gap)


def slides(t: str) -> None:
    """当前项目的页数据（replay 未公开时可能不可读，作为探测）。"""
    pid = load(PROJ).get("project_id")
    for path in [f"/api/replay/{pid}",
                 f"/api/projects/replay/{pid}",
                 f"/api/projects/detail?projectId={pid}"]:
        s, b = req(path, None, "GET", t)
        tag = "JSON" if b.strip().startswith(("{", "[")) else "?"
        print(f"  {s} {tag} {path}  {b[:160]}")


STEPS = {"login": login, "create": create, "start": start, "watch": watch,
         "slides": slides}


def cmd_message(t: str, text: str) -> None:
    message(t, text)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    name, rest = args[0], args[1:]
    if name == "login":
        login()
    elif name == "message":
        if not rest:
            print("用法: flow.py message \"文本\"", file=sys.stderr)
            sys.exit(2)
        cmd_message(token(), " ".join(rest))
    elif name in STEPS:
        STEPS[name](token())
    else:
        print(__doc__)
        sys.exit(2)
