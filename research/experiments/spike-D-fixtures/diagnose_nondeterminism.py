"""诊断 OOXML/ZIP 产物的非确定性来源。

用法：python diagnose_nondeterminism.py A.docx B.docx [...]
逐个比较两次生成产物的内部部件，指出哪些部件字节不同、差异在哪。
"""

from __future__ import annotations

import hashlib
import sys
import zipfile


def parts(path: str) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {i.filename: z.read(i.filename) for i in z.infolist()}


def infos(path: str) -> dict[str, tuple]:
    with zipfile.ZipFile(path) as z:
        return {i.filename: (i.date_time, i.compress_type, i.external_attr,
                             i.create_system) for i in z.infolist()}


def diff(a: str, b: str) -> None:
    print(f"=== {a}")
    print(f"    {b}")
    pa, pb = parts(a), parts(b)
    ia, ib = infos(a), infos(b)

    only_a = set(pa) - set(pb)
    only_b = set(pb) - set(pa)
    if only_a:
        print("  仅 A 有:", sorted(only_a))
    if only_b:
        print("  仅 B 有:", sorted(only_b))

    byte_diff, meta_only_diff = [], []
    for name in sorted(set(pa) & set(pb)):
        if pa[name] != pb[name]:
            byte_diff.append(name)
        elif ia.get(name) != ib.get(name):
            meta_only_diff.append(name)

    print(f"  字节不同的部件: {len(byte_diff)}")
    for n in byte_diff[:20]:
        ha = hashlib.sha256(pa[n]).hexdigest()[:10]
        hb = hashlib.sha256(pb[n]).hexdigest()[:10]
        print(f"    {n:52} {len(pa[n]):>7} vs {len(pb[n]):>7}  {ha} vs {hb}")
    if meta_only_diff:
        print(f"  仅 ZIP 元数据不同（内容相同）: {len(meta_only_diff)}")
        for n in meta_only_diff[:8]:
            print(f"    {n:52} {ia[n]} vs {ib[n]}")

    if byte_diff:
        n = byte_diff[0]
        xa, xb = pa[n], pb[n]
        # 找第一个不同字节
        k = next((i for i in range(min(len(xa), len(xb))) if xa[i] != xb[i]), None)
        if k is not None:
            lo = max(0, k - 90)
            print(f"\n  首个字节差异在 {n} 偏移 {k}：")
            print(f"    A: ...{xa[lo:k+90].decode('utf-8', 'replace')!r}")
            print(f"    B: ...{xb[lo:k+90].decode('utf-8', 'replace')!r}")


if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) % 2 == 0:
        print(__doc__)
        sys.exit(2)
    for i in range(1, len(sys.argv), 2):
        diff(sys.argv[i], sys.argv[i + 1])
        print()
