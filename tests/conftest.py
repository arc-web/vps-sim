import pytest
import tempfile
import os

@pytest.fixture
def temp_db_path():
    """Temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)

@pytest.fixture
def mock_baseline_data():
    """Sample baseline collection matching spec schema exactly."""
    return {
        "timestamp": "2026-03-30T12:00:00Z",
        "ram": {"total_gb": 7.8, "used_gb": 4.2, "available_gb": 3.6, "overhead_gb": 0.5},
        "cpu": {"cores": 2, "load_1m": 1.4, "load_5m": 1.2, "steal_pct": 0.8, "iowait_pct": 1.2, "usr_pct": 8.5},
        "disk": {"total_gb": 96.0, "used_gb": 71.0, "available_gb": 25.0, "read_mbps": 2.1, "write_mbps": 0.3},
        "containers": [
            {"name": "openclaw", "cpu_pct": 12.4, "mem_mb": 512},
            {"name": "zeroclaw", "cpu_pct": 3.1, "mem_mb": 280},
            {"name": "uptime-kuma", "cpu_pct": 0.5, "mem_mb": 95}
        ],
        "system_services": {"embedding_proxy_mb": 180, "caddy_mb": 45, "signet_mb": 120, "measured_overhead_mb": 245},
        "ao_workers": {"count": 0, "total_ram_mb": 0, "avg_cpu_pct": 0},
        "ollama": {"loaded_models": []},
        "tag": None
    }

@pytest.fixture
def mock_scenario_data():
    """Sample scenario YAML data matching spec schema."""
    return {
        "name": "test-scenario",
        "description": "Test scenario for unit tests",
        "last_calibrated": "2026-03-30",
        "stale_after_days": 30,
        "concurrency": {
            "ao_workers": 2,
            "zeroclaw_active": True,
            "researcher_agents": 1
        },
        "add_processes": [
            {"name": "claude-worker", "count": 2, "ram_mb": 480, "cpu_pct": 18, "disk_io_mbps": 8, "disk_storage_mb": 200},
            {"name": "ollama-qwen2.5-1.5b", "count": 1, "ram_mb": 1200, "cpu_pct": 35, "disk_io_mbps": 0}
        ],
        "add_load": {
            "signet_connections": 4,
            "n8n_webhooks_per_min": 6,
            "embedding_proxy_requests_per_min": 4
        },
        "duration_minutes": 45
    }
