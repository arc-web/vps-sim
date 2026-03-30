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
