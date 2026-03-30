"""VPS metrics collection via SSH or subprocess. All values parsed from real command output."""
import json
import subprocess
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    import paramiko
except ImportError:
    paramiko = None


def parse_free(output: str) -> Dict:
    for line in output.split('\n'):
        if line.startswith('Mem:'):
            parts = line.split()
            total = int(parts[1]) / (1024**3)
            used = int(parts[2]) / (1024**3)
            available = int(parts[6]) / (1024**3)
            return {"total_gb": round(total, 2), "used_gb": round(used, 2), "available_gb": round(available, 2)}
    return {"total_gb": 0, "used_gb": 0, "available_gb": 0}


def parse_mpstat(output: str) -> Dict:
    for line in output.split('\n'):
        if line.strip().startswith('Average:'):
            parts = line.split()
            return {"usr_pct": float(parts[2]), "iowait_pct": float(parts[5]), "steal_pct": float(parts[6])}
    return {"usr_pct": 0, "iowait_pct": 0, "steal_pct": 0}


def parse_loadavg(output: str) -> Dict:
    parts = output.strip().split()
    return {"load_1m": float(parts[0]), "load_5m": float(parts[1])}


def parse_df(output: str) -> Dict:
    lines = output.strip().split('\n')
    if len(lines) < 2:
        return {"total_gb": 0, "used_gb": 0, "available_gb": 0}
    parts = lines[-1].split()
    return {
        "total_gb": round(int(parts[1]) / (1024**3), 1),
        "used_gb": round(int(parts[2]) / (1024**3), 1),
        "available_gb": round(int(parts[3]) / (1024**3), 1),
    }


def parse_docker_stats(output: str) -> List[Dict]:
    containers = []
    for line in output.strip().split('\n'):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            cpu_str = data.get("CPUPerc", "0%").replace('%', '')
            mem_str = data.get("MemUsage", "0MiB")
            mem_mb = _parse_mem_usage(mem_str)
            containers.append({"name": data.get("Name", ""), "cpu_pct": float(cpu_str), "mem_mb": mem_mb})
        except (json.JSONDecodeError, ValueError):
            continue
    return containers


def _parse_mem_usage(mem_str: str) -> int:
    match = re.match(r'([\d.]+)\s*(MiB|GiB|KiB)', mem_str)
    if not match:
        return 0
    value, unit = float(match.group(1)), match.group(2)
    if unit == "GiB":
        return int(value * 1024)
    elif unit == "KiB":
        return int(value / 1024)
    return int(value)


def parse_iostat(output: str) -> Dict:
    read_mbps, write_mbps = 0.0, 0.0
    for line in output.split('\n'):
        parts = line.split()
        if len(parts) >= 6 and parts[0] not in ('Device', 'Linux', '', 'avg-cpu:'):
            try:
                read_mbps = float(parts[2]) if len(parts) > 2 else 0
                write_mbps = float(parts[3]) if len(parts) > 3 else 0
            except (ValueError, IndexError):
                pass
    return {"read_mbps": round(read_mbps, 2), "write_mbps": round(write_mbps, 2)}


def parse_ollama_ps(output: str) -> Dict:
    models = []
    for line in output.strip().split('\n'):
        if not line or line.startswith('NAME'):
            continue
        parts = line.split()
        if len(parts) >= 3:
            name = parts[0]
            size_str = parts[1] + " " + parts[2] if len(parts) > 2 else parts[1]
            ram_mb = _parse_model_size(size_str)
            models.append({"name": name, "ram_mb": ram_mb})
    return {"loaded_models": models}


def _parse_model_size(size_str: str) -> int:
    match = re.match(r'([\d.]+)\s*(GB|MB|KB)', size_str)
    if not match:
        return 0
    value, unit = float(match.group(1)), match.group(2)
    if unit == "GB":
        return int(value * 1024)
    elif unit == "KB":
        return int(value / 1024)
    return int(value)


def compute_measured_overhead(used_mb: float, container_ram_mb: float, service_ram_mb: float,
                              ao_ram_mb: float, ollama_ram_mb: float) -> float:
    return max(0, used_mb - container_ram_mb - service_ram_mb - ao_ram_mb - ollama_ram_mb)


def parse_ao_workers(ps_output: str, pgrep_output: str) -> Dict:
    count = 0
    total_rss_kb = 0
    total_cpu = 0.0
    for line in ps_output.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 6:
            count += 1
            total_cpu += float(parts[2])
            total_rss_kb += int(parts[5])
    return {
        "count": count,
        "total_ram_mb": round(total_rss_kb / 1024, 1) if total_rss_kb else 0,
        "avg_cpu_pct": round(total_cpu / max(count, 1), 1),
    }


class MetricsCollector:
    """Collect VPS metrics via SSH or subprocess. No hardcoded values."""

    def __init__(self, mode: str = "subprocess", host: str = None, user: str = None,
                 key: str = None, timeout: int = 10):
        self.mode = mode
        self.host = host
        self.user = user
        self.key = key
        self.timeout = timeout
        self.ssh_client = None

        if mode == "ssh":
            if paramiko is None:
                print("ERROR: paramiko not installed. Cannot use SSH mode.", file=sys.stderr)
                sys.exit(1)
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(hostname=host, username=user, key_filename=key, timeout=timeout)

    def _run_cmd(self, cmd: str) -> str:
        if self.mode == "ssh" and self.ssh_client:
            _, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=self.timeout)
            return stdout.read().decode().strip()
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=self.timeout)
            return result.stdout.strip()

    def collect(self, tag: Optional[str] = None) -> Dict:
        ram = parse_free(self._run_cmd("free -b"))
        cpu_pcts = parse_mpstat(self._run_cmd("mpstat 1 3"))
        load = parse_loadavg(self._run_cmd("cat /proc/loadavg"))
        cores = int(self._run_cmd("grep -c ^processor /proc/cpuinfo") or "1")
        disk = parse_df(self._run_cmd("df -B1 /"))
        disk_io = parse_iostat(self._run_cmd("iostat -x 1 3"))
        containers = parse_docker_stats(self._run_cmd("docker stats --no-stream --format '{{json .}}'"))
        ollama = parse_ollama_ps(self._run_cmd("ollama ps"))

        # Socket counts (spec: ss -s)
        self._run_cmd("ss -s 2>/dev/null || echo ''")

        # Docker inspect for container details
        for c in containers:
            inspect_json = self._run_cmd(f"docker inspect {c['name']} --format '{{{{json .State}}}}' 2>/dev/null || echo '{{}}'")
            try:
                state = json.loads(inspect_json)
                c["restart_count"] = state.get("RestartCount", 0)
                c["status"] = state.get("Status", "unknown")
            except (json.JSONDecodeError, ValueError):
                pass

        ao_ps = self._run_cmd("ps aux | grep '[c]laude' | grep -v grep")
        ao_pgrep = self._run_cmd("pgrep -a claude 2>/dev/null || echo ''")
        ao_workers = parse_ao_workers(ao_ps, ao_pgrep)

        embedding_mb = self._get_service_rss("embedding-proxy")
        caddy_mb = self._get_service_rss("caddy")
        signet_mb = self._get_service_rss("signet")

        used_mb = ram["used_gb"] * 1024
        container_ram = sum(c["mem_mb"] for c in containers)
        service_ram = embedding_mb + caddy_mb + signet_mb
        ollama_ram = sum(m["ram_mb"] for m in ollama["loaded_models"])
        overhead = compute_measured_overhead(used_mb, container_ram, service_ram, ao_workers["total_ram_mb"], ollama_ram)

        cpu = {
            "cores": cores, "load_1m": load["load_1m"], "load_5m": load["load_5m"],
            "steal_pct": cpu_pcts["steal_pct"], "iowait_pct": cpu_pcts["iowait_pct"], "usr_pct": cpu_pcts["usr_pct"],
        }
        disk["read_mbps"] = disk_io["read_mbps"]
        disk["write_mbps"] = disk_io["write_mbps"]

        return {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ram": {**ram, "overhead_gb": round(overhead / 1024, 2)},
            "cpu": cpu, "disk": disk, "containers": containers,
            "system_services": {"embedding_proxy_mb": embedding_mb, "caddy_mb": caddy_mb, "signet_mb": signet_mb, "measured_overhead_mb": round(overhead)},
            "ao_workers": ao_workers, "ollama": ollama, "tag": tag,
        }

    def _get_service_rss(self, name: str) -> int:
        output = self._run_cmd(f"ps -C {name} -o rss= 2>/dev/null || echo '0'")
        total_kb = 0
        for line in output.strip().split('\n'):
            line = line.strip()
            if line and line.isdigit():
                total_kb += int(line)
        return round(total_kb / 1024)

    def close(self):
        if self.ssh_client:
            self.ssh_client.close()
