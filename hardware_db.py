import json
from datetime import datetime
from typing import List, Dict, Any

class HardwareDB:
    """Load and query VPS provider hardware database."""

    def __init__(self, providers_path: str = "providers.json"):
        with open(providers_path) as f:
            self.providers = json.load(f)

    def get_price(self, provider: str, plan: str, today: str = None) -> float:
        """Get current price for a plan, accounting for price_change_date."""
        if today is None:
            today = datetime.now().date().isoformat()

        p = self.providers[provider][plan]
        if p.get("price_change_date") and today >= p["price_change_date"]:
            return p.get("price_usd_post_date") or p["price_usd"]
        return p["price_usd"]

    def match_plans(self, vcpu_min: int, ram_gb_min: float, disk_gb_min: int) -> List[Dict]:
        """Find plans matching minimum requirements, ranked by price."""
        matches = []
        for provider, plans in self.providers.items():
            for plan_name, spec in plans.items():
                if (spec["vcpu"] >= vcpu_min and
                    spec["ram_gb"] >= ram_gb_min and
                    spec["disk_gb"] >= disk_gb_min):
                    matches.append({
                        "provider": provider,
                        "plan": plan_name,
                        "vcpu": spec["vcpu"],
                        "ram_gb": spec["ram_gb"],
                        "price": self.get_price(provider, plan_name),
                        "cpu_steal_risk": spec.get("cpu_steal_risk"),
                        "renewal_trap": self._check_renewal_trap(spec)
                    })
        return sorted(matches, key=lambda x: x["price"])

    def _check_renewal_trap(self, plan: Dict) -> bool:
        """Flag if renewal price > 50% higher than intro."""
        if plan["price_usd_renewal"] is None:
            return False
        delta = abs((plan["price_usd_renewal"] - plan["price_usd"]) / plan["price_usd"])
        return delta > 0.50
