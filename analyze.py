"""Bottleneck analysis, headroom decay, break-even, and migration planning."""
from datetime import datetime, date
from typing import Dict, Optional, List

try:
    from statistics import linear_regression
except ImportError:
    linear_regression = None

THRESHOLDS = {
    "ram":     [(70, "GREEN"), (85, "YELLOW"), (95, "RED"), (100, "CRITICAL")],
    "cpu":     [(60, "GREEN"), (75, "YELLOW"), (90, "RED"), (100, "CRITICAL")],
    "disk":    [(70, "GREEN"), (80, "YELLOW"), (90, "RED"), (100, "CRITICAL")],
    "disk_io": [(50, "GREEN"), (70, "YELLOW"), (85, "RED"), (100, "CRITICAL")],
}


class BottleneckAnalyzer:
    def identify(self, requirements: Dict, provider_plan: Dict) -> Dict:
        checks = {
            "ram": (requirements.get("ram_gb", 0), provider_plan.get("ram_gb", 1)),
            "cpu": (requirements.get("cpu_cores", 0), provider_plan.get("vcpu", 1)),
            "disk": (requirements.get("disk_gb", 0), provider_plan.get("disk_gb", 1)),
            "disk_io": (requirements.get("disk_io_mbps", 0), provider_plan.get("disk_io_max_mbps", 100)),
        }
        results = {}
        tiers_ranked = []
        for resource, (required, available) in checks.items():
            pct = (required / max(available, 0.01)) * 100
            tier = self._assign_tier(resource, pct)
            results[resource] = {"required": required, "available": available, "utilization_pct": round(pct, 1), "tier": tier}
            tier_rank = {"GREEN": 0, "YELLOW": 1, "RED": 2, "CRITICAL": 3}
            tiers_ranked.append((resource, tier_rank.get(tier, 3), pct))
        tiers_ranked.sort(key=lambda x: (-x[1], -x[2]))
        results["primary_bottleneck"] = tiers_ranked[0][0].upper() if tiers_ranked else None
        results["secondary_bottleneck"] = tiers_ranked[1][0].upper() if len(tiers_ranked) > 1 else None
        results["safe_resources"] = [r for r, rank, _ in tiers_ranked if rank == 0]
        worst = tiers_ranked[0] if tiers_ranked else None
        if worst:
            tier = results[worst[0]]["tier"]
            results["verdict"] = f"{tier} - {worst[0].upper()} is the primary constraint at {worst[2]:.0f}% utilization."
        else:
            results["verdict"] = "GREEN - all resources within safe margins."
        return results

    def _assign_tier(self, resource: str, pct: float) -> str:
        thresholds = THRESHOLDS.get(resource, THRESHOLDS["ram"])
        for ceiling, tier in thresholds:
            if pct <= ceiling:
                return tier
        return "CRITICAL"


class HeadroomDecayTracker:
    def __init__(self, baseline_db):
        self.db = baseline_db

    def analyze(self) -> Dict:
        baselines = self.db.get_baselines_since("2020-01-01T00:00:00Z")
        result = {}
        for resource, path, total_path in [("ram", "ram.used_gb", "ram.total_gb"), ("disk", "disk.used_gb", "disk.total_gb")]:
            result[resource] = self._analyze_resource(baselines, path, total_path, resource)
        result["cpu"] = {"days_to_yellow": None, "days_to_red": None, "days_to_critical": None,
                         "confidence": "low" if len(baselines) >= 3 else "none", "skipped": len(baselines) < 3}
        return result

    def _analyze_resource(self, baselines, used_path, total_path, resource):
        if len(baselines) < 3:
            return {"days_to_yellow": None, "days_to_red": None, "days_to_critical": None, "confidence": "none", "skipped": True}
        x_data, y_data = [], []
        first_ts = datetime.fromisoformat(baselines[0]["timestamp"].replace("Z", "+00:00"))
        for b in baselines:
            ts = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
            days = (ts - first_ts).total_seconds() / 86400
            x_data.append(days)
            value = self._get_nested(b["data"], used_path)
            if value is not None:
                y_data.append(value)
        if len(y_data) < 2 or linear_regression is None:
            return {"days_to_yellow": None, "days_to_red": None, "days_to_critical": None, "confidence": "none", "skipped": True}
        x_data = x_data[:len(y_data)]
        try:
            slope, intercept = linear_regression(x_data, y_data)
        except Exception:
            return {"days_to_yellow": None, "days_to_red": None, "days_to_critical": None, "confidence": "none", "skipped": True}
        if slope <= 0:
            return {"days_to_yellow": None, "days_to_red": None, "days_to_critical": None,
                    "confidence": self._confidence(baselines), "skipped": False, "growth_gb_per_day": 0,
                    "current_pct": self._current_pct(baselines, used_path, total_path)}
        total_gb = self._get_nested(baselines[-1]["data"], total_path) or 1
        current = y_data[-1]
        thresholds = THRESHOLDS.get(resource, THRESHOLDS["ram"])
        days_result = {}
        for ceiling, tier_name in thresholds:
            if tier_name == "GREEN":
                continue
            target_gb = total_gb * (ceiling / 100)
            if current < target_gb:
                days_result[f"days_to_{tier_name.lower()}"] = round(max(0, (target_gb - current) / slope), 1)
            else:
                days_result[f"days_to_{tier_name.lower()}"] = 0
        return {**days_result, "confidence": self._confidence(baselines), "skipped": False,
                "growth_gb_per_day": round(slope, 3), "current_pct": self._current_pct(baselines, used_path, total_path)}

    def _confidence(self, baselines):
        if len(baselines) < 3:
            return "none"
        first = datetime.fromisoformat(baselines[0]["timestamp"].replace("Z", "+00:00"))
        last = datetime.fromisoformat(baselines[-1]["timestamp"].replace("Z", "+00:00"))
        span = (last - first).total_seconds() / 86400
        if span > 30: return "high"
        elif span > 7: return "medium"
        return "low"

    def _current_pct(self, baselines, used_path, total_path):
        used = self._get_nested(baselines[-1]["data"], used_path) or 0
        total = self._get_nested(baselines[-1]["data"], total_path) or 1
        return round((used / total) * 100, 1)

    def _get_nested(self, data, path):
        for key in path.split("."):
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return None
        return data


class BreakEvenCalculator:
    def __init__(self, current_vps_usd, target_vps_usd, api_calls_per_day, avg_tokens_per_call,
                 local_model_handles_pct, api_cost_per_1k_tokens):
        self.current_vps_usd = current_vps_usd
        self.target_vps_usd = target_vps_usd
        self.api_calls_per_day = api_calls_per_day
        self.avg_tokens_per_call = avg_tokens_per_call
        self.local_model_handles_pct = local_model_handles_pct
        self.api_cost_per_1k_tokens = api_cost_per_1k_tokens

    def compute(self) -> Dict:
        upgrade_delta = self.target_vps_usd - self.current_vps_usd
        monthly_api_savings = (self.api_calls_per_day * 30 * self.avg_tokens_per_call / 1000) * self.api_cost_per_1k_tokens * self.local_model_handles_pct
        if monthly_api_savings <= 0:
            return {"break_even_months": None, "monthly_api_savings_usd": 0, "cumulative_savings_by_month": {}, "recommendation": "No API savings projected."}
        break_even = upgrade_delta / monthly_api_savings
        csm = {}
        for m in [1, 3, 6, 12]:
            csm[str(m)] = round((monthly_api_savings * m) - upgrade_delta, 2)
        if break_even <= 3: rec = f"Strong ROI. Break-even in {break_even:.1f} months."
        elif break_even <= 12: rec = f"Moderate ROI. Break-even in {break_even:.1f} months."
        else: rec = f"Weak ROI. Break-even in {break_even:.1f} months."
        return {"break_even_months": round(break_even, 1), "monthly_api_savings_usd": round(monthly_api_savings, 2),
                "cumulative_savings_by_month": csm, "recommendation": rec}


class MigrationPlanner:
    def generate(self, target_provider: str, target_plan: str) -> Dict:
        target = f"{target_provider}-{target_plan}"
        steps = [
            "Snapshot current Hostinger VPS",
            f"Provision {target} in same region as primary API endpoints",
            "rsync /docker to new host",
            "Copy /data/.agents workspace",
            "Update DNS / Caddy config",
            "Migrate Signet DB (baselines.db, signet.db)",
            "Bring up Docker stack on new host",
            "Smoke test: openclaw, zeroclaw, n8n, Signet, embedding-proxy",
            "Point Discord webhook to new host",
            "Decommission Hostinger after 48h monitoring window",
        ]
        urgency = ""
        if "hetzner" in target_provider.lower():
            urgency = "Hetzner CPX41 price increases ~30% on April 1 2026. Provision before then to lock current rate."
        return {"target": target, "estimated_downtime_minutes": 15, "steps": steps,
                "rollback": "Hostinger snapshot restore + DNS revert. ETA: 20min.", "urgency_note": urgency}
