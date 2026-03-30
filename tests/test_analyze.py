import pytest
from analyze import BottleneckAnalyzer


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
