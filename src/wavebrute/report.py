"""Report generation for WaveBrute audits.

Supports PDF (ReportLab with neo-brutalist styling), Markdown and HTML (with inline CSS).
Uses Jinja2 for templating where appropriate. All outputs include ethics statements.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import jinja2

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except ImportError:
    # reportlab is unavailable on this build (e.g. the Android APK, where the
    # upstream python-for-android recipe currently can't fetch its source).
    # PDF export is disabled in that case, but Markdown/HTML reports and the
    # rest of the app keep working.
    REPORTLAB_AVAILABLE = False


class ReportBuilder:
    """Builds professional PDF, Markdown and HTML reports from audit results.

    Uses ReportLab for PDF with neo-brutalist styling (thick borders, bright colors).
    Jinja2 for HTML/Markdown templates.
    """

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results or []

    @classmethod
    def from_results(cls, results: list[dict[str, Any]]) -> ReportBuilder:
        """Create ReportBuilder from a list of audit result dicts."""
        return cls(results)

    def to_pdf(self, title: str = "WaveBrute Ethical Audit Report", output_path: str | None = None) -> str:
        """Generate a PDF report with brutalist design."""
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError(
                "PDF report generation is unavailable in this build (reportlab is not "
                "installed). Use format='md' or format='html' instead."
            )

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            output_path = f"wavebrute_report_{timestamp}.pdf"

        if not self.results:
            raise ValueError("No results to report on")

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            textColor=colors.HexColor("#ff004d"),
            spaceAfter=30,
            borderWidth=4,
            borderColor=colors.HexColor("#00ff9f"),
            borderPadding=10,
        )

        heading_style = ParagraphStyle(
            "Heading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=colors.HexColor("#00ff9f"),
            spaceAfter=12,
        )

        elements = []
        elements.append(Paragraph(f"<b>{title}</b>", title_style))
        elements.append(Spacer(1, 20))

        elements.append(Paragraph("Audit Summary", heading_style))
        elements.append(Spacer(1, 12))

        summary_data = [
            ["Metric", "Value"],
            ["Networks Scanned", str(len([r for r in self.results if r.get("type") == "scan"]))],
            ["Simulations Run", str(len(self.results))],
            ["Successful Cracks", str(sum(1 for r in self.results if r.get("success", False)))],
            ["Report Generated", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ]

        table = Table(summary_data, colWidths=[200, 200])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ff004d")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f0f0f0")),
                    ("GRID", (0, 0), (-1, -1), 2, colors.HexColor("#00ff9f")),
                    ("BOX", (0, 0), (-1, -1), 4, colors.black),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 30))

        elements.append(Paragraph("Detailed Findings", heading_style))
        elements.append(Spacer(1, 12))

        for i, result in enumerate(self.results[:10]):
            ssid = result.get("ssid", "Unknown")
            success = result.get("success", False)
            rtype = result.get("type", "unknown")
            detail = f"<b>{rtype.upper()} on {ssid}</b><br/>Success: {success}"
            if result.get("password"):
                detail += f"<br/>Password: {result['password']}"
            if result.get("recommendations"):
                detail += "<br/>Recommendations: " + "; ".join(result["recommendations"][:2])
            elements.append(Paragraph(detail, styles["Normal"]))
            elements.append(Spacer(1, 12))

        elements.append(Paragraph(
            "<br/><b>Ethics Statement:</b> This audit was conducted in simulation mode "
            "or with explicit consent. Always obtain written permission before testing "
            "live networks. WaveBrute is for educational and authorized pentesting only.",
            styles["Normal"],
        ))

        doc.build(elements)
        return os.path.abspath(output_path)

    def to_markdown(self, title: str = "WaveBrute Ethical Audit Report", output_path: str | None = None) -> str:
        """Generate a Markdown report (GitHub friendly)."""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            output_path = f"wavebrute_report_{timestamp}.md"

        lines = [
            f"# {title}",
            "",
            f"**Generated:** {datetime.now().isoformat()}",
            f"**Simulation Mode:** {any(r.get('simulation', True) for r in self.results)}",
            "",
            "## Summary",
            "",
            f"- Total results: {len(self.results)}",
            f"- Networks audited: {len({r.get('ssid') for r in self.results if r.get('ssid')})}",
            "",
            "## Findings",
            "",
        ]

        for result in self.results:
            ssid = result.get("ssid", "N/A")
            success = result.get("success", "N/A")
            rtype = result.get("type", "result").replace("_", " ").title()
            lines.append(f"### {rtype}: {ssid}")
            lines.append(f"- Success: **{success}**")
            if result.get("password"):
                lines.append(f"- Cracked Password: `{result['password']}`")
            if result.get("attempts"):
                lines.append(f"- Attempts: {result['attempts']}")
            if result.get("recommendations"):
                lines.append("**Recommendations:**")
                for rec in result["recommendations"]:
                    lines.append(f"  - {rec}")
            lines.append("")

        lines.append("## Ethics & Responsible Use")
        lines.append(
            "This report was generated by WaveBrute. All activities were either simulated "
            "or performed with explicit consent. Misuse is prohibited."
        )

        content = "\n".join(lines)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return os.path.abspath(output_path)

    def to_html(self, title: str = "WaveBrute Ethical Audit Report", output_path: str | None = None) -> str:
        """Generate HTML report with neo-brutalist CSS styling."""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            output_path = f"wavebrute_report_{timestamp}.html"

        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
        body {
            font-family: 'Press Start 2P', system-ui;
            background: #111111;
            color: #00ff9f;
            padding: 40px;
            line-height: 1.6;
        }
        h1, h2 {
            color: #ff004d;
            border-bottom: 6px solid #ffff00;
            padding-bottom: 10px;
        }
        .brutalist {
            border: 6px solid #ffff00;
            background: #222222;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 8px 8px 0 #ff004d;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            border: 4px solid #00ff9f;
        }
        th, td {
            padding: 12px;
            border: 2px solid #ffff00;
            text-align: left;
        }
        th {
            background: #ff004d;
            color: white;
        }
        .success { color: #00ff9f; font-weight: bold; }
        .header {
            background: #ffff00;
            color: #111;
            padding: 20px;
            border: 6px solid #ff004d;
            text-align: center;
            margin-bottom: 40px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>WAVEBRUTE</h1>
        <p>ETHICAL AUDIT REPORT</p>
    </div>
    <h1>{{ title }}</h1>
    <p><strong>Generated on:</strong> {{ timestamp }}</p>

    <div class="brutalist">
        <h2>Audit Summary</h2>
        <p>Total simulations: {{ total_results }}</p>
        <p>Success rate: {{ success_rate }}%</p>
    </div>

    <h2>Findings</h2>
    {{ findings_html }}

    <div class="brutalist">
        <h2>Responsible Disclosure</h2>
        <p>This report is for educational purposes. Always obtain explicit written consent before performing wireless audits.</p>
        <p>WaveBrute - Scan. Simulate. Secure.</p>
    </div>
</body>
</html>
        """

        total = len(self.results)
        successes = sum(1 for r in self.results if r.get("success", False))
        success_rate = round((successes / total * 100), 1) if total > 0 else 0.0

        findings = ""
        for result in self.results:
            ssid = result.get("ssid", "Unknown")
            success_cls = "class='success'" if result.get("success") else ""
            findings += f"<div class='brutalist'><h3>{result.get('type', 'Audit')} on <em>{ssid}</em></h3>"
            findings += f"<p {success_cls}>Success: {result.get('success', 'N/A')}</p>"
            if result.get("password"):
                findings += f"<p>Password: <code>{result['password']}</code></p>"
            if result.get("notes"):
                findings += f"<p>{result['notes']}</p>"
            findings += "</div>"

        html = (
            template.replace("{{ title }}", title)
            .replace("{{ timestamp }}", datetime.now().isoformat())
            .replace("{{ total_results }}", str(total))
            .replace("{{ success_rate }}", str(success_rate))
            .replace("{{ findings_html }}", findings)
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        return os.path.abspath(output_path)


if __name__ == "__main__":
    builder = ReportBuilder([{"type": "test", "ssid": "TestNet", "success": True, "password": "testpass"}])
    print(builder.to_markdown("Test Report"))
    print("Report generation test completed.")
