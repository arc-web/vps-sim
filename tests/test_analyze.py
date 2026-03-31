import pytest
from analyze import BottleneckAnalyzer, HeadroomDecayTracker, BreakEvenCalculator, MigrationPlanner

def test_bottleneck_tiers_per_provider():
    analyzer = BottleneckAnalyzer()
    requirements = {"ram_gb": 12.0, "cpu_cores": 6, "disk_gb": 80, "disk_io_mbps": 40}
    plan_8core = {"ram_gb": 16, "vcpu": 8, "disk_gb": 240, "disk_io_max_mbps": 100}
    result = analyzer.identify(requirements, plan_8core)
    assert result["cpu"]["tier"] == "YELLOW"
    plan_4core = {"ram_gb": 16, "vcpu": 4, "disk_gb": 240, "disk_io_max_mbps": 100}
    result = analyzer.identify(requirements, plan_4core)
    assert result["cpu"]["tier"] == "CRITICAL"

def test_bottleneck_spec_thresholds():
    analyzer = BottleneckAnalyzer()
    assert analyzer._assign_tier("ram", 65) == "GREEN"
    assert analyzer._assign_tier("ram", 75) == "YELLOW"
    assert analyzer._assign_tier("ram", 90) == "RED"
    assert analyzer._assign_tier("ram", 96) == "CRITICAL"
    assert analyzer._assign_tier("cpu", 55) == "GREEN"
    assert analyzer._assign_tier("cpu", 65) == "YELLOW"
    assert analyzer._assign_tier("cpu", 80) == "RED"
    assert analyzer._assign_tier("cpu", 95) == "CRITICAL"

def test_bottleneck_output_has_verdict():
    analyzer = BottleneckAnalyzer()
    requirements = {"ram_gb": 7.5, "cpu_cores": 2, "disk_gb": 90, "disk_io_mbps": 10}
    plan = {"ram_gb": 8, "vcpu": 2, "disk_gb": 96, "disk_io_max_mbps": 100}
    result = analyzer.identify(requirements, plan)
    assert "primary_bottleneck" in result
    assert "verdict" in result

def test_decay_returns_per_resource_dict(temp_db_path, mock_baseline_data):
    from db import BaselineDB
    db = BaselineDB(temp_db_path)
    db.create_tables()
    for i in range(5):
        b = {**mock_baseline_data, "timestamp": f"2026-03-2{i+1}T12:00:00Z"}
        b["ram"] = {**mock_baseline_data["ram"], "used_gb": 4.0 + (i * 0.3)}
        b["disk"] = {**mock_baseline_data["disk"], "used_gb": 71.0 + (i * 0.2)}
        db.insert_baseline(b)
    tracker = HeadroomDecayTracker(db)
    result = tracker.analyze()
    assert "ram" in result
    assert "disk" in result
    assert "days_to_yellow" in result["ram"]
    assert "days_to_red" in result["ram"]
    assert "days_to_critical" in result["ram"]
    assert "confidence" in result["ram"]
    assert result["ram"]["confidence"] == "low"

def test_decay_insufficient_data(temp_db_path, mock_baseline_data):
    from db import BaselineDB
    db = BaselineDB(temp_db_path)
    db.create_tables()
    db.insert_baseline(mock_baseline_data)
    tracker = HeadroomDecayTracker(db)
    result = tracker.analyze()
    assert result["ram"]["confidence"] == "none"
    assert result["ram"]["skipped"] is True

def test_break_even_with_monthly_breakdown():
    calc = BreakEvenCalculator(
        current_vps_usd=14.99, target_vps_usd=32.49,
        api_calls_per_day=200, avg_tokens_per_call=800,
        local_model_handles_pct=0.40, api_cost_per_1k_tokens=0.003,
    )
    result = calc.compute()
    assert "break_even_months" in result
    assert "monthly_api_savings_usd" in result
    assert "cumulative_savings_by_month" in result
    assert "recommendation" in result
    csm = result["cumulative_savings_by_month"]
    assert "1" in csm and "3" in csm and "6" in csm and "12" in csm
    assert csm["1"] < 0

def test_migration_plan_has_steps():
    planner = MigrationPlanner()
    plan = planner.generate(target_provider="hetzner", target_plan="cpx41")
    assert "target" in plan
    assert "steps" in plan
    assert len(plan["steps"]) >= 5
    assert "rollback" in plan
    assert "estimated_downtime_minutes" in plan
    assert "urgency_note" in plan
