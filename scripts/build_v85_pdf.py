"""
Build the Medical Image Analysis (Elsevier) submission PDF from
Manuscript_for_MedIA.md.

Renders the markdown to a Times-New-Roman, single-column letter-size PDF with
auto-embedded figures wherever a caption block contains a "Source image:"
pointer. Greek letters and math (π, σ, τ, Δ, π*, π_stable, $...$, $$...$$)
are rendered natively via Windows Times New Roman TTF (Unicode-capable) plus
LaTeX-to-Unicode plus <sub>/<sup> tag conversion.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MS_DIR = ROOT / "manuscript"
SRC_MD = MS_DIR / "Manuscript_for_MedIA.md"
OUT_PDF = MS_DIR / "Manuscript_for_MedIA.pdf"
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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

# ---------------------------------------------------------------------------
# Register Unicode-capable Times New Roman so Greek and math symbols render.
# ---------------------------------------------------------------------------
WIN_FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("TNR", str(WIN_FONTS / "times.ttf")))
pdfmetrics.registerFont(TTFont("TNR-Bold", str(WIN_FONTS / "timesbd.ttf")))
pdfmetrics.registerFont(TTFont("TNR-Italic", str(WIN_FONTS / "timesi.ttf")))
pdfmetrics.registerFont(TTFont("TNR-BoldItalic", str(WIN_FONTS / "timesbi.ttf")))
pdfmetrics.registerFontFamily(
    "TNR", normal="TNR", bold="TNR-Bold",
    italic="TNR-Italic", boldItalic="TNR-BoldItalic",
)

PAGE_W, PAGE_H = letter
LM = RM = 0.9 * inch
TM = BM = 0.9 * inch
TW = PAGE_W - LM - RM

styles = getSampleStyleSheet()


def mkstyle(name, parent_name="Normal", **kw):
    p = styles[parent_name] if parent_name in styles else styles["Normal"]
    return ParagraphStyle(name, parent=p, **kw)


TITLE = mkstyle("ms_title", fontName="TNR-Bold", fontSize=15, leading=20,
                alignment=TA_CENTER, spaceBefore=0, spaceAfter=10)
AUTH = mkstyle("ms_auth", fontName="TNR", fontSize=11, leading=14,
               alignment=TA_CENTER, spaceAfter=4)
H1 = mkstyle("ms_h1", fontName="TNR-Bold", fontSize=12.5, leading=16,
             spaceBefore=12, spaceAfter=4)
H2 = mkstyle("ms_h2", fontName="TNR-Bold", fontSize=11, leading=14,
             spaceBefore=8, spaceAfter=3)
H3 = mkstyle("ms_h3", fontName="TNR-BoldItalic", fontSize=10.5, leading=13.5,
             spaceBefore=6, spaceAfter=3)
BODY = mkstyle("ms_body", fontName="TNR", fontSize=10.2, leading=13.8,
               alignment=TA_JUSTIFY, spaceAfter=4)
ABST = mkstyle("ms_abst", fontName="TNR", fontSize=10, leading=13.5,
               leftIndent=14, rightIndent=14, alignment=TA_JUSTIFY,
               spaceBefore=4, spaceAfter=8)
EQN = mkstyle("ms_eqn", fontName="TNR-Italic", fontSize=10.5, leading=14,
              alignment=TA_CENTER, spaceBefore=4, spaceAfter=4)
CAP = mkstyle("ms_cap", fontName="TNR", fontSize=8.8, leading=11.5,
              leftIndent=8, rightIndent=8, spaceAfter=6)
TBCELL = mkstyle("ms_tc", fontName="TNR", fontSize=8.2, leading=10.5,
                 spaceAfter=0)
TBHEAD = mkstyle("ms_th", fontName="TNR-Bold", fontSize=8.2, leading=10.5,
                 spaceAfter=0)
BULL = mkstyle("ms_bull", fontName="TNR", fontSize=10.2, leading=13.5,
               leftIndent=14, firstLineIndent=-10, spaceAfter=3)


# ---------------------------------------------------------------------------
# LaTeX-to-Unicode + sub/sup conversion for math fragments.
# ---------------------------------------------------------------------------
LATEX_GREEK = {
    r'\\alpha': 'α', r'\\beta': 'β', r'\\gamma': 'γ', r'\\delta': 'δ',
    r'\\epsilon': 'ε', r'\\varepsilon': 'ε', r'\\zeta': 'ζ', r'\\eta': 'η',
    r'\\theta': 'θ', r'\\vartheta': 'ϑ', r'\\iota': 'ι', r'\\kappa': 'κ',
    r'\\lambda': 'λ', r'\\mu': 'μ', r'\\nu': 'ν', r'\\xi': 'ξ',
    r'\\pi': 'π', r'\\varpi': 'ϖ', r'\\rho': 'ρ', r'\\varrho': 'ϱ',
    r'\\sigma': 'σ', r'\\varsigma': 'ς', r'\\tau': 'τ', r'\\upsilon': 'υ',
    r'\\phi': 'ϕ', r'\\varphi': 'φ', r'\\chi': 'χ', r'\\psi': 'ψ',
    r'\\omega': 'ω',
    r'\\Gamma': 'Γ', r'\\Delta': 'Δ', r'\\Theta': 'Θ', r'\\Lambda': 'Λ',
    r'\\Xi': 'Ξ', r'\\Pi': 'Π', r'\\Sigma': 'Σ', r'\\Upsilon': 'Υ',
    r'\\Phi': 'Φ', r'\\Psi': 'Ψ', r'\\Omega': 'Ω',
}
LATEX_OPS = {
    r'\\times': '×', r'\\cdot': '·', r'\\pm': '±', r'\\mp': '∓',
    r'\\leq': '≤', r'\\le': '≤', r'\\geq': '≥', r'\\ge': '≥',
    r'\\neq': '≠', r'\\ne': '≠', r'\\approx': '≈', r'\\sim': '∼',
    r'\\equiv': '≡', r'\\to': '→', r'\\rightarrow': '→',
    r'\\leftarrow': '←', r'\\Rightarrow': '⇒', r'\\Leftarrow': '⇐',
    r'\\infty': '∞', r'\\partial': '∂', r'\\nabla': '∇',
    r'\\sum': 'Σ', r'\\prod': 'Π', r'\\int': '∫',
    r'\\in': '∈', r'\\notin': '∉', r'\\subset': '⊂', r'\\supset': '⊃',
    r'\\cup': '∪', r'\\cap': '∩', r'\\emptyset': '∅', r'\\forall': '∀',
    r'\\exists': '∃', r'\\propto': '∝',
    r'\\ldots': '…', r'\\cdots': '⋯', r'\\dots': '…',
    r'\\hat': '', r'\\bar': '', r'\\vec': '',
    r'\\mathbf': '', r'\\mathbb': '', r'\\mathcal': '', r'\\mathrm': '',
    r'\\textbf': '', r'\\textit': '', r'\\text': '',
}


def _unfold_braces(s):
    """Convert LaTeX _{...} and ^{...} into XML <sub>...</sub> / <sup>...</sup>;
    convert _x and ^x (single token) similarly. Does NOT process inside <font>."""
    # Subscript {...}
    s = re.sub(r'_\{([^{}]*)\}', r'<sub>\1</sub>', s)
    s = re.sub(r'\^\{([^{}]*)\}', r'<sup>\1</sup>', s)
    # Subscript single token (alphanumeric or *)
    s = re.sub(r'_([A-Za-z0-9*])', r'<sub>\1</sub>', s)
    s = re.sub(r'\^([A-Za-z0-9*])', r'<sup>\1</sup>', s)
    return s


def _latex_to_unicode(s):
    """Convert LaTeX commands inside a math fragment to Unicode + XML."""
    # Strip \frac{a}{b} → (a)/(b)
    s = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r'(\1)/(\2)', s)
    # Strip \sqrt{x} → √(x)
    s = re.sub(r'\\sqrt\{([^{}]*)\}', r'√(\1)', s)
    # Greek + ops table
    for pat, rep in {**LATEX_GREEK, **LATEX_OPS}.items():
        s = re.sub(pat + r'(?![A-Za-z])', rep, s)
    # \text{...} and similar formatting wrappers — already mapped to '' above,
    # but the {...} braces remain; strip them
    s = re.sub(r'\{([^{}]*)\}', r'\1', s)
    # Underscore/caret subscripts/superscripts
    s = _unfold_braces(s)
    # Stray backslashes left → drop the backslash
    s = re.sub(r'\\([A-Za-z]+)', r'\1', s)
    return s.strip()


def _math_to_xml(s, display=False):
    """Convert a math fragment to italic Unicode-with-XML output."""
    s = _latex_to_unicode(s)
    return f'<i>{s}</i>'


def render_math(text):
    """Replace $$...$$ and $...$ math fragments in text with rendered XML."""
    # Display math: $$ ... $$ — replace inline (the document treats display
    # math as its own paragraph anyway, surfaced via parse_markdown).
    def _disp(m):
        return _math_to_xml(m.group(1), display=True)
    text = re.sub(r'\$\$([^$]+)\$\$', _disp, text, flags=re.DOTALL)
    # Inline math: $ ... $
    def _inl(m):
        return _math_to_xml(m.group(1), display=False)
    text = re.sub(r'\$([^$\n]+)\$', _inl, text)
    return text


# ---------------------------------------------------------------------------
# Inline conversion: math, bold, italic, code, dashes, and tokenised Greek
# subscripts (e.g. π_stable → π<sub>stable</sub>).
# ---------------------------------------------------------------------------
GREEK_LETTERS = 'αβγδεζηθικλμνξοπρστυϕφχψωΓΔΘΛΞΠΣΥΦΨΩ'


def inline(text):
    # 1. Math first (so math content doesn't get mangled by markdown rules)
    text = render_math(text)
    # 2. Footnote refs
    text = re.sub(r'\[\^(\w+)\]', r'<super>\1</super>', text)
    # 3. Bold + italic
    text = re.sub(r'\*\*\*([^*]+)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<i>\1</i>', text)
    # 4. Inline code
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" size="9">\1</font>', text)
    # 5. Greek-letter subscripts in prose: π_stable → π<sub>stable</sub>
    text = re.sub(
        r'([' + GREEK_LETTERS + r'])_([A-Za-z]+)',
        r'\1<sub>\2</sub>', text,
    )
    # 6. Greek-letter superscripts in prose: π* and π^* → π<sup>*</sup>
    text = re.sub(
        r'([' + GREEK_LETTERS + r'])\^?\*',
        r'\1<sup>*</sup>', text,
    )
    # 7. Escape stray ampersands not already entities
    text = re.sub(r'&(?!(amp|lt|gt|quot|apos|[a-zA-Z]+;|#\d+;));?',
                  lambda m: m.group(0) if m.group(0).endswith(';') else '&amp;',
                  text)
    # 8. em/en dashes
    text = text.replace('---', '—').replace(' -- ', ' – ')
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

        # Standalone display-math line (whole para is $$...$$)
        m_eqn = re.match(r'^\$\$([^$]+)\$\$\s*$', text, flags=re.DOTALL)
        if m_eqn:
            xml = _math_to_xml(m_eqn.group(1), display=True)
            p = safe_para(xml, EQN)
            if p:
                story.append(Spacer(1, 4))
                story.append(p)
                story.append(Spacer(1, 4))
            para_buf.clear()
            return

        # Figure caption block (auto-embed image)
        m_fig = re.match(r'^\*\*((?:Extended Data )?Figure \d+(?:[a-z])?)\.\*\*', text)
        if m_fig:
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
            in_abstract = htext.lower().startswith('abstract') or htext.lower().startswith('structured abstract')
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
        canvas.setFont('TNR', 9)
        pn = canvas.getPageNumber()
        canvas.drawCentredString(PAGE_W / 2, 0.45 * inch, str(pn))
        if pn > 1:
            canvas.setFont('TNR-Italic', 8)
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
