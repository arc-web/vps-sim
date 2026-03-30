import pytest
from report import ReportBuilder
import json

def test_build_json_report():
    """Generate JSON report output."""
    builder = ReportBuilder()

    report_data = {
        "scenario": "Daily Orchestration",
        "requirements": {"ram_gb": 6.5, "cpu_cores": 4, "disk_gb": 85},
        "matched_plans": [
            {"provider": "hetzner", "plan": "cpx31", "price": 17.29}
        ],
        "bottlenecks": {"ram_gb": {"tier": "YELLOW", "utilization_pct": 83}},
        "migration": {"urgency": "recommended", "action": "Plan upgrade"}
    }

    json_output = builder.to_json(report_data)
    parsed = json.loads(json_output)

    assert parsed["scenario"] == "Daily Orchestration"
    assert "matched_plans" in parsed

def test_build_comparison_table():
    """Generate provider comparison HTML table."""
    builder = ReportBuilder()

    plans = [
        {"provider": "hetzner", "plan": "cpx31", "vcpu": 4, "ram_gb": 8, "price": 17.29},
        {"provider": "hostinger", "plan": "kvm4", "vcpu": 4, "ram_gb": 16, "price": 12.99}
    ]

    html = builder.comparison_table(plans)
    assert "hetzner" in html
    assert "hostinger" in html
    assert "<table" in html and "</table>" in html

def test_build_html_report():
    """Generate complete HTML report with inline SVG charts."""
    builder = ReportBuilder()

    report_data = {
        "scenario": "Daily Orchestration",
        "requirements": {"ram_gb": 6.5, "cpu_cores": 4, "disk_gb": 85},
        "matched_plans": [{"provider": "hetzner", "plan": "cpx31", "vcpu": 4, "ram_gb": 8, "price": 17.29}],
        "bottlenecks": {"ram_gb": {"tier": "YELLOW", "utilization_pct": 83}}
    }

    html = builder.to_html(report_data)
    assert "<!DOCTYPE" in html
    assert "Daily Orchestration" in html
    assert "<svg" in html  # Inline SVG

def test_svg_bar_chart():
    """Generate inline SVG bar chart."""
    builder = ReportBuilder()

    data = {"RAM": 83, "CPU": 75, "Disk": 45}
    svg = builder.svg_bar_chart(data, title="Resource Utilization")

    assert "<svg" in svg
    assert "RAM" in svg
    assert "83" in svg
