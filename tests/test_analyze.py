import pytest
from analyze import BottleneckAnalyzer
import tempfile
from db import BaselineDB


def test_identify_bottlenecks(mock_baseline_data):
    """Identify resource bottlenecks by tier."""
    analyzer = BottleneckAnalyzer()

    # Simulate high RAM usage
    scenario_reqs = {"ram_gb": 7.0, "cpu_cores": 2, "disk_gb": 90}
    hardware = {"ram_gb": 7.8, "cpu_cores": 2, "disk_gb": 96}

    bottlenecks = analyzer.identify(scenario_reqs, hardware)
    assert "ram_gb" in bottlenecks
    assert bottlenecks["ram_gb"]["tier"] in ["GREEN", "YELLOW", "RED", "CRITICAL"]


def test_tier_assignment():
    """Verify tier thresholds."""
    analyzer = BottleneckAnalyzer()

    # 90% = RED (85-95)
    tier = analyzer._assign_tier(0.90)
    assert tier == "RED"

    # 95% = CRITICAL
    tier = analyzer._assign_tier(0.95)
    assert tier == "CRITICAL"


def test_calculate_headroom_decay():
    """Calculate headroom decline using linear regression."""
    from analyze import HeadroomDecayTracker

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_db_path = f.name

    db = BaselineDB(temp_db_path)
    db.create_tables()

    # Insert 5 baselines with increasing RAM usage
    for i in range(5):
        baseline = {
            "timestamp": f"2026-03-2{i}T12:00:00Z",
            "ram": {
                "used_gb": 3.0 + (i * 0.5),
                "total_gb": 8.0
            },
            "cpu": {
                "usr_pct": 30.0,
                "cores": 2
            },
            "disk": {
                "used_gb": 50.0
            }
        }
        db.insert_baseline(baseline)

    tracker = HeadroomDecayTracker(db)
    decay = tracker.estimate_days_to_full()

    assert decay > 0  # Should predict future exhaustion
    assert isinstance(decay, (int, float))

    db.close()


def test_break_even_calculation():
    """Calculate break-even month for upgrade vs API savings."""
    from analyze import BreakEvenCalculator

    calc = BreakEvenCalculator(
        api_calls_per_day=200,
        avg_tokens_per_call=800,
        local_model_handles_pct=0.40,
        api_cost_per_1k_tokens=0.003,
        current_vps_cost_usd=14.99,
        upgrade_cost_usd=32.49
    )

    break_even_month = calc.compute_break_even()
    assert break_even_month > 0
    assert isinstance(break_even_month, int)


def test_migration_plan():
    """Generate migration recommendation."""
    from analyze import MigrationPlanner

    bottlenecks = {
        "ram_gb": {"tier": "RED", "utilization_pct": 88},
        "cpu_cores": {"tier": "YELLOW", "utilization_pct": 75},
        "disk_gb": {"tier": "GREEN", "utilization_pct": 45}
    }

    planner = MigrationPlanner()
    plan = planner.generate(bottlenecks)

    assert "urgency" in plan
    assert "action" in plan
    assert plan["urgency"] in ["urgent", "recommended", "ok"]
