import pytest
from hardware_db import HardwareDB

def test_load_providers_json():
    """Load providers.json and verify schema."""
    db = HardwareDB("providers.json")
    assert "hetzner" in db.providers
    assert "cpx41" in db.providers["hetzner"]
    plan = db.providers["hetzner"]["cpx41"]
    assert plan["vcpu"] == 8
    assert plan["ram_gb"] == 16.0

def test_price_resolution_post_date():
    """Price jumps after price_change_date."""
    db = HardwareDB("providers.json")
    plan = db.providers["hetzner"]["cpx41"]
    # Mock today as 2026-04-05
    import datetime
    from unittest.mock import patch
    with patch('hardware_db.datetime') as mock_dt:
        mock_dt.datetime.now().date.return_value = datetime.date(2026, 4, 5)
        price = db.get_price("hetzner", "cpx41")
        assert price == plan["price_usd_post_date"]

def test_match_plans_filters_correctly():
    """Match plans to scenario requirements."""
    db = HardwareDB("providers.json")
    matches = db.match_plans(vcpu_min=8, ram_gb_min=16, disk_gb_min=200)
    assert any(m["provider"] == "hetzner" and m["plan"] == "cpx41" for m in matches)

def test_renewal_trap_flag():
    """Flag plans with >50% renewal cost delta."""
    db = HardwareDB("providers.json")
    plan = db.providers["hostinger"]["kvm4"]
    delta_pct = abs((plan["price_usd_renewal"] - plan["price_usd"]) / plan["price_usd"] * 100)
    assert delta_pct > 50, "KVM4 renewal trap should be >50%"
