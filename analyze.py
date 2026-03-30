"""Resource bottleneck analyzer for VPS simulations."""
from typing import Dict
from datetime import datetime
from statistics import linear_regression


class BottleneckAnalyzer:
    """Identify resource bottlenecks in scenario projections."""

    # Tier thresholds (utilization %)
    THRESHOLDS = {
        "GREEN": (0, 70),
        "YELLOW": (70, 85),
        "RED": (85, 95),
        "CRITICAL": (95, 100)
    }

    def identify(self, scenario_reqs: Dict, hardware_spec: Dict) -> Dict:
        """Identify bottlenecks by resource type.

        Args:
            scenario_reqs: Dict with keys: ram_gb, cpu_cores, disk_gb (required resources)
            hardware_spec: Dict with keys: ram_gb, cpu_cores, disk_gb (available resources)

        Returns:
            Dict mapping resource type to bottleneck analysis:
            {
                "ram_gb": {
                    "required": float,
                    "available": float,
                    "utilization_pct": float,
                    "tier": str
                },
                ...
            }
        """
        bottlenecks = {}

        for resource in ["ram_gb", "cpu_cores", "disk_gb"]:
            required = scenario_reqs.get(resource, 0)
            available = hardware_spec.get(resource, 0)

            # Handle division by zero
            if available > 0:
                utilization_pct = (required / available) * 100
            else:
                utilization_pct = 100

            bottlenecks[resource] = {
                "required": required,
                "available": available,
                "utilization_pct": round(utilization_pct, 1),
                "tier": self._assign_tier(utilization_pct / 100)
            }

        return bottlenecks

    def _assign_tier(self, utilization: float) -> str:
        """Map utilization (0.0-1.0 range) to tier.

        Args:
            utilization: Value between 0.0 and 1.0 (or higher for over-subscribed)

        Returns:
            Tier name: "GREEN", "YELLOW", "RED", or "CRITICAL"
        """
        pct = utilization * 100

        # Check against thresholds
        for tier, (low, high) in self.THRESHOLDS.items():
            if low <= pct < high:
                return tier

        # If utilization >= 100% or above the highest threshold
        return "CRITICAL"


class HeadroomDecayTracker:
    """Track headroom decline and predict exhaustion."""

    def __init__(self, baseline_db):
        self.db = baseline_db

    def estimate_days_to_full(self, resource: str = "ram", threshold_pct: float = 95.0) -> float:
        """Estimate days until resource exhaustion.

        Args:
            resource: Resource type to analyze ("ram")
            threshold_pct: Utilization percentage threshold (0-100)

        Returns:
            Days until threshold is reached, or None if insufficient data
        """
        baselines = self.db.get_baselines_since("2020-01-01T00:00:00Z")

        if len(baselines) < 3:
            return None  # Insufficient data

        # Extract resource usage over time
        x_data = []  # Days since first baseline
        y_data = []  # Resource usage

        first_ts = datetime.fromisoformat(baselines[0]["timestamp"].replace("Z", "+00:00"))

        for baseline in baselines:
            ts = datetime.fromisoformat(baseline["timestamp"].replace("Z", "+00:00"))
            days_since = (ts - first_ts).days
            x_data.append(days_since)

            if resource == "ram":
                y_data.append(baseline["data"]["ram"]["used_gb"])

        if len(x_data) < 2:
            return None

        try:
            # Linear regression: slope (GB/day)
            slope, intercept = linear_regression(x_data, y_data)

            # Total RAM (assume baseline is current hardware)
            total_gb = baselines[-1]["data"]["ram"]["total_gb"]
            current_used = baselines[-1]["data"]["ram"]["used_gb"]

            # Days until threshold
            threshold_gb = total_gb * (threshold_pct / 100)
            if slope <= 0:
                return None  # No growth

            days_to_threshold = (threshold_gb - current_used) / slope
            return max(0, round(days_to_threshold, 1))
        except:
            return None
