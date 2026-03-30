import pytest
import tempfile
import os
from pathlib import Path

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
    """Sample baseline collection data."""
    return {
        "timestamp": "2026-03-30T12:00:00Z",
        "ram": {"total_gb": 7.8, "used_gb": 4.2, "available_gb": 3.6, "overhead_gb": 0.5},
        "cpu": {"cores": 2, "load_1m": 1.4, "load_5m": 1.2, "steal_pct": 0.8, "iowait_pct": 1.2, "usr_pct": 8.5},
        "disk": {"total_gb": 96, "used_gb": 71, "available_gb": 25, "read_mbps": 2.1, "write_mbps": 0.3},
        "containers": [
            {"name": "openclaw", "cpu_pct": 12.4, "mem_mb": 512},
            {"name": "zeroclaw", "cpu_pct": 3.1, "mem_mb": 280}
        ],
        "system_services": {"embedding_proxy_mb": 180, "caddy_mb": 45, "signet_mb": 120, "measured_overhead_mb": 512},
        "ao_workers": {"count": 0, "total_ram_mb": 0, "avg_cpu_pct": 0},
        "ollama": [],
        "tag": None
    }
