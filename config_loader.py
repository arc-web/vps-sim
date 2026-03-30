"""Configuration loader for vps-sim."""
import yaml


def load_config(path: str = "config.yaml") -> dict:
    """Load and validate config.yaml.

    Args:
        path: Path to config.yaml file

    Returns:
        Parsed YAML configuration dict
    """
    with open(path) as f:
        return yaml.safe_load(f)
