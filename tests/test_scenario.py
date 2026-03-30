# tests/test_scenario.py
import pytest
import yaml
import tempfile
import os
from scenario import ScenarioLoader, Scenario, ProjectionEngine


def test_load_scenario_correct_schema():
    """Load scenario and verify all spec-required fields are accessible."""
    loader = ScenarioLoader()
    scenario = loader.load("scenarios/scenario-3-arc-sprint.yaml")
    assert scenario.name == "arc-sprint"
    assert scenario.duration_minutes == 45
    assert scenario.concurrency["ao_workers"] == 4
    assert len(scenario.add_processes) == 2
    assert scenario.add_processes[0]["name"] == "claude-worker"
    assert scenario.add_processes[0]["ram_mb"] == 480
    assert scenario.add_processes[0]["cpu_pct"] == 18
    assert scenario.add_processes[0]["disk_io_mbps"] == 8
    assert scenario.add_load["signet_connections"] == 6
    assert scenario.last_calibrated == "2026-03-30"
    assert scenario.stale_after_days == 30

def test_validation_missing_required_field():
    """Exit code 1 when add_processes entry missing required field."""
    bad_yaml = {
        "name": "bad", "description": "missing cpu_pct",
        "last_calibrated": "2026-03-30", "stale_after_days": 30,
        "concurrency": {"ao_workers": 0, "zeroclaw_active": False, "researcher_agents": 0},
        "add_processes": [{"name": "test", "count": 1, "ram_mb": 100}],
        "add_load": {}, "duration_minutes": 10
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(bad_yaml, f)
        path = f.name
    try:
        loader = ScenarioLoader()
        with pytest.raises(SystemExit):
            loader.load(path)
    finally:
        os.unlink(path)

def test_validation_unknown_field_warns(capsys):
    """Unknown fields in add_processes emit warning but don't error."""
    data = {
        "name": "warn-test", "description": "unknown field",
        "last_calibrated": "2026-03-30", "stale_after_days": 30,
        "concurrency": {"ao_workers": 0, "zeroclaw_active": False, "researcher_agents": 0},
        "add_processes": [{"name": "t", "count": 1, "ram_mb": 100, "cpu_pct": 5, "mystery_field": 99}],
        "add_load": {}, "duration_minutes": 10
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(data, f)
        path = f.name
    try:
        loader = ScenarioLoader()
        scenario = loader.load(path)
        captured = capsys.readouterr()
        assert "mystery_field" in captured.err
        assert scenario.name == "warn-test"
    finally:
        os.unlink(path)

def test_staleness_check():
    """Flag stale scenario when last_calibrated > stale_after_days ago."""
    loader = ScenarioLoader()
    scenario = loader.load("scenarios/scenario-3-arc-sprint.yaml")
    assert scenario.is_stale(today="2026-05-15") is True
    assert scenario.is_stale(today="2026-04-01") is False

def test_list_scenarios():
    """List all scenario files."""
    loader = ScenarioLoader()
    names = loader.list_scenarios("scenarios/")
    assert len(names) >= 3

def test_disk_storage_mb_defaults_to_zero():
    """disk_storage_mb absent in YAML defaults to 0."""
    loader = ScenarioLoader()
    scenario = loader.load("scenarios/scenario-3-arc-sprint.yaml")
    ollama_proc = [p for p in scenario.add_processes if p["name"] == "ollama-qwen2.5-1.5b"][0]
    assert ollama_proc.get("disk_storage_mb", 0) == 0

# --- Projection Engine Tests ---

def test_project_ram(mock_baseline_data, mock_scenario_data):
    """RAM projection: baseline.used + sum(process.ram_mb*count)/1024 + overhead/1024"""
    engine = ProjectionEngine(mock_baseline_data)
    scenario = Scenario(mock_scenario_data)
    ram = engine.project_ram(scenario)
    # 4.2 + (480*2+1200*1)/1024 + 245/1024 = 4.2 + 2.109375 + 0.23925... = 6.55
    expected = round(4.2 + (2160/1024) + (245/1024), 2)
    assert ram == expected

def test_project_cpu(mock_baseline_data, mock_scenario_data):
    """CPU projection: ceil((sum(cpu_pct*count) + baseline.usr_pct) / 80)"""
    engine = ProjectionEngine(mock_baseline_data)
    scenario = Scenario(mock_scenario_data)
    cores = engine.project_cpu(scenario)
    # 8.5 + (18*2 + 35*1) = 79.5 -> ceil(79.5/80) = 1
    assert cores == 1

def test_project_disk(mock_baseline_data, mock_scenario_data):
    """Disk: baseline.used + ao_workers*0.2 + sum(storage*count)/1024"""
    engine = ProjectionEngine(mock_baseline_data)
    scenario = Scenario(mock_scenario_data)
    disk = engine.project_disk(scenario)
    # 71.0 + 2*0.2 + (200*2+0)/1024 = 71.0 + 0.4 + 0.390625 = 71.8
    expected = round(71.0 + 0.4 + (400/1024), 1)
    assert disk == expected

def test_project_disk_io(mock_baseline_data, mock_scenario_data):
    """Disk IO: sum(disk_io_mbps * count)"""
    engine = ProjectionEngine(mock_baseline_data)
    scenario = Scenario(mock_scenario_data)
    assert engine.project_disk_io(scenario) == 16  # 8*2 + 0*1

def test_signet_bottleneck(mock_baseline_data, mock_scenario_data):
    """Signet: connections * 200ms. Flag if > 500ms."""
    engine = ProjectionEngine(mock_baseline_data)
    scenario = Scenario(mock_scenario_data)
    assert engine.signet_queue_ms(scenario) == 800
    result = engine.project_all(scenario)
    assert result["signet_bottleneck"] is True
