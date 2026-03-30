import subprocess
import re
import yaml
from typing import Dict, Optional


class ProcessMeasurer:
    """Measure real running process resource usage."""

    def measure(self, pattern: str) -> Dict:
        """Find processes matching pattern and measure their total RAM/CPU."""
        try:
            # Get all pids matching pattern
            ps_output = subprocess.run(
                f"ps aux | grep '{pattern}' | grep -v grep",
                shell=True, capture_output=True, text=True
            ).stdout.strip()

            if not ps_output:
                return {"pattern": pattern, "count": 0, "total_rss_mb": 0, "avg_cpu_pct": 0}

            pids = []
            total_rss_mb = 0
            total_cpu = 0.0

            for line in ps_output.split('\n'):
                parts = line.split()
                if len(parts) >= 6:
                    pid = parts[1]
                    cpu = float(parts[2])
                    rss_kb = int(parts[5])
                    pids.append(pid)
                    total_rss_mb += rss_kb / 1024
                    total_cpu += cpu

            return {
                "pattern": pattern,
                "count": len(pids),
                "total_rss_mb": round(total_rss_mb, 1),
                "avg_cpu_pct": round(total_cpu / max(len(pids), 1), 1)
            }
        except Exception as e:
            return {"pattern": pattern, "count": 0, "total_rss_mb": 0, "avg_cpu_pct": 0, "error": str(e)}

    def write_yaml(self, path: str, data: Dict) -> None:
        """Write calibration data to YAML file."""
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
