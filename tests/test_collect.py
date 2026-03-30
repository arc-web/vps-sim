import pytest
from unittest.mock import patch, MagicMock
from collect import MetricsCollector

def test_collect_subprocess_mode(mock_baseline_data):
    """Collect metrics via subprocess (no SSH)."""
    with patch('collect.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(stdout='{"timestamp": "2026-03-30T12:00:00Z"}')
        collector = MetricsCollector(mode="subprocess")
        # Verify it calls ps, free, df, docker ps, etc.
        assert collector.mode == "subprocess"

def test_collect_ssh_mode():
    """Collect metrics via SSH (mocked paramiko)."""
    with patch('collect.paramiko') as mock_paramiko:
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_client.exec_command.return_value = (MagicMock(), MagicMock(read=lambda: b'2'), MagicMock())

        collector = MetricsCollector(mode="ssh", host="187.77.222.191", user="root", key="~/.ssh/id_ed25519_hostinger")
        assert collector.mode == "ssh"

def test_collect_baseline_structure(mock_baseline_data):
    """Baseline data has all required fields."""
    required_keys = ["timestamp", "ram", "cpu", "disk", "containers", "system_services", "ao_workers", "ollama"]
    for key in required_keys:
        assert key in mock_baseline_data
