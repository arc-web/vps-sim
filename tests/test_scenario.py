import pytest
from pathlib import Path
from scenario import ScenarioLoader, Scenario

# Get the vps-sim root directory
ROOT = Path(__file__).parent.parent

def test_load_scenario():
    """Load scenario YAML and parse into Scenario object."""
    loader = ScenarioLoader()
    scenario = loader.load(str(ROOT / "scenarios/scenario-1-daily-orchestration.yaml"))
    assert scenario.name == "Daily Orchestration"
    assert scenario.duration_hours == 24
    assert scenario.ao_workers["count"] == 2

def test_validate_scenario():
    """Verify required fields in scenario."""
    loader = ScenarioLoader()
    scenario = loader.load(str(ROOT / "scenarios/scenario-2-google-ads-pipeline.yaml"))
    assert hasattr(scenario, "processes")
    assert len(scenario.processes) > 0

def test_scenario_list():
    """List all available scenarios."""
    loader = ScenarioLoader()
    scenarios = loader.list_scenarios(str(ROOT / "scenarios/"))
    assert len(scenarios) >= 3

def test_project_ram_requirement(mock_baseline_data):
    """Project RAM requirement for scenario."""
    from scenario import ProjectionEngine
    engine = ProjectionEngine(mock_baseline_data)
    scenario_data = {
        "name": "Test", "description": "Test scenario", "duration_hours": 24,
        "baseline_overlay": {"ram_delta_mb": 256, "cpu_delta_pct": 5.0, "disk_delta_mb": 50},
        "ao_workers": {"count": 2, "ram_per_worker_mb": 384, "cpu_per_worker_pct": 12.0},
        "processes": [{"name": "test", "count": 1, "ram_mb": 512, "cpu_pct": 10.0}],
        "disk_growth_mb": 100
    }
    scenario = Scenario(scenario_data)

    ram_gb = engine.project_ram(scenario)
    assert ram_gb > 0
    assert isinstance(ram_gb, float)

def test_project_cpu_requirement(mock_baseline_data):
    """Project CPU cores needed."""
    from scenario import ProjectionEngine
    engine = ProjectionEngine(mock_baseline_data)
    scenario_data = {
        "name": "Test", "description": "Test scenario", "duration_hours": 24,
        "baseline_overlay": {"ram_delta_mb": 256, "cpu_delta_pct": 5.0, "disk_delta_mb": 50},
        "ao_workers": {"count": 2, "ram_per_worker_mb": 384, "cpu_per_worker_pct": 12.0},
        "processes": [{"name": "test", "count": 1, "ram_mb": 512, "cpu_pct": 10.0}],
        "disk_growth_mb": 100
    }
    scenario = Scenario(scenario_data)

    cores = engine.project_cpu(scenario)
    assert cores >= 2
    assert isinstance(cores, int)
