"""PptxSmith 能力实测：生成一份含 A 级原生语义对象的 PPTX。

目的：验证本项目承诺的「铁三角」中可实测的两条：
  1. A 级原生语义输出——图表带嵌入工作簿、改数值图表更新、表格可增行；
  2. 中文量字预测——长中文段落的折行与行高是否与目标软件渲染一致。

这是研究实验物（ADR-0006「可丢弃」），不是产品脚手架。
输出：research/experiments/spike-E/sample_pptxsmith.pptx
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import zipfile

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

OUT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)

# 与 Spike D fixture 同一组固定事实，保证可比性
TITLE = "2026 年第二季度经营回顾与下半年增长计划"
SUBTITLE = "从经营结果到行动闭环"
MIXED = "AI PPTX Compiler / PowerPoint / WPS / Q2 中英混排"
LONG_CN = (
    "第二季度公司整体经营保持稳健增长，收入结构与毛利水平同步改善，但在部门之间仍存在明显分化："
    "华东与华南区域的交付节奏好于预期，华北区域的回款周期偏长，导致现金流净额与经营利润之间出现"
    "时间性缺口。同时，外部市场环境的不确定性上升，客户对价格与交付周期的敏感度提高，我们在报价"
    "环节需要更充分地使用标准化的成本模型，避免过去的经验判断带来毛利损失。"
)
INK = RGBColor(0x1A, 0x1A, 0x1A)
BRAND = RGBColor(0x00, 0x52, 0xD4)
MUTED = RGBColor(0x64, 0x74, 0x8B)

# 量字：用 fontTools 读真实字体的 advance width 做折行预测
FONT_REG = os.path.join(os.path.dirname(OUT), "spike-D-fixtures", "NotoSansSC-Regular.ttf")


def measure(text: str, font_path: str, size_pt: float, box_w_in: float) -> dict:
    """按真实字体度量做中文折行与高度预测（量字引擎的最小原型）。"""
    from fontTools.ttLib import TTFont
    f = TTFont(font_path, lazy=True)
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    upm = f["head"].unitsPerEm
    hhea = f["hhea"]
    # 行高因子（Spike B 已证明纯度量会低估，这里记录原始值）
    raw_factor = (hhea.ascent - hhea.descent + hhea.lineGap) / upm

    limit = int(box_w_in * 72.0 / size_pt * upm)   # 一行可用 advance 总和
    lines, cur = [], 0
    for ch in text:
        g = cmap.get(ord(ch))
        if g is None:
            g = cmap.get(ord(" ")) or ".notdef"
        w = hmtx[g][0]
        if cur + w > limit and cur > 0:
            lines.append(cur)
            cur = w
        else:
            cur += w
    if cur:
        lines.append(cur)
    n = max(1, len(lines))
    f.close()
    return {
        "font": os.path.basename(font_path),
        "sizePt": size_pt,
        "boxWidthIn": box_w_in,
        "lines": n,
        "rawLineFactor": round(raw_factor, 4),
        "predictedHeightIn": round(n * size_pt * raw_factor / 72.0, 4),
    }


def build() -> str:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)   # 16:9

    blank = prs.slide_layouts[6]

    # ---------- P1 封面 ----------
    s = prs.slides.add_slide(blank)
    t = s.shapes.add_textbox(Inches(0.9), Inches(2.2), Inches(11.5), Inches(1.6))
    p = t.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = TITLE
    r.font.size = Pt(40)
    r.font.bold = True
    r.font.color.rgb = INK
    r.font.name = "Noto Sans SC"

    sub = s.shapes.add_textbox(Inches(0.95), Inches(3.9), Inches(11.0), Inches(0.8))
    p2 = sub.text_frame.paragraphs[0]
    r2 = p2.add_run()
    r2.text = SUBTITLE
    r2.font.size = Pt(18)
    r2.font.color.rgb = BRAND
    r2.font.name = "Noto Sans SC"

    # 装饰竖线
    ln = s.shapes.add_shape(1, Inches(0.9), Inches(2.25), Pt(4), Inches(2.0))
    ln.fill.solid()
    ln.fill.fore_color.rgb = BRAND
    ln.line.fill.background()

    mx = s.shapes.add_textbox(Inches(0.95), Inches(5.0), Inches(11.0), Inches(0.5))
    pm = mx.text_frame.paragraphs[0]
    rm = pm.add_run()
    rm.text = MIXED
    rm.font.size = Pt(12)
    rm.font.color.rgb = MUTED
    rm.font.name = "Noto Sans SC"

    # ---------- P2 原生图表（A 级语义核心）----------
    s2 = prs.slides.add_slide(blank)
    h = s2.shapes.add_textbox(Inches(0.6), Inches(0.45), Inches(12.0), Inches(0.7))
    rh = h.text_frame.paragraphs[0].add_run()
    rh.text = "季度营业收入与同比"
    rh.font.size = Pt(26)
    rh.font.bold = True
    rh.font.color.rgb = INK
    rh.font.name = "Noto Sans SC"

    cd = CategoryChartData()
    cd.categories = ["Q1", "Q2", "Q3", "Q4"]
    cd.add_series("营业收入（亿元）", (12.4, 15.1, 14.6, 18.6))
    cd.add_series("同比", (0.086, 0.124, -0.037, 0.093))
    gf = s2.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,
                             Inches(0.6), Inches(1.35), Inches(8.0), Inches(5.4), cd)
    ch = gf.chart
    ch.has_title = True
    ch.chart_title.text_frame.text = "季度营业收入与同比"
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.font.size = Pt(11)
    ch.font.name = "Noto Sans SC"

    # ---------- P3 表格 + 长中文段落 ----------
    s3 = prs.slides.add_slide(blank)
    h3 = s3.shapes.add_textbox(Inches(0.6), Inches(0.45), Inches(12.0), Inches(0.7))
    rh3 = h3.text_frame.paragraphs[0].add_run()
    rh3.text = "分部门经营概览"
    rh3.font.size = Pt(26)
    rh3.font.bold = True
    rh3.font.color.rgb = INK
    rh3.font.name = "Noto Sans SC"

    rows = [
        ["部门", "收入（亿元）", "毛利率", "同比"],
        ["华东", "6.4", "23.1%", "+15.8%"],
        ["华南", "4.1", "22.6%", "+12.1%"],
        ["华北", "3.2", "17.2%", "-4.1%"],
        ["其他", "1.4", "—", "+3.5%"],
        ["合计", "15.1", "21.3%", "+12.4%"],
    ]
    tb = s3.shapes.add_table(len(rows), 4, Inches(0.6), Inches(1.3),
                             Inches(5.6), Inches(2.4)).table
    for ri, row in enumerate(rows):
        for ci, v in enumerate(row):
            c = tb.cell(ri, ci)
            c.text = v
            for para in c.text_frame.paragraphs:
                para.alignment = PP_ALIGN.CENTER
                for run in para.runs:
                    run.font.size = Pt(11)
                    run.font.name = "Noto Sans SC"
                    if ri == 0:
                        run.font.bold = True
            c.vertical_anchor = MSO_ANCHOR.MIDDLE

    # 长中文段落：用真实度量预测高度，再看 WPS 是否溢出
    box_w = 6.6
    m = measure(LONG_CN, FONT_REG, 12, box_w)
    box = s3.shapes.add_textbox(Inches(6.5), Inches(1.3), Inches(box_w), Inches(m["predictedHeightIn"]))
    tf = box.text_frame
    tf.word_wrap = True
    tf.text = LONG_CN
    for para in tf.paragraphs:
        for run in para.runs:
            run.font.size = Pt(12)
            run.font.name = "Noto Sans SC"
            run.font.color.rgb = INK

    # 输入事实对照（用于零改写核对）
    facts = s3.shapes.add_textbox(Inches(6.5), Inches(4.2), Inches(box_w), Inches(2.2))
    ftf = facts.text_frame
    ftf.word_wrap = True
    ftf.text = ("固定事实（来自 XLSX 规范值）：\n"
                "  营业收入 15.1 亿元\n  预算 18.6 亿元\n  同比 +12.4%\n  毛利率 21.3%\n"
                "OCR/C1 探针目标：图表 Q2 营收 15.1 → 88.8")
    for para in ftf.paragraphs:
        for run in para.runs:
            run.font.size = Pt(11)
            run.font.color.rgb = MUTED
            run.font.name = "Noto Sans SC"

    # ---------- P4 notes 页 ----------
    s3.notes_slide.notes_text_frame.text = (
        "受控信息：客户代号 CUSTOMER-ALPHA-017，成本中心 CC-2407，联系人 owner@example.invalid。"
    )

    path = os.path.join(OUT, "sample_pptxsmith.pptx")
    prs.save(path)

    return path, m


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def inspect(path: str) -> dict:
    """解包检查：原生语义部件是否齐全。"""
    z = zipfile.ZipFile(path)
    names = z.namelist()
    res = {
        "slides": len([n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)]),
        "charts": [n for n in names if n.startswith("ppt/charts/chart")],
        "embeddings": [n for n in names if n.endswith(".xlsx")],
        "notesSlides": [n for n in names if n.startswith("ppt/notesSlides/notesSlide")],
        "theme": [n for n in names if n.startswith("ppt/theme/")],
        "media": [n for n in names if n.startswith("ppt/media/")],
        "svgParts": [n for n in names if n.endswith(".svg")],
        "totalParts": len(names),
    }
    # 嵌入工作簿里读出真实数值
    if res["embeddings"]:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(z.read(res["embeddings"][0])))
        ws = wb.worksheets[0]
        res["embeddedWorkbookCells"] = [
            [ws.cell(r, c).value for c in range(1, 6)] for r in range(1, 7)
        ]
    # 图表缓存值
    if res["charts"]:
        cx = z.read(res["charts"][0]).decode("utf-8", "ignore")
        res["chartCachedValues"] = re.findall(r"<c:pt idx=\"\d+\"><c:v>([^<]+)</c:v>", cx)
        res["chartHasExternalData"] = "externalData" in cx
        res["chartSeriesNames"] = re.findall(r"<c:tx>.*?<c:v>([^<]+)</c:v>", cx, re.S)
    z.close()
    return res


if __name__ == "__main__":
    path, m = build()
    info = inspect(path)
    print("生成:", path, os.path.getsize(path), "bytes")
    print("\n量字预测:", json.dumps(m, ensure_ascii=False, indent=1))
    print("\n解包检查:", json.dumps(info, ensure_ascii=False, indent=1))
    with open(os.path.join(OUT, "sample_pptxsmith.json"), "w", encoding="utf-8") as f:
        json.dump({"measure": m, "parts": info,
                   "sha256": _sha256(path)},
                  f, ensure_ascii=False, indent=1)
