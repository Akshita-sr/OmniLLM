"""Build the OmniLLM book PDF from its 16 source markdown files.

This is the second-edition builder (May 2026), rewritten to:
  1. Stitch together the new 16-file source tree (`book2/`) rather than the
     single legacy `book/OmniLLM_Book.md` master.
  2. Produce an assembled master `OmniLLM_Book.md` alongside the PDF, so that
     downstream tooling (PDF readers, GitHub viewers, search) can still treat
     the book as a single document.
  3. Preserve all the font-and-glyph fixes from the first-edition builder:
     DejaVu Sans / DejaVu Sans Mono registration with ReportLab, emoji ->
     short-text substitution, box-drawing-character -> ASCII substitution
     inside <pre> blocks (because xhtml2pdf ignores @font-face inside <pre>).

Pipeline:
    [16 markdown files in book2/]
        |
        v concatenate (in defined order) -> book2/OmniLLM_Book.md
        |
        v markdown library -> HTML body
        |
        v inject CSS, footer, page-break stylesheet
        |
        v xhtml2pdf  -> book2/OmniLLM_Book.pdf
        |
        +-> also writes book2/OmniLLM_Book.html for browser preview

Usage:
    python book2/build_pdf.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import markdown as md
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import pisa


BOOK_DIR = Path(__file__).parent
MASTER_MD = BOOK_DIR / "OmniLLM_Book.md"
HTML_OUT = BOOK_DIR / "OmniLLM_Book.html"
PDF_OUT = BOOK_DIR / "OmniLLM_Book.pdf"


# ─── Source-file order ────────────────────────────────────────────────────────
# The 16 source files in the order they appear in the book.  Adding or removing
# a part is one edit here; nothing else needs to change.

SOURCE_FILES: tuple[str, ...] = (
    "00_front_matter.md",
    "01_toc.md",
    "02_part1_motivation.md",
    "03_part2_architecture.md",
    "04_part3a_master_table.md",
    "05_part3b_core_modules.md",
    "06_part3c_hri_rag.md",
    "07_part3d_robotics_server_utils_bridge.md",
    "08_part4_setup_and_day_zero.md",
    "09_part5_experiments.md",
    "10_part6_future.md",
    "11_appendix_a_python_primer.md",
    "12_appendix_b_glossary.md",
    "13_appendix_c_commands_d_troubleshooting.md",
    "14_appendix_e_flow_f_file_index.md",
    "15_appendix_g_h_references.md",
)


# ─── Font registration ────────────────────────────────────────────────────────
# DejaVu Sans + DejaVu Sans Mono ship with matplotlib.  They have full coverage
# of the box-drawing characters (U+2500..U+257F), arrows (U+2190..U+21FF) and
# common geometric shapes that the original Helvetica fallback rendered as
# tofu squares.

_MPL_FONTS = (
    Path("C:/Users/akshi/anaconda3/Lib/site-packages/matplotlib/mpl-data/fonts/ttf"),
    # Add additional candidate locations here for portability:
    Path("/usr/share/fonts/truetype/dejavu"),                                # Debian/Ubuntu
    Path("/Library/Fonts"),                                                   # macOS
    Path("C:/Windows/Fonts"),                                                # Windows system
)


def _resolve_font(name: str) -> Path | None:
    for base in _MPL_FONTS:
        p = base / name
        if p.exists():
            return p
    return None


def register_fonts() -> None:
    """Register DejaVu Sans (body) and DejaVu Sans Mono (code) with ReportLab.

    xhtml2pdf will pick these up by font-family name from CSS.
    """
    fonts = {
        "DejaVuSans": _resolve_font("DejaVuSans.ttf"),
        "DejaVuSans-Bold": _resolve_font("DejaVuSans-Bold.ttf"),
        "DejaVuSans-Oblique": _resolve_font("DejaVuSans-Oblique.ttf"),
        "DejaVuSans-BoldOblique": _resolve_font("DejaVuSans-BoldOblique.ttf"),
        "DejaVuSansMono": _resolve_font("DejaVuSansMono.ttf"),
        "DejaVuSansMono-Bold": _resolve_font("DejaVuSansMono-Bold.ttf"),
        "DejaVuSansMono-Oblique": _resolve_font("DejaVuSansMono-Oblique.ttf"),
        "DejaVuSansMono-BoldOblique": _resolve_font("DejaVuSansMono-BoldOblique.ttf"),
    }

    missing = [n for n, p in fonts.items() if p is None]
    if missing:
        print(
            f"[build_pdf] WARNING: missing fonts {missing} — diagrams may render as squares.",
            flush=True,
        )

    for name, path in fonts.items():
        if path is None:
            continue
        pdfmetrics.registerFont(TTFont(name, str(path)))

    pdfmetrics.registerFontFamily(
        "DejaVuSans",
        normal="DejaVuSans",
        bold="DejaVuSans-Bold",
        italic="DejaVuSans-Oblique",
        boldItalic="DejaVuSans-BoldOblique",
    )
    pdfmetrics.registerFontFamily(
        "DejaVuSansMono",
        normal="DejaVuSansMono",
        bold="DejaVuSansMono-Bold",
        italic="DejaVuSansMono-Oblique",
        boldItalic="DejaVuSansMono-BoldOblique",
    )


# ─── CSS ──────────────────────────────────────────────────────────────────────

CSS = """
@page {
  size: A4;
  margin: 2cm 1.8cm 2cm 1.8cm;
  @frame footer {
    -pdf-frame-content: footerContent;
    bottom: 1cm; margin-left: 1.8cm; margin-right: 1.8cm; height: 1cm;
  }
}
body {
  font-family: "DejaVuSans", "Helvetica", "Arial", sans-serif;
  font-size: 10.5pt;
  line-height: 1.4;
  color: #222;
}
h1 {
  font-size: 22pt; color: #0d47a1;
  border-bottom: 2px solid #0d47a1;
  padding-bottom: 4pt; margin-top: 18pt;
  -pdf-keep-with-next: true;
}
h2 {
  font-size: 16pt; color: #1565c0; margin-top: 14pt;
  border-bottom: 1px solid #bbdefb; padding-bottom: 2pt;
  -pdf-keep-with-next: true;
}
h3 {
  font-size: 13pt; color: #1976d2; margin-top: 10pt;
  -pdf-keep-with-next: true;
}
h4 {
  font-size: 11.5pt; color: #1e88e5; margin-top: 8pt;
  -pdf-keep-with-next: true;
}
p { margin: 4pt 0; text-align: justify; }
strong { color: #0d47a1; }
em { color: #424242; }
code {
  font-family: "DejaVuSansMono", "Courier New", monospace;
  font-size: 9pt;
  background: #f3f3f3;
  padding: 0 3px;
}
pre {
  background: #fafafa;
  border: 1px solid #d0d0d0;
  border-left: 3px solid #1976d2;
  padding: 6pt 8pt;
  font-family: "DejaVuSansMono", "Courier New", monospace;
  font-size: 7.8pt;
  line-height: 1.25;
  white-space: pre;
  -pdf-keep-with-next: false;
}
pre code {
  background: transparent; padding: 0;
  font-family: "DejaVuSansMono", "Courier New", monospace;
  font-size: 7.8pt;
}
table { border-collapse: collapse; margin: 8pt 0; width: 100%; }
th {
  background: #e3f2fd; padding: 4pt 6pt;
  border: 0.5pt solid #90caf9;
  text-align: left; font-weight: bold; font-size: 10pt;
}
td {
  padding: 3pt 6pt; border: 0.5pt solid #cfd8dc;
  vertical-align: top; font-size: 10pt;
}
blockquote {
  border-left: 3pt solid #1976d2; background: #f5f7fa;
  padding: 5pt 10pt; margin: 8pt 0;
  color: #37474f; font-style: italic;
}
ul, ol { margin: 4pt 0 4pt 18pt; }
li { margin: 2pt 0; }
hr { border: 0; border-top: 0.5pt solid #cfd8dc; margin: 14pt 0; }
a { color: #1565c0; text-decoration: none; }
"""


# ─── Pre-processing ───────────────────────────────────────────────────────────
# Emoji that DejaVu cannot render.  Replaced with short, font-safe equivalents
# so the text reads correctly instead of showing as a tofu square.

_EMOJI_REPLACE = {
    "\U0001F464": "[Human]",      # 👤 BUST IN SILHOUETTE
    "\U0001F916": "[Robot]",      # 🤖 ROBOT FACE
    "\U0001F947": "1st",          # 🥇 GOLD MEDAL
    "\U0001F948": "2nd",          # 🥈 SILVER MEDAL
    "\U0001F949": "3rd",          # 🥉 BRONZE MEDAL
    "\U0001F393": "(Academic)",   # 🎓 GRADUATION CAP
    "\U0001F4A1": "(Tip)",        # 💡 LIGHT BULB
    "\U0001F4D6": "(Book)",       # 📖 OPEN BOOK
    "⚡": "*",                # ⚡ HIGH VOLTAGE
    "⚠": "(!)",              # ⚠ WARNING SIGN
    "️": "",                 # Variation Selector-16 (invisible joiner)
    "̃": "",                 # Combining tilde
    # The author's check-box convention in the Day Zero chapter:
    "✓": "[x]",              # ✓ CHECK MARK
    "✅": "[OK]",             # ✅ WHITE HEAVY CHECK
    "❌": "[X]",              # ❌ CROSS MARK
}

# Box-drawing and block-element characters.  xhtml2pdf ignores @font-face font
# substitution inside <pre> blocks, so DejaVu's coverage of these code points
# does not help — they still render as tofu squares.  ALL of these characters
# appear ONLY inside fenced code blocks (verified by grep), so substituting
# globally is safe.

_BOX_REPLACE = {
    "─": "-",   # ─ LIGHT HORIZONTAL
    "━": "=",   # ━ HEAVY HORIZONTAL
    "│": "|",   # │ LIGHT VERTICAL
    "┌": "+",   # ┌ LIGHT DOWN AND RIGHT
    "┐": "+",   # ┐ LIGHT DOWN AND LEFT
    "└": "+",   # └ LIGHT UP AND RIGHT
    "┘": "+",   # ┘ LIGHT UP AND LEFT
    "├": "+",   # ├ LIGHT VERTICAL AND RIGHT
    "┤": "+",   # ┤ LIGHT VERTICAL AND LEFT
    "┬": "+",   # ┬ LIGHT DOWN AND HORIZONTAL
    "┴": "+",   # ┴ LIGHT UP AND HORIZONTAL
    "┼": "+",   # ┼ LIGHT VERTICAL AND HORIZONTAL
    "╱": "/",   # ╱ DIAGONAL UPPER RIGHT TO LOWER LEFT
    "╲": "\\",  # ╲ DIAGONAL UPPER LEFT TO LOWER RIGHT
    "╔": "+", "╗": "+", "╚": "+", "╝": "+",   # heavy double corners
    "╠": "+", "╣": "+", "╦": "+", "╩": "+", "╬": "+",
    "═": "=",   # heavy double horizontal
    "║": "|",   # heavy double vertical
    "█": "#",   # █ FULL BLOCK
    "▏": "|",   # ▏ LEFT ONE EIGHTH BLOCK
    "▼": "v",   # ▼ BLACK DOWN-POINTING TRIANGLE
    "▲": "^",   # ▲ BLACK UP-POINTING TRIANGLE
    "▶": ">",   # ▶ BLACK RIGHT-POINTING TRIANGLE
    "◀": "<",   # ◀ BLACK LEFT-POINTING TRIANGLE
    "↑": "^",   # ↑ UPWARDS ARROW
    "↓": "v",   # ↓ DOWNWARDS ARROW
    "←": "<-",  # ← LEFTWARDS ARROW
    "→": "->",  # → RIGHTWARDS ARROW
}


# ─── Assembly ─────────────────────────────────────────────────────────────────

def assemble_master() -> str:
    """Read the 16 source files in order and concatenate them.

    A `\\newpage` separator is inserted between files if the source file does
    not already end with one.  YAML frontmatter from file 00 is preserved at
    the top of the master so pandoc-style metadata still works for tools that
    read it.
    """
    parts: list[str] = []
    for fname in SOURCE_FILES:
        path = BOOK_DIR / fname
        if not path.exists():
            print(f"[build_pdf] WARNING: source file missing: {path}", flush=True)
            continue
        text = path.read_text(encoding="utf-8")
        # If the file doesn't end with a page break and isn't the last file,
        # append one so the next chapter starts on a new page.
        text = text.rstrip()
        if fname != SOURCE_FILES[-1] and "\\newpage" not in text[-200:]:
            text += "\n\n\\newpage\n"
        parts.append(text + "\n\n")
    return "".join(parts)


def clean_markdown(text: str) -> str:
    """Strip pandoc YAML frontmatter and LaTeX commands; replace problem
    emoji and box-drawing characters that xhtml2pdf renders as squares."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:].lstrip()
    text = text.replace("\\newpage", "\n\n<div class='pageBreak'></div>\n\n")
    for needle, repl in _EMOJI_REPLACE.items():
        text = text.replace(needle, repl)
    for needle, repl in _BOX_REPLACE.items():
        text = text.replace(needle, repl)
    return text


def md_to_html(text: str) -> str:
    body = md.markdown(
        text,
        extensions=[
            "tables",
            "fenced_code",
            "codehilite",
            "toc",
            "sane_lists",
        ],
        extension_configs={
            "codehilite": {"noclasses": True, "pygments_style": "friendly"},
        },
    )
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>The Embodied LLM Arena</title>"
        f"<style>{CSS}\n"
        ".pageBreak { page-break-before: always; }"
        "</style></head><body>"
        + body
        + "<div id='footerContent' style='text-align:center;font-size:8pt;color:#888;'>"
          "The Embodied LLM Arena &mdash; OmniLLM &nbsp;|&nbsp; "
          "<pdf:pagenumber/></div>"
        "</body></html>"
    )
    return html


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("[build_pdf] Registering DejaVu fonts with ReportLab", flush=True)
    register_fonts()

    print(f"[build_pdf] Assembling master from {len(SOURCE_FILES)} source files",
          flush=True)
    raw = assemble_master()
    MASTER_MD.write_text(raw, encoding="utf-8")
    print(f"[build_pdf] Master Markdown saved to {MASTER_MD} ({len(raw)} chars)",
          flush=True)

    cleaned = clean_markdown(raw)

    print(f"[build_pdf] Converting Markdown -> HTML ({len(cleaned)} chars)",
          flush=True)
    t0 = time.time()
    html = md_to_html(cleaned)
    HTML_OUT.write_text(html, encoding="utf-8")
    print(f"[build_pdf] HTML done in {time.time()-t0:.1f}s ({len(html)} chars)",
          flush=True)
    print(f"[build_pdf] HTML saved to {HTML_OUT}", flush=True)

    print("[build_pdf] Converting HTML -> PDF (xhtml2pdf)...", flush=True)
    t0 = time.time()
    with open(PDF_OUT, "wb") as fh:
        result = pisa.CreatePDF(html, dest=fh, encoding="utf-8")
    print(f"[build_pdf] PDF done in {time.time()-t0:.1f}s", flush=True)

    if result.err:
        print(f"[build_pdf] !! {result.err} errors during conversion", flush=True)
        sys.exit(1)

    size = PDF_OUT.stat().st_size
    print(f"[build_pdf] {PDF_OUT.name} = {size/1024:.1f} KB", flush=True)


if __name__ == "__main__":
    main()
