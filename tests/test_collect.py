import pytest
from unittest.mock import patch, MagicMock
from collect import MetricsCollector, parse_free, parse_mpstat, parse_df, parse_docker_stats, parse_loadavg, compute_measured_overhead

def test_parse_free():
    output = """              total        used        free      shared  buff/cache   available
Mem:     8360878080  4502118400  1234567890   123456789  2624191790  3858759680
Swap:    1073741824           0  1073741824"""
    result = parse_free(output)
    assert abs(result["total_gb"] - 7.79) < 0.1
    assert abs(result["used_gb"] - 4.19) < 0.1
    assert abs(result["available_gb"] - 3.59) < 0.1

def test_parse_mpstat():
    output = """Linux 6.8.0 (openclaw)   03/30/26   _x86_64_

12:00:00     CPU    %usr   %nice    %sys %iowait   %steal    %idle
12:00:01     all    8.50    0.00    2.00    1.20     0.80    87.50
12:00:02     all    9.00    0.00    1.50    1.00     0.50    88.00
12:00:03     all    8.00    0.00    2.50    1.40     1.10    87.00
Average:     all    8.50    0.00    2.00    1.20     0.80    87.50"""
    result = parse_mpstat(output)
    assert result["usr_pct"] == 8.5
    assert result["iowait_pct"] == 1.2
    assert result["steal_pct"] == 0.8

def test_parse_df():
    output = """Filesystem       1B-blocks        Used   Available Use% Mounted on
/dev/sda1    103079215104 76293898240 26785316864  75% /"""
    result = parse_df(output)
    assert abs(result["total_gb"] - 96.0) < 1
    assert abs(result["used_gb"] - 71.1) < 1
    assert abs(result["available_gb"] - 24.9) < 1

def test_parse_docker_stats():
    output = '{"Name":"openclaw","CPUPerc":"12.40%","MemUsage":"512MiB / 7.8GiB"}\n{"Name":"zeroclaw","CPUPerc":"3.10%","MemUsage":"280MiB / 7.8GiB"}'
    result = parse_docker_stats(output)
    assert len(result) == 2
    assert result[0]["name"] == "openclaw"
    assert result[0]["cpu_pct"] == 12.4
    assert result[0]["mem_mb"] == 512

def test_parse_loadavg():
    output = "1.40 1.20 0.90 2/128 12345"
    result = parse_loadavg(output)
    assert result["load_1m"] == 1.4
    assert result["load_5m"] == 1.2

def test_compute_measured_overhead():
    used_mb = 4200
    container_ram = 512 + 280 + 95
    service_ram = 180 + 45 + 120
    ao_ram = 0
    ollama_ram = 0
    overhead = compute_measured_overhead(used_mb, container_ram, service_ram, ao_ram, ollama_ram)
    assert overhead == used_mb - container_ram - service_ram - ao_ram - ollama_ram

def test_collect_returns_spec_schema():
    with patch('collect.MetricsCollector._run_cmd') as mock_cmd:
        mock_cmd.side_effect = lambda cmd: {
            "free -b": "              total        used        free      shared  buff/cache   available\nMem:     8360878080  4502118400  1234567890   123456789  2624191790  3858759680\nSwap:    1073741824           0  1073741824",
            "mpstat 1 3": "Linux 6.8.0\n\n12:00:00     CPU    %usr   %nice    %sys %iowait   %steal    %idle\nAverage:     all    8.50    0.00    2.00    1.20     0.80    87.50",
            "cat /proc/loadavg": "1.40 1.20 0.90 2/128 12345",
            "grep -c ^processor /proc/cpuinfo": "2",
            "df -B1 /": "Filesystem       1B-blocks        Used   Available Use% Mounted on\n/dev/sda1    103079215104 76293898240 26785316864  75% /",
            "docker stats --no-stream --format '{{json .}}'": "",
            "ollama ps": "",
            "iostat -x 1 3": "",
        }.get(cmd, "")

        collector = MetricsCollector(mode="subprocess")
        result = collector.collect()

        for key in ["timestamp", "ram", "cpu", "disk", "containers", "system_services", "ao_workers", "ollama", "tag"]:
            assert key in result, f"Missing key: {key}"

        assert "total_gb" in result["ram"]
        assert "usr_pct" in result["cpu"]
        assert "steal_pct" in result["cpu"]
        assert "iowait_pct" in result["cpu"]
        assert "measured_overhead_mb" in result["system_services"]
        assert "loaded_models" in result["ollama"]
