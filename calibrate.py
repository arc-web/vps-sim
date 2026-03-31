"""Measure running processes and write calibration data back to scenario YAML."""
import subprocess
import yaml
import sys
from datetime import date
from typing import Dict, Optional

try:
    import paramiko
except ImportError:
    paramiko = None


class Calibrator:
    def __init__(self, mode: str = "subprocess", host: str = None, user: str = None,
                 key: str = None, timeout: int = 10):
        self.mode = mode
        self.ssh_client = None
        if mode == "ssh" and paramiko:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(hostname=host, username=user, key_filename=key, timeout=timeout)

    def _run_cmd(self, cmd: str) -> str:
        if self.mode == "ssh" and self.ssh_client:
            _, stdout, _ = self.ssh_client.exec_command(cmd, timeout=30)
            return stdout.read().decode().strip()
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()

    def measure_process(self, name: str, duration: int = 30) -> Dict:
        output = self._run_cmd(f"ps aux | grep '[{name[0]}]{name[1:]}' 2>/dev/null")
        if not output.strip():
            return {"name": name, "count": 0, "total_ram_mb": 0, "avg_ram_mb": 0, "avg_cpu_pct": 0}
        count = 0
        total_rss_kb = 0
        total_cpu = 0.0
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 6:
                count += 1
                total_cpu += float(parts[2])
                total_rss_kb += int(parts[5])
        total_ram_mb = round(total_rss_kb / 1024, 1)
        return {
            "name": name, "count": count, "total_ram_mb": total_ram_mb,
            "avg_ram_mb": round(total_ram_mb / max(count, 1), 1),
            "avg_cpu_pct": round(total_cpu / max(count, 1), 1),
        }

    def writeback(self, yaml_path: str, process_name: str, ram_mb: float, cpu_pct: float):
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        for proc in data.get("add_processes", []):
            if proc["name"] == process_name:
                proc["ram_mb"] = ram_mb
                proc["cpu_pct"] = cpu_pct
        data["last_calibrated"] = date.today().isoformat()
        with open(yaml_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def calibrate_scenario(self, yaml_path: str, duration: int = 30):
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        for proc in data.get("add_processes", []):
            result = self.measure_process(proc["name"], duration)
            if result["count"] > 0:
                self.writeback(yaml_path, proc["name"], result["avg_ram_mb"], result["avg_cpu_pct"])
            else:
                print(f"WARNING: No running processes found for '{proc['name']}'. Skipping.", file=sys.stderr)

    def close(self):
        if self.ssh_client:
            self.ssh_client.close()
