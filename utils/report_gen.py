from pathlib import Path
from typing import Dict, Any, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import red, green, black, HexColor
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    PageBreak,
)
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus.doctemplate import Indenter


# ---------- COLORS ----------
HEADER_COLOR = HexColor("#1F4FD8")
PASS_COLOR = HexColor("#2ECC71")
FAIL_COLOR = HexColor("#E74C3C")
FOOTER_COLOR = HexColor("#7F8C8D")


def create_report(
    result: Dict[str, Any],
    original_pdf_path: str,
    logo_path: str | None = None,
) -> bytes:
    output_path = Path(original_pdf_path).with_suffix(".comparison_report.pdf")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    elements: List[Any] = []

    # =========================================================
    # COVER
    # =========================================================
    if logo_path and Path(logo_path).exists():
        elements.append(RLImage(logo_path, width=4 * cm, height=2 * cm))
        elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>PDF Comparison Report</b>", styles["Title"]))
    elements.append(Spacer(1, 12))

    overall = result["overall"]
    elements.append(
        Paragraph(
            f"""
            <b>Overall Change:</b> {overall['overall_change']}<br/>
            <b>Overall Confidence:</b> {overall['confidence'] * 100:.1f}%
            """,
            styles["Normal"],
        )
    )

    elements.append(PageBreak())

    # =========================================================
    # TABLE OF CONTENTS (CLICKABLE)
    # =========================================================
    elements.append(Paragraph("<b>Table of Contents</b>", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    for page in result["pages"]:
        status_color = PASS_COLOR if page["status"] == "PASS" else FAIL_COLOR
        elements.append(
            Paragraph(
                f"""
                <link href="#page_{page['page']}">
                    Page {page['page']} —
                    <font color="{status_color.hexval}">
                        {page['status']}
                    </font>
                </link>
                """,
                styles["Normal"],
            )
        )

    elements.append(PageBreak())

    # =========================================================
    # PAGE-WISE DETAIL SECTIONS
    # =========================================================
    for page in result["pages"]:
        status_color = PASS_COLOR if page["status"] == "PASS" else FAIL_COLOR

        elements.append(
            Paragraph(
                f"""
                <a name="page_{page['page']}"/>
                <b>Page {page['page']} —
                <font color="{status_color.hexval}">
                {page['status']}
                </font></b>
                """,
                styles["Heading2"],
            )
        )

        elements.append(
            Paragraph(
                f"Confidence: {page['confidence'] * 100:.1f}%<br/>"
                f"Image Similarity: {page['image_similarity'] * 100:.1f}%",
                styles["Normal"],
            )
        )

        elements.append(Spacer(1, 12))

        # -----------------------------------------------------
        # IMAGE OVERLAYS (SIDE-BY-SIDE + DIFF)
        # -----------------------------------------------------
        if page.get("images"):
            img_table = []

            row = []
            for img_path in page["images"]:
                if Path(img_path).exists():
                    row.append(
                        RLImage(img_path, width=5 * cm, height=7 * cm)
                    )

            if row:
                img_table.append(row)

                table = Table(img_table, hAlign="LEFT")
                table.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.5, black),
                        ]
                    )
                )

                elements.append(table)
                elements.append(Spacer(1, 14))

        # -----------------------------------------------------
        # TEXT DIFFERENCES
        # -----------------------------------------------------
        if page["text_changes"]:
            table_data = [["Change", "Original", "Revised"]]

            for change in page["text_changes"]:
                color = green if change["type"] == "ADDED" else red

                table_data.append(
                    [
                        change["type"],
                        Paragraph(
                            f"<font color='{color.hexval}'>{change['original']}</font>",
                            styles["Normal"],
                        ),
                        Paragraph(
                            f"<font color='{color.hexval}'>{change['revised']}</font>",
                            styles["Normal"],
                        ),
                    ]
                )

            table = Table(
                table_data,
                colWidths=[3 * cm, 6 * cm, 6 * cm],
                repeatRows=1,
            )

            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), HEADER_COLOR),
                        ("GRID", (0, 0), (-1, -1), 0.5, black),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )

            elements.append(table)
        else:
            elements.append(
                Paragraph("No text changes detected.", styles["Italic"])
            )

        elements.append(PageBreak())

    # =========================================================
    # FOOTER
    # =========================================================
    def footer(canvas, doc):
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(FOOTER_COLOR)
        canvas.drawString(
            2 * cm,
            1.5 * cm,
            "Generated by PDF Comparator • Confidential",
        )

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    return output_path.read_bytes()
