import pytest
from calibrate import ProcessMeasurer


def test_measure_running_processes():
    """Measure RAM/CPU of running processes matching pattern."""
    measurer = ProcessMeasurer()
    measurements = measurer.measure("python")  # Should find this process
    assert isinstance(measurements, dict)


def test_write_calibration_yaml():
    """Write calibration results to YAML."""
    import tempfile
    measurer = ProcessMeasurer()

    with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
        path = f.name

    measurer.write_yaml(path, {"test": "data"})

    with open(path) as f:
        content = f.read()
    assert "test" in content
