"""Resource bottleneck analyzer for VPS simulations."""
from typing import Dict


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
