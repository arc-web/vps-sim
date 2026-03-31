import pytest
import json
from report import ReportBuilder

def test_json_output_urgent_flags_first():
    builder = ReportBuilder()
    data = {
        "urgent_flags": ["SIGNET_BOTTLENECK"],
        "generated_at": "2026-03-30T12:00:00Z",
        "baseline_age_minutes": 5, "baseline_stale": False,
        "scenarios": {}, "top_recommendation": {}, "headroom_decay": {}, "break_even": {},
    }
    output = builder.to_json(data)
    parsed = json.loads(output)
    keys = list(parsed.keys())
    assert keys[0] == "urgent_flags"

def test_html_has_all_9_sections():
    builder = ReportBuilder()
    data = _sample_report_data()
    html = builder.to_html(data)
    assert "Executive Summary" in html
    assert "Live Baseline" in html
    assert "Scenario Projections" in html
    assert "Provider Profiles" in html
    assert "Comparison Table" in html
    assert "Break-even Analysis" in html
    assert "Headroom Decay" in html
    assert "Bottleneck Summary" in html
    assert "Migration Plan" in html

def test_html_has_svg_charts():
    builder = ReportBuilder()
    data = _sample_report_data()
    html = builder.to_html(data)
    assert "<svg" in html

def test_comparison_table():
    builder = ReportBuilder()
    plans = [
        {"provider": "hetzner", "plan": "cpx41", "vcpu": 8, "ram_gb": 16, "price": 32.49},
        {"provider": "hostinger", "plan": "kvm4", "vcpu": 4, "ram_gb": 16, "price": 12.99},
    ]
    html = builder.comparison_table(plans)
    assert "hetzner" in html
    assert "hostinger" in html
    assert "<table" in html

def test_svg_break_even_curve():
    builder = ReportBuilder()
    csm = {"1": -15.0, "3": -10.0, "6": 5.0, "12": 25.0}
    svg = builder.svg_break_even(csm)
    assert "<svg" in svg
    assert "Break" in svg or "break" in svg

def test_svg_decay_chart():
    builder = ReportBuilder()
    decay = {"current_pct": 74, "growth_gb_per_day": 0.18, "days_to_yellow": 0, "days_to_red": 18}
    svg = builder.svg_decay_trend(decay, "Disk", total_gb=96)
    assert "<svg" in svg

def _sample_report_data():
    return {
        "urgent_flags": [],
        "generated_at": "2026-03-30T12:00:00Z",
        "baseline_age_minutes": 5, "baseline_stale": False,
        "baseline": {
            "ram": {"total_gb": 7.8, "used_gb": 4.2},
            "cpu": {"cores": 2, "usr_pct": 8.5, "steal_pct": 0.8},
            "disk": {"total_gb": 96, "used_gb": 71},
            "containers": [{"name": "openclaw", "cpu_pct": 12.4, "mem_mb": 512}],
        },
        "scenarios": {
            "arc-sprint": {
                "requirements": {"ram_gb": 8.5, "cpu_cores": 4, "disk_gb": 75},
                "bottlenecks": {"primary_bottleneck": "RAM", "verdict": "RED"},
            }
        },
        "provider_profiles": {
            "hetzner": {"cpx41": {"overview": "8 vCPU", "pros": ["Fast"], "cons": ["Price hike"], "risks": [], "opportunities": []}},
        },
        "matched_plans": [{"provider": "hetzner", "plan": "cpx41", "vcpu": 8, "ram_gb": 16, "price": 32.49}],
        "headroom_decay": {"disk": {"current_pct": 74, "growth_gb_per_day": 0.18, "days_to_red": 18}},
        "break_even": {"cumulative_savings_by_month": {"1": -15, "3": -10, "6": 5, "12": 25}, "break_even_months": 5.2},
        "top_recommendation": {"provider": "hetzner", "plan": "cpx41", "reason": "Best balance of performance and price."},
        "migration": {"target": "hetzner-cpx41", "steps": ["Snapshot", "Provision"], "rollback": "Restore snapshot", "urgency_note": "Price hike April 1"},
    }
