"""确定性回归测试：证明 fixture 生成器每次产出相同字节。

为什么需要它：一次「脚本崩溃但比对仍报通过」的假阳性，差点让不可复现的
fixture 被当成可复现。本测试强制校验生成器退出码为 0，再比对产物 hash。

用法：python test_determinism.py
退出码：0 = 全部确定；1 = 有不一致；2 = 生成器失败
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "generate_fixtures.py")
ARTIFACTS = ["经营摘要.docx", "财务数据.xlsx", "市场动态.pdf",
             "品牌参考.pptx", "fonts-manifest.json"]


def sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run_generator() -> int:
    r = subprocess.run([sys.executable, GEN], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=HERE)
    if r.returncode != 0:
        print("生成器失败，stderr 末段：")
        print("\n".join((r.stderr or "").strip().split("\n")[-12:]))
    return r.returncode


def snapshot(dst: str) -> dict:
    out = {}
    for a in ARTIFACTS:
        src = os.path.join(HERE, a)
        if not os.path.exists(src):
            raise SystemExit(f"产物缺失: {a}")
        shutil.copy2(src, dst)
        out[a] = sha(src)
    return out


def main() -> int:
    # 第一轮
    if run_generator() != 0:
        return 2
    with tempfile.TemporaryDirectory() as t1:
        first = snapshot(t1)

        # 第二轮（确保跨秒边界）
        import time
        time.sleep(3)
        if run_generator() != 0:
            return 2
        second = {a: sha(os.path.join(HERE, a)) for a in ARTIFACTS}

        # 三轮：从第一轮快照恢复后再生成，验证不依赖历史状态
        for a in ARTIFACTS:
            shutil.copy2(os.path.join(t1, a), os.path.join(HERE, a))
        if run_generator() != 0:
            return 2
        third = {a: sha(os.path.join(HERE, a)) for a in ARTIFACTS}

    print(f"{'产物':<26} {'轮1==轮2':<10} {'轮1==轮3':<10} sha256[:16]")
    bad = []
    for a in ARTIFACTS:
        ok12 = first[a] == second[a]
        ok13 = first[a] == third[a]
        if not (ok12 and ok13):
            bad.append(a)
        print(f"{a:<26} {'一致' if ok12 else '不一致':<10} "
              f"{'一致' if ok13 else '不一致':<10} {first[a][:16]}")

    print()
    if bad:
        print(f"FAIL 非确定性产物: {bad}")
        return 1
    print("PASS 全部产物字节确定（三轮一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
