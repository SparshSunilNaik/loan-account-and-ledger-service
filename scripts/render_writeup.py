"""Render the concise write-up and verify that the PDF is exactly one page.

uv run --with reportlab==4.4.5 --with pypdf==6.1.1 python scripts/render_writeup.py
"""

import re
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = (ROOT / "docs/technical_writeup.md").read_text()
    styles = {
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=16, leading=19, spaceAfter=9
        ),
        "heading": ParagraphStyle(
            "heading",
            fontName="Helvetica-Bold",
            fontSize=10.2,
            leading=12.4,
            spaceBefore=6,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=9.3, leading=12.1, spaceAfter=4
        ),
    }
    flow = []
    for block in source.strip().split("\n\n"):
        if block.startswith("# "):
            style, text = styles["title"], block[2:]
        elif block.startswith("## "):
            style, text = styles["heading"], block[3:]
        else:
            style, text = styles["body"], re.sub(r"\s+", " ", block)
        flow.append(Paragraph(escape(text), style))
    flow.append(Spacer(1, 1))
    target = ROOT / "docs/technical_writeup.pdf"
    SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=34,
        bottomMargin=34,
        title="LedgerCore Technical Summary",
        author="LedgerCore",
        invariant=1,
    ).build(flow)
    assert len(PdfReader(target).pages) == 1, "Write-up exceeded one page"
    print(f"One-page PDF rendered: {target.name} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
