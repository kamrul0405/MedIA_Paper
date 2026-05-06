"""
Build the v85 MedIA submission PDF from Manuscript_v85_for_MedIA.md.

Renders the markdown to a Times-Roman, single-column letter-size PDF using
ReportLab. Auto-embeds main + Extended Data figures wherever a caption block
contains a `Source image: figures/.../*.png` reference, scaled to page width.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MS_DIR = ROOT / "manuscript"
SRC_MD = MS_DIR / "Manuscript_v85_for_MedIA.md"
OUT_PDF = MS_DIR / "Manuscript_v85_for_MedIA.pdf"
HEADER = "Structural priors vs learned models in longitudinal post-treatment brain-tumour MRI"
JOURNAL = "Medical Image Analysis (Elsevier)"

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)
from PIL import Image as PILImage

PAGE_W, PAGE_H = letter
LM = RM = 0.9 * inch
TM = BM = 0.9 * inch
TW = PAGE_W - LM - RM

styles = getSampleStyleSheet()


def mkstyle(name, parent_name="Normal", **kw):
    p = styles[parent_name] if parent_name in styles else styles["Normal"]
    return ParagraphStyle(name, parent=p, **kw)


TITLE = mkstyle("ms_title", fontName="Times-Bold", fontSize=15, leading=20,
                alignment=TA_CENTER, spaceBefore=0, spaceAfter=10)
AUTH = mkstyle("ms_auth", fontName="Times-Roman", fontSize=11, leading=14,
               alignment=TA_CENTER, spaceAfter=4)
JRNL = mkstyle("ms_jrnl", fontName="Times-Italic", fontSize=10, leading=13,
               alignment=TA_CENTER, spaceAfter=12)
H1 = mkstyle("ms_h1", fontName="Times-Bold", fontSize=12.5, leading=16,
             spaceBefore=12, spaceAfter=4)
H2 = mkstyle("ms_h2", fontName="Times-Bold", fontSize=11, leading=14,
             spaceBefore=8, spaceAfter=3)
H3 = mkstyle("ms_h3", fontName="Times-BoldItalic", fontSize=10.5, leading=13.5,
             spaceBefore=6, spaceAfter=3)
BODY = mkstyle("ms_body", fontName="Times-Roman", fontSize=10.2, leading=13.8,
               alignment=TA_JUSTIFY, spaceAfter=4)
ABST = mkstyle("ms_abst", fontName="Times-Roman", fontSize=10, leading=13.5,
               leftIndent=14, rightIndent=14, alignment=TA_JUSTIFY,
               spaceBefore=4, spaceAfter=8)
CAP = mkstyle("ms_cap", fontName="Times-Roman", fontSize=8.8, leading=11.5,
              leftIndent=8, rightIndent=8, spaceAfter=6)
TBCELL = mkstyle("ms_tc", fontName="Times-Roman", fontSize=8.2, leading=10.5,
                 spaceAfter=0)
TBHEAD = mkstyle("ms_th", fontName="Times-Bold", fontSize=8.2, leading=10.5,
                 spaceAfter=0)
BULL = mkstyle("ms_bull", fontName="Times-Roman", fontSize=10.2, leading=13.5,
               leftIndent=14, firstLineIndent=-10, spaceAfter=3)


def inline(text):
    text = re.sub(r'\[\^(\w+)\]', r'<super>\1</super>', text)
    text = re.sub(r'\*\*\*([^*]+)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" size="9">\1</font>', text)
    text = re.sub(r'&(?!(amp|lt|gt|quot|apos);)', r'&amp;', text)
    text = text.replace('---', '—').replace('--', '–')
    text = text.replace('π*', 'pi*').replace('π_stable', 'pi_stable')
    text = text.replace('τ', 'tau').replace('σ', 'sigma').replace('Δ', 'Delta')
    text = text.replace('≤', '&lt;=').replace('≥', '&gt;=').replace('±', '+/-')
    text = re.sub(r'\$\$([^$]+)\$\$', lambda m: '<i>' + m.group(1).replace('\\', '') + '</i>', text)
    text = re.sub(r'\$([^$]+)\$', lambda m: '<i>' + m.group(1).replace('\\', '') + '</i>', text)
    return text.strip()


def safe_para(text, style):
    text = text.strip()
    if not text:
        return None
    try:
        return Paragraph(text, style)
    except Exception:
        clean = re.sub(r'<[^>]+>', '', text)
        clean = re.sub(r'&\w+;', '', clean)
        try:
            return Paragraph(clean, style)
        except Exception:
            return None


def parse_pipe_table(lines):
    rows = []
    for line in lines:
        if re.match(r'^\s*\|[-: |]+\|\s*$', line):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if cells:
            rows.append(cells)
    if not rows:
        return []
    max_cols = max(len(r) for r in rows)
    norm = []
    for i, r in enumerate(rows):
        while len(r) < max_cols:
            r.append('')
        style = TBHEAD if i == 0 else TBCELL
        norm.append([safe_para(inline(c), style) or Paragraph('', style) for c in r])
    col_w = TW / max_cols
    t = Table(norm, colWidths=[col_w] * max_cols, repeatRows=1)
    t.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8.2),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEEEEE')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#AAAAAA')),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return [Spacer(1, 5), t, Spacer(1, 6)]


def fit_image(path, max_w=TW, max_h=PAGE_H - TM - BM - 1.2 * inch):
    """Open image, scale to fit max_w/max_h, return ReportLab Image."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        with PILImage.open(p) as im:
            iw, ih = im.size
        scale = min(max_w / iw, max_h / ih, 1.0)
        return Image(str(p), width=iw * scale, height=ih * scale)
    except Exception as e:
        print(f"  WARN: failed to embed {path}: {e}")
        return None


def parse_markdown(md_text):
    story = []
    lines = md_text.split('\n')
    n = len(lines)
    i = 0
    para_buf = []
    in_abstract = False

    def flush():
        if not para_buf:
            return
        text = ' '.join(l.strip() for l in para_buf if l.strip())
        if not text.strip():
            para_buf.clear()
            return

        # Figure caption block: starts with **Figure N.** or **Extended Data Figure N.**
        m_fig = re.match(r'^\*\*((?:Extended Data )?Figure \d+(?:[a-z])?)\.\*\*', text)
        if m_fig:
            # Locate `Source image: figures/...` reference
            m_src = re.search(r'Source image:\s*`?([^`\s]+\.(?:png|jpg|jpeg|tif|tiff))`?', text)
            img_path = None
            if m_src:
                rel = m_src.group(1).strip()
                cand = ROOT / rel
                if cand.exists():
                    img_path = cand
            if img_path:
                img = fit_image(img_path)
                if img:
                    story.append(Spacer(1, 6))
                    story.append(img)
                    story.append(Spacer(1, 3))
            cap = safe_para(inline(text), CAP)
            if cap:
                story.append(KeepTogether([cap, Spacer(1, 4)]))
            para_buf.clear()
            return

        st = ABST if in_abstract else BODY
        p = safe_para(inline(text), st)
        if p:
            story.append(p)
        para_buf.clear()

    while i < n and not lines[i].strip():
        i += 1

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if re.match(r'^---+\s*$', stripped) or re.match(r'^\*\*\*+\s*$', stripped):
            flush()
            story.append(Spacer(1, 3))
            story.append(HRFlowable(width=TW, thickness=0.5,
                                    color=colors.HexColor('#888888')))
            story.append(Spacer(1, 3))
            i += 1
            continue

        hm = re.match(r'^(#{1,4})\s+(.*)', stripped)
        if hm:
            flush()
            level = len(hm.group(1))
            htext = hm.group(2).strip()
            if level == 1 and not story:
                story.append(safe_para(inline(htext), TITLE))
                story.append(Spacer(1, 4))
                i += 1
                continue
            in_abstract = htext.lower() == 'abstract'
            if level == 1:
                story.append(Spacer(1, 8))
                story.append(HRFlowable(width=TW, thickness=1,
                                        color=colors.HexColor('#333333')))
                story.append(Spacer(1, 2))
                p = safe_para(inline(htext), H1)
            elif level == 2:
                p = safe_para(inline(htext), H2)
            elif level == 3:
                p = safe_para(inline(htext), H3)
            else:
                p = safe_para('<b>' + inline(htext) + '</b>', BODY)
            if p:
                story.append(p)
            i += 1
            continue

        if stripped.startswith('|'):
            flush()
            tbl_lines = []
            while i < n and lines[i].strip().startswith('|'):
                tbl_lines.append(lines[i])
                i += 1
            story += parse_pipe_table(tbl_lines)
            continue

        if re.match(r'^[-*+]\s', stripped):
            flush()
            item = re.sub(r'^[-*+]\s+', '', stripped)
            p = safe_para('• ' + inline(item), BULL)
            if p:
                story.append(p)
            i += 1
            continue

        nm = re.match(r'^(\d+)\.\s+(.*)', stripped)
        if nm:
            flush()
            p = safe_para(nm.group(1) + '. ' + inline(nm.group(2)), BULL)
            if p:
                story.append(p)
            i += 1
            continue

        if not stripped:
            flush()
            story.append(Spacer(1, 2))
            i += 1
            continue

        para_buf.append(line)
        i += 1

    flush()
    return story


def make_page_fn(header, journal):
    def fn(canvas, doc):
        canvas.saveState()
        canvas.setFont('Times-Roman', 9)
        pn = canvas.getPageNumber()
        canvas.drawCentredString(PAGE_W / 2, 0.45 * inch, str(pn))
        if pn > 1:
            canvas.setFont('Times-Italic', 8)
            canvas.drawString(LM, PAGE_H - 0.5 * inch, header[:90])
            canvas.drawRightString(PAGE_W - RM, PAGE_H - 0.5 * inch, journal)
        canvas.restoreState()
    return fn


def main():
    print(f"Reading: {SRC_MD}")
    md = SRC_MD.read_text(encoding='utf-8')
    print(f"Parsing markdown ({len(md):,} chars)...")
    story = parse_markdown(md)
    print(f"Story elements: {len(story)}")
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=letter,
        leftMargin=LM, rightMargin=RM,
        topMargin=TM + 0.2 * inch, bottomMargin=BM + 0.15 * inch,
        title=HEADER, author='Sheikh Kamrul Islam', subject=JOURNAL,
    )
    pfn = make_page_fn(HEADER, JOURNAL)
    doc.build(story, onFirstPage=pfn, onLaterPages=pfn)
    size_kb = OUT_PDF.stat().st_size / 1024
    print(f"Wrote: {OUT_PDF.name}  ({size_kb:.0f} KB)")


if __name__ == '__main__':
    main()
