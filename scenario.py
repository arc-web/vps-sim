# scenario.py
import sys
import math
import yaml
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

REQUIRED_PROCESS_FIELDS = {"name", "count", "ram_mb", "cpu_pct"}
KNOWN_PROCESS_FIELDS = {"name", "count", "ram_mb", "cpu_pct", "disk_io_mbps", "disk_storage_mb"}
REQUIRED_TOP_FIELDS = {"name", "description", "last_calibrated", "stale_after_days",
                       "concurrency", "add_processes", "add_load", "duration_minutes"}


class Scenario:
    """Parsed and validated scenario specification."""

    def __init__(self, data: Dict, source_path: str = ""):
        self.name = data["name"]
        self.description = data["description"]
        self.last_calibrated = data["last_calibrated"]
        self.stale_after_days = data["stale_after_days"]
        self.concurrency = data["concurrency"]
        self.add_processes = data["add_processes"]
        self.add_load = data.get("add_load", {})
        self.duration_minutes = data["duration_minutes"]
        self.source_path = source_path
        self._raw = data

    def is_stale(self, today: str = None) -> bool:
        """Check if last_calibrated is older than stale_after_days."""
        if today is None:
            today = date.today().isoformat()
        cal_date = date.fromisoformat(str(self.last_calibrated))
        check_date = date.fromisoformat(today)
        age_days = (check_date - cal_date).days
        return age_days > self.stale_after_days


class ScenarioLoader:
    """Load, validate, and list scenario YAML files."""

    def load(self, path: str) -> Scenario:
        """Load and validate a scenario YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        self._validate(data, path)
        return Scenario(data, source_path=path)

    def list_scenarios(self, dir_path: str) -> List[str]:
        """List all scenario file stems in directory."""
        return sorted([f.stem for f in Path(dir_path).glob("scenario-*.yaml")])

    def _validate(self, data: Dict, path: str):
        """Validate scenario YAML against spec requirements."""
        for field in REQUIRED_TOP_FIELDS:
            if field not in data:
                print(f"ERROR: {path}: missing required field '{field}'", file=sys.stderr)
                sys.exit(1)

        for i, proc in enumerate(data.get("add_processes", [])):
            for field in REQUIRED_PROCESS_FIELDS:
                if field not in proc:
                    print(f"ERROR: {path}: add_processes[{i}] missing required field '{field}'", file=sys.stderr)
                    sys.exit(1)

            if not isinstance(proc["count"], int):
                print(f"ERROR: {path}: add_processes[{i}].count must be int, got {type(proc['count']).__name__}", file=sys.stderr)
                sys.exit(1)
            if not isinstance(proc["ram_mb"], (int, float)):
                print(f"ERROR: {path}: add_processes[{i}].ram_mb must be numeric, got {type(proc['ram_mb']).__name__}", file=sys.stderr)
                sys.exit(1)

            unknown = set(proc.keys()) - KNOWN_PROCESS_FIELDS
            for field in unknown:
                print(f"WARNING: {path}: add_processes[{i}] has unknown field '{field}'", file=sys.stderr)

            if "disk_storage_mb" not in proc:
                proc["disk_storage_mb"] = 0
            if "disk_io_mbps" not in proc:
                proc["disk_io_mbps"] = 0


class ProjectionEngine:
    """Project resource requirements for a scenario against a baseline."""

    def __init__(self, baseline: Dict):
        self.baseline = baseline

    def project_ram(self, scenario: Scenario) -> float:
        """Spec formula: baseline.ram.used_gb + sum(process.ram_mb * count)/1024 + measured_overhead_mb/1024"""
        base_used = self.baseline["ram"]["used_gb"]
        process_ram_mb = sum(p["ram_mb"] * p["count"] for p in scenario.add_processes)
        overhead_mb = self.baseline["system_services"]["measured_overhead_mb"]
        total_gb = base_used + (process_ram_mb / 1024) + (overhead_mb / 1024)
        return round(total_gb, 2)

    def project_cpu(self, scenario: Scenario) -> int:
        """Spec formula: ceil((sum(process.cpu_pct * count) + baseline.cpu.usr_pct) / 80)"""
        base_cpu = self.baseline["cpu"]["usr_pct"]
        process_cpu = sum(p["cpu_pct"] * p["count"] for p in scenario.add_processes)
        total_demand = base_cpu + process_cpu
        required_cores = math.ceil(total_demand / 80.0)
        return required_cores

    def project_disk(self, scenario: Scenario) -> float:
        """Spec formula: baseline.disk.used_gb + ao_workers*0.2 + sum(disk_storage_mb * count)/1024"""
        base_used = self.baseline["disk"]["used_gb"]
        ao_worktree = scenario.concurrency.get("ao_workers", 0) * 0.2
        storage_mb = sum(p.get("disk_storage_mb", 0) * p["count"] for p in scenario.add_processes)
        total_gb = base_used + ao_worktree + (storage_mb / 1024)
        return round(total_gb, 1)

    def project_disk_io(self, scenario: Scenario) -> float:
        """Spec formula: sum(process.disk_io_mbps * count)"""
        return sum(p.get("disk_io_mbps", 0) * p["count"] for p in scenario.add_processes)

    def signet_queue_ms(self, scenario: Scenario) -> int:
        """Spec: signet_connections * 200. Flag if > 500."""
        connections = scenario.add_load.get("signet_connections", 0)
        return connections * 200

    def project_all(self, scenario: Scenario) -> Dict:
        """Run all projections, return structured dict."""
        queue_ms = self.signet_queue_ms(scenario)
        return {
            "ram_gb": self.project_ram(scenario),
            "cpu_cores": self.project_cpu(scenario),
            "disk_gb": self.project_disk(scenario),
            "disk_io_mbps": self.project_disk_io(scenario),
            "signet_queue_ms": queue_ms,
            "signet_bottleneck": queue_ms > 500,
            "scenario_stale": scenario.is_stale()
        }
