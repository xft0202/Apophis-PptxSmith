"""解包分析 SANDUN 导出的 PPTX 产物 —— 验证其 A 级语义能力。

关注点：
1. 图表是原生 chart part（ppt/charts/chart*.xml）还是图片/形状？
2. 是否存在嵌入工作簿（ppt/embeddings/*.xlsx）—— A 级语义的铁证？
3. 文字是真文本还是路径/图片？
4. 表格是原生 graphicFrame 表格还是拼出来的形状？
5. 字体如何引用（嵌入式？还是要求用户安装？）

用法：python inspect_pptx.py <pptx路径>
"""

from __future__ import annotations

import json
import os
import re
import sys
import zipfile
from collections import Counter

EMU_PER_INCH = 914400


def inspect(path: str) -> dict:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        res: dict = {"file": os.path.basename(path),
                     "bytes": os.path.getsize(path)}

        slides = sorted(n for n in names
                        if re.match(r"ppt/slides/slide\d+\.xml$", n))
        res["slides"] = len(slides)
        res["charts"] = sorted(n for n in names if n.startswith("ppt/charts/chart"))
        res["embeddings"] = sorted(n for n in names if n.endswith((".xlsx", ".xls")))
        res["media"] = sorted(n for n in names if n.startswith("ppt/media/"))
        res["svg"] = sorted(n for n in names if n.endswith(".svg"))
        res["notesSlides"] = sorted(n for n in names
                                    if n.startswith("ppt/notesSlides/notesSlide"))
        res["fonts"] = sorted(n for n in names if n.startswith("ppt/fonts/"))
        res["theme"] = sorted(n for n in names if n.startswith("ppt/theme/"))
        res["totalParts"] = len(names)
        res["hasChartXml"] = bool(res["charts"])
        res["hasEmbeddedWorkbook"] = bool(res["embeddings"])

        # 判定媒体类型
        media_ext = Counter(os.path.splitext(m)[1].lower() for m in res["media"])
        res["mediaExt"] = dict(media_ext)

        # 逐页分析图形类型
        graphic_types = Counter()
        table_count = 0
        chart_refs = 0
        pic_count = 0
        text_runs = 0
        sp_count = 0
        for s in slides:
            xml = z.read(s).decode("utf-8", "ignore")
            for m in re.finditer(r"<a:graphicData\s+uri=\"([^\"]+)\"", xml):
                graphic_types[m.group(1).split("/")[-1]] += 1
            table_count += len(re.findall(r"<a:tbl>", xml))
            chart_refs += len(re.findall(r"<c:chart\b", xml))
            pic_count += len(re.findall(r"<p:pic>", xml))
            sp_count += len(re.findall(r"<p:sp>", xml))
            text_runs += len(re.findall(r"<a:t>", xml))
        res["graphicTypes"] = dict(graphic_types)
        res["tables"] = table_count
        res["chartRefs"] = chart_refs
        res["pictures"] = pic_count
        res["shapes"] = sp_count
        res["textRuns"] = text_runs

        # 字体引用
        fonts = Counter()
        for s in slides:
            xml = z.read(s).decode("utf-8", "ignore")
            for m in re.finditer(r'typeface="([^"]+)"', xml):
                fonts[m.group(1)] += 1
        res["typefaces"] = dict(fonts.most_common(12))

        # 若存在图表部件，看其缓存与外部数据
        if res["charts"]:
            cx = z.read(res["charts"][0]).decode("utf-8", "ignore")
            res["chartCachedValues"] = re.findall(
                r"<c:pt idx=\"\d+\"><c:v>([^<]+)</c:v>", cx)[:20]
            res["chartHasExternalData"] = "externalData" in cx
            res["chartTypes"] = re.findall(r"<c:(\w+Chart)>", cx)
    return res


def _write_json(path: str, obj: dict) -> bool:
    """写 JSON 结果文件，失败时给出明确错误。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        return True
    except OSError as e:
        print(f"写入失败 {path}: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    r = inspect(sys.argv[1])
    print(json.dumps(r, ensure_ascii=False, indent=1))
    out = os.path.splitext(sys.argv[1])[0] + ".inspect.json"
    if _write_json(out, r):
        print("\n结果已写入:", out)
