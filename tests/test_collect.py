import pytest
from unittest.mock import patch, MagicMock
from collect import MetricsCollector

def test_collect_subprocess_mode(mock_baseline_data):
    """Collect metrics via subprocess (no SSH)."""
    with patch('collect.subprocess.run') as mock_run:
        # Mock subprocess.run to return realistic command outputs
        def mock_cmd_output(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', '')
            if 'free -b' in cmd:
                # Mem:  8360878080  4502118400  3858759680  0  1234567890  3858759680
                return MagicMock(stdout='Mem: 8360878080 4502118400 3858759680 0 1234567890 3858759680')
            elif '/proc/loadavg' in cmd:
                return MagicMock(stdout='1.4 1.2 0.9 1/4 1234')
            elif 'grep -c' in cmd:
                return MagicMock(stdout='2')
            elif 'df -B1' in cmd:
                return MagicMock(stdout='/ 103079215104 76293898240 26785316864 0 0')
            else:
                return MagicMock(stdout='')

        mock_run.side_effect = mock_cmd_output
        collector = MetricsCollector(mode="subprocess")
        assert collector.mode == "subprocess"

        # Call collect() and verify returned dict structure
        result = collector.collect()
        assert "timestamp" in result
        assert "ram" in result
        assert "cpu" in result
        assert "disk" in result
        assert "containers" in result
        assert "system_services" in result
        assert "ao_workers" in result
        assert "ollama" in result
        assert isinstance(result["ollama"], list)

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
