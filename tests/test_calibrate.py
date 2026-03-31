import pytest
import yaml
import tempfile
import os
from unittest.mock import patch, MagicMock
from calibrate import Calibrator

def test_measure_process_parses_ps_output():
    ps_output = """root  1234 18.0  3.5 512000 480000 ? Sl 12:00 0:30 claude-worker
root  1235 17.5  3.4 510000 475000 ? Sl 12:00 0:28 claude-worker"""
    with patch.object(Calibrator, '_run_cmd', return_value=ps_output):
        cal = Calibrator(mode="subprocess")
        result = cal.measure_process("claude-worker", duration=1)
        assert result["count"] == 2
        assert result["total_ram_mb"] > 0
        assert result["avg_cpu_pct"] > 0
        assert result["avg_ram_mb"] > 0

def test_writeback_updates_yaml():
    scenario_data = {
        "name": "test", "description": "test", "last_calibrated": "2026-01-01", "stale_after_days": 30,
        "concurrency": {"ao_workers": 0, "zeroclaw_active": False, "researcher_agents": 0},
        "add_processes": [{"name": "claude-worker", "count": 2, "ram_mb": 100, "cpu_pct": 5}],
        "add_load": {}, "duration_minutes": 10,
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(scenario_data, f)
        path = f.name
    try:
        cal = Calibrator(mode="subprocess")
        cal.writeback(path, "claude-worker", ram_mb=480, cpu_pct=18.0)
        with open(path) as f:
            updated = yaml.safe_load(f)
        proc = updated["add_processes"][0]
        assert proc["ram_mb"] == 480
        assert proc["cpu_pct"] == 18.0
        assert updated["last_calibrated"] != "2026-01-01"
    finally:
        os.unlink(path)

def test_measure_missing_process_returns_zero():
    with patch.object(Calibrator, '_run_cmd', return_value=""):
        cal = Calibrator(mode="subprocess")
        result = cal.measure_process("nonexistent-proc", duration=1)
        assert result["count"] == 0
