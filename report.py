import json
from typing import Dict, List

class ReportBuilder:
    """Build JSON and HTML report outputs."""

    def to_json(self, data: Dict) -> str:
        """Serialize report to JSON."""
        return json.dumps(data, indent=2)

    def comparison_table(self, plans: List[Dict]) -> str:
        """Generate HTML table comparing VPS plans."""
        html = "<table border='1' cellpadding='8'><tr>"
        html += "<th>Provider</th><th>Plan</th><th>vCPU</th><th>RAM (GB)</th><th>Price (USD)</th></tr>"

        for plan in plans:
            html += f"<tr>"
            html += f"<td>{plan['provider']}</td>"
            html += f"<td>{plan['plan']}</td>"
            html += f"<td>{plan['vcpu']}</td>"
            html += f"<td>{plan['ram_gb']}</td>"
            html += f"<td>${plan['price']:.2f}</td>"
            html += f"</tr>"

        html += "</table>"
        return html

    def to_html(self, data: Dict) -> str:
        """Generate complete HTML report with SVG charts."""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>VPS Simulation Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        h2 { color: #333; }
        .requirement { background: #f9f9f9; padding: 10px; margin: 10px 0; }
        .tier-GREEN { color: green; font-weight: bold; }
        .tier-YELLOW { color: orange; font-weight: bold; }
        .tier-RED { color: red; font-weight: bold; }
        .tier-CRITICAL { color: darkred; font-weight: bold; }
    </style>
</head>
<body>
"""
        html += f"<h1>Scenario: {data['scenario']}</h1>"

        html += "<h2>Requirements</h2>"
        html += "<div class='requirement'>"
        for k, v in data['requirements'].items():
            html += f"<p>{k}: {v}</p>"
        html += "</div>"

        html += "<h2>Resource Utilization</h2>"
        bottleneck_data = {k.replace('_gb', '').replace('_cores', '').upper(): v['utilization_pct']
                           for k, v in data['bottlenecks'].items()}
        html += self.svg_bar_chart(bottleneck_data, title="Utilization %")

        html += "<h2>Matched Plans</h2>"
        plans = data.get('matched_plans', [])
        html += self.comparison_table(plans)

        html += "</body></html>"
        return html

    def svg_bar_chart(self, data: Dict, title: str = "") -> str:
        """Generate inline SVG bar chart."""
        width, height = 600, 300
        bar_width = 60
        max_value = max(data.values()) if data else 100

        svg = f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        svg += f'<text x="10" y="20" font-size="16" font-weight="bold">{title}</text>'

        x_pos = 50
        for label, value in data.items():
            bar_height = (value / max_value) * 200
            y_pos = height - bar_height - 40

            svg += f'<rect x="{x_pos}" y="{y_pos}" width="{bar_width}" height="{bar_height}" fill="steelblue" />'
            svg += f'<text x="{x_pos}" y="{height - 20}" font-size="12">{label}</text>'
            svg += f'<text x="{x_pos}" y="{y_pos - 5}" font-size="12" text-anchor="middle">{value:.0f}%</text>'

            x_pos += bar_width + 20

        svg += '</svg>'
        return svg
