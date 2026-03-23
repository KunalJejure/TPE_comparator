from __future__ import annotations

"""ReportLab-based detailed comparison report generator."""

import io
import logging
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import red, green, black, HexColor
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    PageBreak,
)

logger = logging.getLogger(__name__)

HEADER_COLOR = HexColor("#1F4FD8")
PASS_COLOR = HexColor("#2ECC71")
FAIL_COLOR = HexColor("#E74C3C")
FOOTER_COLOR = HexColor("#7F8C8D")


def create_report(
    result: Dict[str, Any],
    report_images: List[Image.Image],
    logo_path: str | None = None,
) -> bytes:
    """Build a comprehensive PDF comparison report.

    Returns:
        PDF file contents as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    elements: List[Any] = []

    # --- Cover ---
    if logo_path and Path(logo_path).exists():
        elements.append(RLImage(logo_path, width=4 * cm, height=2 * cm))
        elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>PDF Comparison Report</b>", styles["Title"]))
    elements.append(Spacer(1, 12))

    overall = result.get("overall", {})
    elements.append(
        Paragraph(
            f"<b>Overall Change:</b> {overall.get('overall_change', 'UNKNOWN')}<br/>"
            f"<b>Overall Confidence:</b> {overall.get('confidence', 0.0) * 100:.1f}%",
            styles["Normal"],
        )
    )
    elements.append(PageBreak())

    # --- Table of Contents ---
    elements.append(Paragraph("<b>Table of Contents</b>", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    for page in result.get("pages", []):
        status_color = PASS_COLOR if page.get("status") == "PASS" else FAIL_COLOR
        elements.append(
            Paragraph(
                f'<link href="#page_{page.get("page", 0)}">'
                f'Page {page.get("page", 0)} — '
                f'<font color="{status_color.hexval()}">{page.get("status", "PASS")}</font>'
                f"</link>",
                styles["Normal"],
            )
        )
    elements.append(PageBreak())

    # --- Page details & Images ---
    for i, page in enumerate(result.get("pages", [])):
        status_color = PASS_COLOR if page.get("status") == "PASS" else FAIL_COLOR

        elements.append(
            Paragraph(
                f'<a name="page_{page.get("page", 0)}"/>'
                f'<b>Page {page.get("page", 0)} — '
                f'<font color="{status_color.hexval()}">{page.get("status", "PASS")}</font></b>',
                styles["Heading2"],
            )
        )
        elements.append(
            Paragraph(
                f"Confidence: {page.get('confidence', 0.0) * 100:.1f}%<br/>"
                f"Image Similarity: {page.get('image_similarity', 1.0) * 100:.1f}%",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 12))

        ai_changes = page.get("ai_text_changes", [])
        if ai_changes:
            table_data = [["Change", "Original", "Revised"]]
            for change in ai_changes:
                color = green if change.get("type") == "ADDED" else red
                table_data.append([
                    change.get("type", ""),
                    Paragraph(
                        f"<font color='{color.hexval()}'>{change.get('original', '')}</font>",
                        styles["Normal"],
                    ),
                    Paragraph(
                        f"<font color='{color.hexval()}'>{change.get('revised', '')}</font>",
                        styles["Normal"],
                    ),
                ])
            table = Table(table_data, colWidths=[3 * cm, 6 * cm, 6 * cm], repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_COLOR),
                ("GRID", (0, 0), (-1, -1), 0.5, black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No text changes detected.", styles["Italic"]))

        elements.append(Spacer(1, 12))
        
        # Append image of this page if available
        if i < len(report_images) and report_images[i]:
            img_buf = io.BytesIO()
            report_images[i].save(img_buf, format="PNG")
            img_buf.seek(0)
            
            # constrain image to A4 width/height minus margins
            max_width = A4[0] - 72
            max_height = A4[1] - 150
            img_obj = RLImage(img_buf)
            img_obj.drawWidth = max_width
            img_obj.drawHeight = max_width * (report_images[i].height / report_images[i].width)
            if img_obj.drawHeight > max_height:
                img_obj.drawHeight = max_height
                img_obj.drawWidth = max_height * (report_images[i].width / report_images[i].height)
                
            elements.append(img_obj)

        elements.append(PageBreak())

    # --- Footer ---
    def footer(canvas, d):
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(FOOTER_COLOR)
        canvas.drawString(2 * cm, 1.5 * cm, "Generated by PDF Comparator")

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
