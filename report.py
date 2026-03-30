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
