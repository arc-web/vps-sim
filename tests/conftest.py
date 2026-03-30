import pytest

@pytest.fixture
def mock_baseline_data():
    """Baseline system data for testing."""
    return {
        "ram": {
            "used_gb": 16.0
        },
        "cpu": {
            "usr_pct": 30.0,
            "cores": 2
        },
        "disk": {
            "used_gb": 50.0
        }
    }
