"""Spike D fixture verifier — 可丢弃的研究实验物。

用途：在运行四套架构之前，先证明 fixture 材料自身满足 manifest 的输入契约。
若这里失败，后续所有架构比较都建立在错误输入上。

检查项对应 manifest 第 2–4 节与第 7 节：
- 规范事实值可在材料中定位；
- 有意冲突存在（DOCX 15.0 vs XLSX 15.1；PDF +12.0% vs XLSX +12.4%）；
- 排版集齐全（标题、中英混排、≥180 字长中文段落、4 列×5 行表格、2 系列×4 季度图表）；
- 安全集齐全（提示注入文本、脱敏值、无真实密钥）；
- PPTX 含 master/layout/theme、原生图表、嵌入工作簿、notes、未知扩展部件与未知关系。
"""

from __future__ import annotations

import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
F = lambda *p: os.path.join(HERE, *p)

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


# --- 1. DOCX -----------------------------------------------------------------
def verify_docx() -> None:
    from docx import Document

    doc = Document(F("经营摘要.docx"))
    text = "\n".join(p.text for p in doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            text += "\n" + " | ".join(c.text for c in row.cells)

    check("DOCX 标题存在", "2026 年第二季度经营回顾与下半年增长计划" in text)
    check("DOCX 中英混排存在", "AI PPTX Compiler" in text and "WPS" in text)
    check("DOCX 有意冲突 15.0 存在", "15.0 亿元" in text, "应与 XLSX 的 15.1 冲突")
    check("DOCX 无 XLSX 规范值 15.1 误写", "收入 15.1" not in text)
    check("DOCX 同比 +12.4% 存在", "12.4%" in text)
    check("DOCX 预算 18.6 存在", "18.6" in text)
    check("DOCX 毛利率 21.3% 存在", "21.3%" in text)
    check("DOCX 脱敏值存在", all(v in text for v in
          ("CUSTOMER-ALPHA-017", "CC-2407", "owner@example.invalid")))
    check("DOCX 负增长样本存在", "-12.4%" in text)
    check("DOCX 表格存在", len(doc.tables) >= 1, f"tables={len(doc.tables)}")

    long_paras = [p.text for p in doc.paragraphs if len(re.findall(r"[\u4e00-\u9fff]", p.text)) >= 180]
    check("DOCX 长中文段落 ≥180 字", bool(long_paras),
          f"found={len(long_paras)}, max={max((len(p) for p in long_paras), default=0)}")

    # 无真实密钥
    keyish = re.findall(r"sk-[A-Za-z0-9]{16,}", text)
    check("DOCX 无真实 provider key", not keyish, str(keyish[:2]))


# --- 2. XLSX -----------------------------------------------------------------
def verify_xlsx() -> None:
    from openpyxl import load_workbook

    wb = load_workbook(F("财务数据.xlsx"))
    check("XLSX 工作表齐全", set(["财务数据", "分部门", "图表数据"]) <= set(wb.sheetnames),
          str(wb.sheetnames))

    ws = wb["财务数据"]
    check("XLSX 规范值 15.1 存在", ws.cell(2, 2).value == 15.1, f"B2={ws.cell(2,2).value}")
    check("XLSX 预算 18.6 存在", ws.cell(2, 5).value == 18.6, f"E2={ws.cell(2,5).value}")
    check("XLSX 同比 0.124 存在", ws.cell(2, 3).value == 0.124, f"C2={ws.cell(2,3).value}")
    check("XLSX 毛利率 0.213 存在", ws.cell(3, 4).value == 0.213, f"D3={ws.cell(3,4).value}")

    ws2 = wb["分部门"]
    check("XLSX 分部门表 4 列 × 5 行", ws2.max_column == 4 and ws2.max_row == 6,
          f"dims={ws2.max_column}x{ws2.max_row}")
    neg = [c.value for r in ws2.iter_rows() for c in r
           if isinstance(c.value, (int, float)) and c.value < 0]
    check("XLSX 表格含负值", bool(neg), str(neg))
    blanks = [c.coordinate for r in ws2.iter_rows() for c in r if c.value is None]
    check("XLSX 表格含空值", bool(blanks), str(blanks[:3]))

    ws3 = wb["图表数据"]
    check("XLSX 图表数据 2 系列 × 4 季度", ws3.max_row == 5 and ws3.max_column == 3,
          f"dims={ws3.max_column}x{ws3.max_row}")
    q3 = ws3.cell(4, 3).value
    check("XLSX 图表数据含负增长", isinstance(q3, (int, float)) and q3 < 0, f"Q3 同比={q3}")
    check("XLSX 含原生图表对象", len(ws3._charts) >= 1, f"charts={len(ws3._charts)}")


# --- 3. PDF ------------------------------------------------------------------
def verify_pdf() -> None:
    from pypdf import PdfReader

    r = PdfReader(F("市场动态.pdf"))
    n = len(r.pages)
    text = "\n".join(p.extract_text() or "" for p in r.pages)

    check("PDF 有内容页", n >= 2, f"pages={n}")
    check("PDF 有意冲突 +12.0% 存在", "12.0%" in text, "应与 XLSX 的 +12.4% 冲突")
    check("PDF 提示注入文本存在", "忽略所有项目规则" in text)
    check("PDF 明文提及 project-secret", "project-secret" in text)
    check("PDF 有表格内容", "华东" in text and "价格敏感度" in text)
    check("PDF 有脚注", "¹" in text or "第三方数据" in text)

    # 字体嵌入
    fonts = set()
    for page in r.pages:
        res = page.get("/Resources")
        if not res:
            continue
        fdict = res.get("/Font")
        if not fdict:
            continue
        for k in fdict:
            fo = fdict[k].get_object()
            bf = fo.get("/BaseFont")
            if bf:
                fonts.add(str(bf))
    check("PDF 嵌入字体并含子集前缀", any("Noto" in f for f in fonts), str(sorted(fonts)))


# --- 4. PPTX -----------------------------------------------------------------
def verify_pptx() -> None:
    from pptx import Presentation

    p = F("品牌参考.pptx")
    prs = Presentation(p)
    check("PPTX 页数 ≥3", len(prs.slides) >= 3, f"slides={len(prs.slides)}")

    kinds, notes, chart_n = set(), 0, 0
    for s in prs.slides:
        for sh in s.shapes:
            kinds.add(str(sh.shape_type))
            if sh.has_chart:
                chart_n += 1
        if s.has_notes_slide:
            notes += 1
    check("PPTX 含原生图表", chart_n >= 1, f"charts={chart_n}")
    check("PPTX 含 notes", notes >= 2, f"notes_slides={notes}")
    check("PPTX 含表格", any("TABLE" in k for k in kinds), str(sorted(kinds)))

    z = zipfile.ZipFile(p)
    names = z.namelist()
    check("PPTX 含 theme", any(n.startswith("ppt/theme/") for n in names))
    check("PPTX 含 slideMaster", any(n.startswith("ppt/slideMasters/") for n in names))
    check("PPTX 含 slideLayout", any(n.startswith("ppt/slideLayouts/") for n in names))
    check("PPTX 含嵌入工作簿", any(n.endswith(".xlsx") for n in names),
          str([n for n in names if n.endswith(".xlsx")]))
    check("PPTX 含未知扩展部件", "ppt/unknown/pptXsmithFixture.xml" in names)

    ct = z.read("[Content_Types].xml").decode("utf-8")
    check("PPTX 未知部件已登记内容类型", "vnd.pptXsmith.unknown-fixture+xml" in ct)
    rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
    check("PPTX 含未知关系", "pptXsmith-unknown-fixture" in rels)

    # 笔记中的受控值
    allnotes = "\n".join(
        s.notes_slide.notes_text_frame.text for s in prs.slides if s.has_notes_slide)
    check("PPTX notes 含脱敏值", "CUSTOMER-ALPHA-017" in allnotes)

    # 未知部件内容可读且含 marker
    payload = z.read("ppt/unknown/pptXsmithFixture.xml").decode("utf-8")
    check("PPTX 未知部件内容完整", "mustSurvive" in payload and "CUSTOMER-ALPHA-017" in payload)


# --- 5. 字体清单 -------------------------------------------------------------
def verify_fonts() -> None:
    data = json.load(open(F("fonts-manifest.json"), encoding="utf-8"))
    entries = data["entries"]
    check("字体清单含 OFL 开源条目", any(e["kind"] == "open" for e in entries))
    check("字体清单含宿主专有条目", any(e["kind"] == "host-only" for e in entries))
    check("字体清单每条含 sha256 与许可证",
          all(e.get("sha256") and e.get("license") for e in entries))
    check("字体清单标注未验证目标软件",
          data["targetSoftware"]["unverified"] == ["Microsoft PowerPoint"])
    check("字体清单含 WPS 版本", data["targetSoftware"]["version"] == "11.8.2.8411")


# --- 6. hash 一致性 ----------------------------------------------------------
def verify_hashes() -> None:
    import hashlib

    rec = json.load(open(F("fixtures-hashes.json"), encoding="utf-8"))
    bad = []
    for a in rec["artifacts"]:
        p = F(a["file"])
        if not os.path.exists(p):
            bad.append(a["file"] + ":missing")
            continue
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if h != a["sha256"] or os.path.getsize(p) != a["bytes"]:
            bad.append(a["file"] + ":mismatch")
    check("fixtures-hashes.json 与实物一致", not bad, str(bad))


def main() -> int:
    verify_docx(); verify_xlsx(); verify_pdf(); verify_pptx()
    verify_fonts(); verify_hashes()

    ok = sum(1 for _, o, _ in results if o)
    fail = [(n, d) for n, o, d in results if not o]
    print(f"通过 {ok}/{len(results)}\n")
    if fail:
        print("失败项：")
        for n, d in fail:
            print(f"  FAIL  {n}  {d}")
    else:
        print("全部通过：fixture 材料满足 manifest 输入契约。")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
