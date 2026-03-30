import math
import yaml
from pathlib import Path
from typing import Dict, List, Optional

class Scenario:
    """Parsed scenario specification."""

    def __init__(self, data: Dict):
        self.name = data["name"]
        self.duration_hours = data["duration_hours"]
        self.description = data["description"]
        self.baseline_overlay = data["baseline_overlay"]
        self.ao_workers = data["ao_workers"]
        self.processes = data["processes"]
        self.disk_growth_mb = data["disk_growth_mb"]

class ScenarioLoader:
    """Load and validate scenario YAML files."""

    def load(self, path: str) -> Scenario:
        """Load a scenario YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return Scenario(data)

    def list_scenarios(self, dir_path: str) -> List[str]:
        """List all scenario files in directory."""
        return sorted([f.stem for f in Path(dir_path).glob("scenario-*.yaml")])


class ProjectionEngine:
    """Project resource requirements for a scenario."""

    def __init__(self, baseline: Dict):
        self.baseline = baseline

    def project_ram(self, scenario: Scenario) -> float:
        """Project total RAM needed (GB)."""
        baseline_used = self.baseline["ram"]["used_gb"]
        overlay_mb = scenario.baseline_overlay["ram_delta_mb"]
        ao_ram = scenario.ao_workers["count"] * scenario.ao_workers["ram_per_worker_mb"]
        process_ram = sum(p["count"] * p["ram_mb"] for p in scenario.processes)

        total_mb = (baseline_used * 1024) + overlay_mb + ao_ram + process_ram
        return round(total_mb / 1024, 2)

    def project_cpu(self, scenario: Scenario) -> int:
        """Project CPU cores needed."""
        baseline_pct = self.baseline["cpu"]["usr_pct"]
        overlay_pct = scenario.baseline_overlay["cpu_delta_pct"]
        ao_cpu = scenario.ao_workers["count"] * scenario.ao_workers["cpu_per_worker_pct"]
        process_cpu = sum(p["count"] * p["cpu_pct"] for p in scenario.processes)

        total_cpu_pct = baseline_pct + overlay_pct + ao_cpu + process_cpu
        # 80% target utilization per core
        required_cores = math.ceil(total_cpu_pct / 80.0)
        return max(required_cores, self.baseline["cpu"]["cores"])

    def project_disk(self, scenario: Scenario) -> float:
        """Project total disk needed (GB)."""
        baseline_used = self.baseline["disk"]["used_gb"]
        growth_gb = scenario.disk_growth_mb / 1024
        ao_disk = scenario.ao_workers["count"] * 0.2  # 200 MB per worker

        total_gb = baseline_used + growth_gb + ao_disk
        return round(total_gb, 1)
