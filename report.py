"""JSON + HTML report generation with inline SVG charts."""
import json
from collections import OrderedDict
from typing import Dict, List


class ReportBuilder:
    def to_json(self, data: Dict) -> str:
        ordered = OrderedDict()
        ordered["urgent_flags"] = data.get("urgent_flags", [])
        for key in data:
            if key != "urgent_flags":
                ordered[key] = data[key]
        return json.dumps(ordered, indent=2)

    def to_html(self, data: Dict) -> str:
        html = self._html_head()

        # 1. Executive Summary
        html += "<h2>Executive Summary</h2>\n"
        flags = data.get("urgent_flags", [])
        if flags:
            html += "<div class='urgent'>"
            for f in flags:
                html += f"<p class='flag'>URGENT: {f}</p>"
            html += "</div>\n"
        rec = data.get("top_recommendation", {})
        if rec:
            html += f"<p><strong>Top Recommendation:</strong> {rec.get('provider', '')} {rec.get('plan', '')} - {rec.get('reason', '')}</p>\n"

        # 2. Live Baseline
        html += "<h2>Live Baseline</h2>\n"
        baseline = data.get("baseline", {})
        if baseline:
            html += f"<p>Baseline age: {data.get('baseline_age_minutes', '?')} minutes"
            if data.get("baseline_stale"):
                html += " <span class='stale'>(STALE)</span>"
            html += "</p>\n"
            html += self._baseline_section(baseline)

        # 3. Scenario Projections
        html += "<h2>Scenario Projections</h2>\n"
        for name, scenario in data.get("scenarios", {}).items():
            html += f"<h3>{name}</h3>\n"
            reqs = scenario.get("requirements", {})
            html += f"<p>RAM: {reqs.get('ram_gb', '?')} GB | CPU: {reqs.get('cpu_cores', '?')} cores | Disk: {reqs.get('disk_gb', '?')} GB</p>\n"
            bn = scenario.get("bottlenecks", {})
            if bn:
                html += f"<p class='verdict'>{bn.get('verdict', '')}</p>\n"

        # 4. Provider Profiles
        html += "<h2>Provider Profiles</h2>\n"
        for provider, plans in data.get("provider_profiles", {}).items():
            for plan_name, info in plans.items():
                html += f"<h3>{provider} - {plan_name}</h3>\n"
                html += f"<p>{info.get('overview', '')}</p>\n"
                if info.get("pros"):
                    html += "<p><strong>Pros:</strong> " + ", ".join(info["pros"]) + "</p>\n"
                if info.get("cons"):
                    html += "<p><strong>Cons:</strong> " + ", ".join(info["cons"]) + "</p>\n"
                if info.get("risks"):
                    html += "<p><strong>Risks:</strong> " + ", ".join(info["risks"]) + "</p>\n"
                if info.get("opportunities"):
                    html += "<p><strong>Opportunities:</strong> " + ", ".join(info["opportunities"]) + "</p>\n"

        # 5. Comparison Table
        html += "<h2>Comparison Table</h2>\n"
        html += self.comparison_table(data.get("matched_plans", []))

        # 6. Break-even Analysis
        html += "<h2>Break-even Analysis</h2>\n"
        be = data.get("break_even", {})
        csm = be.get("cumulative_savings_by_month", {})
        if csm:
            html += self.svg_break_even(csm)
            if be.get("break_even_months"):
                html += f"<p>Break-even at month {be['break_even_months']:.1f}</p>\n"

        # 7. Headroom Decay
        html += "<h2>Headroom Decay</h2>\n"
        decay = data.get("headroom_decay", {})
        for resource, info in decay.items():
            if isinstance(info, dict) and not info.get("skipped"):
                total = baseline.get(resource, {}).get("total_gb", 100) if baseline else 100
                html += f"<h3>{resource.upper()}</h3>\n"
                html += self.svg_decay_trend(info, resource.upper(), total_gb=total)

        # 8. Bottleneck Summary
        html += "<h2>Bottleneck Summary</h2>\n"
        for name, scenario in data.get("scenarios", {}).items():
            bn = scenario.get("bottlenecks", {})
            html += f"<p><strong>{name}:</strong> {bn.get('verdict', 'N/A')}</p>\n"

        # 9. Migration Plan
        migration = data.get("migration")
        if migration:
            html += "<h2>Migration Plan</h2>\n"
            html += f"<p>Target: {migration.get('target', '')}</p>\n"
            html += f"<p>Estimated downtime: {migration.get('estimated_downtime_minutes', '?')} min</p>\n"
            html += "<ol>\n"
            for step in migration.get("steps", []):
                html += f"  <li>{step}</li>\n"
            html += "</ol>\n"
            html += f"<p><strong>Rollback:</strong> {migration.get('rollback', '')}</p>\n"
            if migration.get("urgency_note"):
                html += f"<p class='urgent'>{migration['urgency_note']}</p>\n"

        html += "</body></html>"
        return html

    def comparison_table(self, plans: List[Dict]) -> str:
        if not plans:
            return "<p>No matching plans found.</p>"
        html = "<table>\n<tr><th>Provider</th><th>Plan</th><th>vCPU</th><th>RAM (GB)</th><th>Price (USD)</th></tr>\n"
        for p in plans:
            html += f"<tr><td>{p.get('provider','')}</td><td>{p.get('plan','')}</td>"
            html += f"<td>{p.get('vcpu','')}</td><td>{p.get('ram_gb','')}</td>"
            html += f"<td>${p.get('price',0):.2f}</td></tr>\n"
        html += "</table>\n"
        return html

    def svg_break_even(self, csm: Dict) -> str:
        w, h = 500, 250
        pad = 40
        months = sorted(csm.keys(), key=lambda x: int(x))
        values = [csm[m] for m in months]
        if not values:
            return ""
        min_v = min(min(values), 0)
        max_v = max(max(values), 1)
        span = max_v - min_v or 1
        svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">\n'
        svg += f'<text x="{w//2}" y="15" text-anchor="middle" font-size="14" font-weight="bold">Break-even Cost Curve</text>\n'
        zero_y = pad + ((max_v - 0) / span) * (h - 2*pad)
        svg += f'<line x1="{pad}" y1="{zero_y:.0f}" x2="{w-pad}" y2="{zero_y:.0f}" stroke="#999" stroke-dasharray="4"/>\n'
        points = []
        for i, (m, v) in enumerate(zip(months, values)):
            x = pad + (i / max(len(months)-1, 1)) * (w - 2*pad)
            y = pad + ((max_v - v) / span) * (h - 2*pad)
            points.append(f"{x:.0f},{y:.0f}")
            color = "#e74c3c" if v < 0 else "#27ae60"
            svg += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="4" fill="{color}"/>\n'
            svg += f'<text x="{x:.0f}" y="{h-5}" text-anchor="middle" font-size="10">Mo {m}</text>\n'
        if len(points) > 1:
            svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="#3498db" stroke-width="2"/>\n'
        svg += '</svg>\n'
        return svg

    def svg_decay_trend(self, decay: Dict, label: str, total_gb: float = 100) -> str:
        w, h = 500, 200
        pad = 40
        current_pct = decay.get("current_pct", 0)
        growth = decay.get("growth_gb_per_day", 0)
        days_to_red = decay.get("days_to_red")
        svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">\n'
        svg += f'<text x="{w//2}" y="15" text-anchor="middle" font-size="14" font-weight="bold">{label} Headroom Decay</text>\n'
        for pct, color, tier in [(70, "#f1c40f", "YELLOW"), (85, "#e67e22", "RED"), (95, "#e74c3c", "CRIT")]:
            y = pad + ((100 - pct) / 100) * (h - 2*pad)
            svg += f'<line x1="{pad}" y1="{y:.0f}" x2="{w-pad}" y2="{y:.0f}" stroke="{color}" stroke-dasharray="4"/>\n'
            svg += f'<text x="{w-pad+5}" y="{y:.0f}" font-size="9" fill="{color}">{tier}</text>\n'
        x_start = pad
        y_start = pad + ((100 - current_pct) / 100) * (h - 2*pad)
        svg += f'<circle cx="{x_start}" cy="{y_start:.0f}" r="4" fill="#3498db"/>\n'
        svg += f'<text x="{x_start+8}" y="{y_start:.0f}" font-size="10">Now: {current_pct}%</text>\n'
        if growth > 0:
            max_days = max(days_to_red or 60, 60)
            future_pct = min(current_pct + (growth / total_gb * 100 * max_days), 100)
            x_end = w - pad
            y_end = pad + ((100 - future_pct) / 100) * (h - 2*pad)
            svg += f'<line x1="{x_start}" y1="{y_start:.0f}" x2="{x_end}" y2="{y_end:.0f}" stroke="#3498db" stroke-width="2"/>\n'
        svg += '</svg>\n'
        return svg

    def _html_head(self) -> str:
        return """<!DOCTYPE html>
<html><head><title>VPS Simulation Report</title>
<style>
body { font-family: -apple-system, Arial, sans-serif; margin: 20px; max-width: 900px; }
h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px; }
h2 { color: #34495e; margin-top: 30px; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background: #f8f9fa; }
.urgent { background: #fdecea; border-left: 4px solid #e74c3c; padding: 10px; margin: 10px 0; }
.flag { color: #e74c3c; font-weight: bold; }
.stale { color: #e74c3c; font-weight: bold; }
.verdict { font-weight: bold; padding: 5px; background: #f8f9fa; border-radius: 4px; }
svg { margin: 10px 0; }
</style>
</head><body>
<h1>VPS Capacity Simulation Report</h1>
"""

    def _baseline_section(self, baseline: Dict) -> str:
        html = "<table>\n<tr><th>Resource</th><th>Used</th><th>Total</th><th>%</th></tr>\n"
        for resource in ["ram", "cpu", "disk"]:
            info = baseline.get(resource, {})
            if resource == "cpu":
                html += f"<tr><td>CPU</td><td>{info.get('usr_pct',0)}% usr, {info.get('steal_pct',0)}% steal</td>"
                html += f"<td>{info.get('cores',0)} cores</td><td>-</td></tr>\n"
            else:
                used = info.get("used_gb", 0)
                total = info.get("total_gb", 1)
                pct = round((used/total)*100, 1) if total else 0
                html += f"<tr><td>{resource.upper()}</td><td>{used} GB</td><td>{total} GB</td><td>{pct}%</td></tr>\n"
        html += "</table>\n"
        containers = baseline.get("containers", [])
        if containers:
            html += "<h3>Containers</h3>\n<table>\n<tr><th>Name</th><th>CPU %</th><th>RAM (MB)</th></tr>\n"
            for c in containers:
                html += f"<tr><td>{c['name']}</td><td>{c['cpu_pct']}</td><td>{c['mem_mb']}</td></tr>\n"
            html += "</table>\n"
        return html
