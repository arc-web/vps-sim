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
