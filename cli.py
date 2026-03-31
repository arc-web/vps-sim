#!/usr/bin/env python3
"""VPS capacity planning simulator - CLI entry point with 7 subcommands."""
import argparse
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from config_loader import load_config
from collect import MetricsCollector
from db import BaselineDB
from scenario import ScenarioLoader, ProjectionEngine
from hardware_db import HardwareDB
from analyze import BottleneckAnalyzer, HeadroomDecayTracker, BreakEvenCalculator, MigrationPlanner
from report import ReportBuilder
from calibrate import Calibrator


def main():
    parser = argparse.ArgumentParser(description="VPS capacity planning simulator")
    sub = parser.add_subparsers(dest="command", help="Commands")

    # collect
    p_collect = sub.add_parser("collect", help="Collect baseline metrics from VPS")
    p_collect.add_argument("--local", action="store_true", help="Subprocess mode (on VPS)")
    p_collect.add_argument("--print", dest="print_json", action="store_true", help="Print JSON to stdout")
    p_collect.add_argument("--tag", default=None, help="Label for this collection")
    p_collect.add_argument("--db", default="baselines.db", help="Database path")

    # scenario
    p_scenario = sub.add_parser("scenario", help="Project resource requirements")
    p_scenario.add_argument("--name", help="Scenario name (without path)")
    p_scenario.add_argument("--all", dest="all_scenarios", action="store_true", help="Project all scenarios")
    p_scenario.add_argument("--db", default="baselines.db")

    # calibrate
    p_cal = sub.add_parser("calibrate", help="Measure running processes")
    p_cal.add_argument("--process", help="Process name to measure")
    p_cal.add_argument("--scenario", help="Scenario name to calibrate all processes")
    p_cal.add_argument("--duration", type=int, default=30, help="Sample duration (seconds)")
    p_cal.add_argument("--local", action="store_true")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Bottleneck analysis + decay + break-even")
    p_analyze.add_argument("--scenario", required=True, help="Scenario name")
    p_analyze.add_argument("--json", dest="json_output", action="store_true", help="JSON output")
    p_analyze.add_argument("--db", default="baselines.db")
    p_analyze.add_argument("--target-cost", type=float, help="Target VPS cost (overrides provider price)")

    # migrate
    p_migrate = sub.add_parser("migrate", help="Migration checklist")
    p_migrate.add_argument("--to", required=True, dest="target", help="Target plan (e.g. hetzner-cpx41)")

    # report
    p_report = sub.add_parser("report", help="Generate HTML/JSON report")
    p_report.add_argument("--scenario", help="Single scenario name")
    p_report.add_argument("--all-scenarios", action="store_true")
    p_report.add_argument("--json", dest="json_only", action="store_true", help="JSON only")
    p_report.add_argument("--summary", action="store_true", help="5-line terminal summary")
    p_report.add_argument("--db", default="baselines.db")

    # compare
    p_compare = sub.add_parser("compare", help="Provider comparison table")
    p_compare.add_argument("--all-scenarios", action="store_true")
    p_compare.add_argument("--db", default="baselines.db")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config("config.yaml")

    handlers = {
        "collect": _handle_collect, "scenario": _handle_scenario,
        "calibrate": _handle_calibrate, "analyze": _handle_analyze,
        "migrate": _handle_migrate, "report": _handle_report, "compare": _handle_compare,
    }
    handlers[args.command](args, config)


def _handle_collect(args, config):
    mode = "subprocess" if args.local else "ssh"
    try:
        collector = MetricsCollector(
            mode=mode, host=config["vps"]["ssh_host"],
            user=config["vps"]["ssh_user"], key=config["vps"]["ssh_key"],
            timeout=config["vps"].get("ssh_timeout_seconds", 10),
        )
    except Exception as e:
        print(f"ERROR: Collection failed - {e}", file=sys.stderr)
        sys.exit(1)

    baseline = collector.collect(tag=args.tag)
    collector.close()

    db = BaselineDB(args.db)
    db.create_tables()
    db.insert_baseline(baseline, tag=args.tag)

    if args.print_json:
        print(json.dumps(baseline, indent=2))
    else:
        print(f"Collected: {baseline['timestamp']} (tag: {args.tag or 'none'})")


def _handle_scenario(args, config):
    db = BaselineDB(args.db)
    latest = db.get_latest_baseline()
    if not latest:
        print("ERROR: No baselines in database. Run collect first.", file=sys.stderr)
        sys.exit(1)

    baseline = latest["data"]
    loader = ScenarioLoader()
    engine = ProjectionEngine(baseline)

    if args.all_scenarios:
        names = loader.list_scenarios("scenarios/")
        paths = [f"scenarios/{n}.yaml" for n in names]
    elif args.name:
        paths = glob.glob(f"scenarios/scenario-*{args.name}*.yaml") or [f"scenarios/{args.name}.yaml"]
    else:
        print("ERROR: --name or --all required", file=sys.stderr)
        sys.exit(1)

    for path in paths:
        scenario = loader.load(path)
        result = engine.project_all(scenario)
        print(f"\n--- {scenario.name} ---")
        print(f"RAM: {result['ram_gb']} GB | CPU: {result['cpu_cores']} cores | Disk: {result['disk_gb']} GB")
        if result["signet_bottleneck"]:
            print(f"WARNING: Signet bottleneck - {result['signet_queue_ms']}ms queue latency")
        if result["scenario_stale"]:
            print("WARNING: Scenario data is stale (last_calibrated > stale_after_days)")


def _handle_calibrate(args, config):
    mode = "subprocess" if args.local else "ssh"
    cal = Calibrator(
        mode=mode, host=config["vps"]["ssh_host"],
        user=config["vps"]["ssh_user"], key=config["vps"]["ssh_key"],
    )

    if args.scenario:
        paths = glob.glob(f"scenarios/scenario-*{args.scenario}*.yaml")
        if not paths:
            print(f"ERROR: No scenario matching '{args.scenario}'", file=sys.stderr)
            sys.exit(1)
        cal.calibrate_scenario(paths[0], duration=args.duration)
        print(f"Calibrated: {paths[0]}")
    elif args.process:
        result = cal.measure_process(args.process, duration=args.duration)
        print(json.dumps(result, indent=2))
    else:
        print("ERROR: --process or --scenario required", file=sys.stderr)
        sys.exit(1)
    cal.close()


def _handle_analyze(args, config):
    db = BaselineDB(args.db)
    latest = db.get_latest_baseline()
    if not latest:
        print("ERROR: No baselines. Run collect first.", file=sys.stderr)
        sys.exit(1)

    baseline = latest["data"]
    loader = ScenarioLoader()

    paths = glob.glob(f"scenarios/scenario-*{args.scenario}*.yaml")
    if not paths:
        print(f"ERROR: No scenario matching '{args.scenario}'", file=sys.stderr)
        sys.exit(1)

    scenario = loader.load(paths[0])
    engine = ProjectionEngine(baseline)
    requirements = engine.project_all(scenario)

    hw_db = HardwareDB("providers.json")
    matched = hw_db.match_plans(
        vcpu_min=requirements["cpu_cores"],
        ram_gb_min=requirements["ram_gb"],
        disk_gb_min=requirements["disk_gb"],
    )

    analyzer = BottleneckAnalyzer()
    if matched:
        top = matched[0]
        plan_spec = hw_db.providers[top["provider"]][top["plan"]]
        plan_spec["disk_io_max_mbps"] = 100
        bottlenecks = analyzer.identify(requirements, plan_spec)
    else:
        bottlenecks = {"verdict": "No matching plans found."}

    decay_tracker = HeadroomDecayTracker(db)
    decay = decay_tracker.analyze()

    costs = config.get("costs", {})
    target_cost = args.target_cost
    if not target_cost and matched:
        target_cost = matched[0]["price"]

    break_even = {}
    if target_cost:
        be_calc = BreakEvenCalculator(
            current_vps_usd=costs.get("current_vps_usd", 14.99),
            target_vps_usd=target_cost,
            api_calls_per_day=costs.get("api_calls_per_day", 200),
            avg_tokens_per_call=costs.get("avg_tokens_per_call", 800),
            local_model_handles_pct=costs.get("local_model_handles_pct", 0.40),
            api_cost_per_1k_tokens=costs.get("api_cost_per_1k_tokens", 0.003),
        )
        break_even = be_calc.compute()

    output = {
        "scenario": scenario.name, "requirements": requirements,
        "bottlenecks": bottlenecks, "headroom_decay": decay, "break_even": break_even,
    }

    if args.json_output:
        print(json.dumps(output, indent=2))
    else:
        print(f"\n--- Analysis: {scenario.name} ---")
        print(f"Requirements: RAM {requirements['ram_gb']}GB | CPU {requirements['cpu_cores']} cores | Disk {requirements['disk_gb']}GB")
        print(f"Bottleneck: {bottlenecks.get('verdict', 'N/A')}")
        if break_even:
            print(f"Break-even: {break_even.get('break_even_months', 'N/A')} months")


def _handle_migrate(args, config):
    parts = args.target.split("-", 1)
    if len(parts) != 2:
        print("ERROR: --to format is 'provider-plan' (e.g. hetzner-cpx41)", file=sys.stderr)
        sys.exit(1)
    provider, plan = parts
    planner = MigrationPlanner()
    result = planner.generate(target_provider=provider, target_plan=plan)
    print(json.dumps(result, indent=2))


def _handle_report(args, config):
    db = BaselineDB(args.db)
    latest = db.get_latest_baseline()
    if not latest:
        print("ERROR: No baselines. Run collect first.", file=sys.stderr)
        sys.exit(1)

    baseline = latest["data"]
    loader = ScenarioLoader()
    engine = ProjectionEngine(baseline)
    hw_db = HardwareDB("providers.json")
    analyzer = BottleneckAnalyzer()

    if args.all_scenarios:
        names = loader.list_scenarios("scenarios/")
        paths = [f"scenarios/{n}.yaml" for n in names]
    elif args.scenario:
        paths = glob.glob(f"scenarios/scenario-*{args.scenario}*.yaml")
    else:
        print("ERROR: --scenario or --all-scenarios required", file=sys.stderr)
        sys.exit(1)

    scenarios_data = {}
    all_matched = []
    for path in paths:
        scenario = loader.load(path)
        reqs = engine.project_all(scenario)
        matched = hw_db.match_plans(reqs["cpu_cores"], reqs["ram_gb"], reqs["disk_gb"])
        if matched:
            top = matched[0]
            plan_spec = hw_db.providers[top["provider"]][top["plan"]]
            plan_spec["disk_io_max_mbps"] = 100
            bn = analyzer.identify(reqs, plan_spec)
        else:
            bn = {"verdict": "No plans found"}
        scenarios_data[scenario.name] = {"requirements": reqs, "bottlenecks": bn}
        all_matched.extend(matched)

    seen = set()
    unique_matched = []
    for m in all_matched:
        key = f"{m['provider']}-{m['plan']}"
        if key not in seen:
            seen.add(key)
            unique_matched.append(m)

    profiles = {}
    for provider, plans in hw_db.providers.items():
        profiles[provider] = {}
        for pname, pdata in plans.items():
            profiles[provider][pname] = {
                "overview": pdata.get("overview", ""),
                "pros": pdata.get("pros", []),
                "cons": pdata.get("cons", []),
                "risks": pdata.get("risks", []),
                "opportunities": pdata.get("opportunities", []),
            }

    decay_tracker = HeadroomDecayTracker(db)
    decay = decay_tracker.analyze()

    costs = config.get("costs", {})
    target_cost = unique_matched[0]["price"] if unique_matched else None
    break_even = {}
    if target_cost:
        be_calc = BreakEvenCalculator(
            current_vps_usd=costs.get("current_vps_usd", 14.99),
            target_vps_usd=target_cost,
            api_calls_per_day=costs.get("api_calls_per_day", 200),
            avg_tokens_per_call=costs.get("avg_tokens_per_call", 800),
            local_model_handles_pct=costs.get("local_model_handles_pct", 0.40),
            api_cost_per_1k_tokens=costs.get("api_cost_per_1k_tokens", 0.003),
        )
        break_even = be_calc.compute()

    age = db.baseline_age_minutes()
    stale = (age or 999) > 20

    urgent = []
    if stale:
        urgent.append("baseline_stale - last collection > 20 minutes ago")
    for name, sd in scenarios_data.items():
        bn = sd.get("bottlenecks", {})
        primary = bn.get("primary_bottleneck", "").lower()
        if primary and bn.get(primary, {}).get("tier") == "CRITICAL":
            urgent.append(f"{name}: CRITICAL resource exhaustion on {primary.upper()}")

    report_data = {
        "urgent_flags": urgent,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "baseline_age_minutes": age, "baseline_stale": stale,
        "baseline": baseline, "scenarios": scenarios_data,
        "provider_profiles": profiles, "matched_plans": unique_matched,
        "headroom_decay": decay, "break_even": break_even,
        "top_recommendation": {"provider": unique_matched[0]["provider"], "plan": unique_matched[0]["plan"],
                               "reason": "Best price-to-performance match."} if unique_matched else {},
    }

    builder = ReportBuilder()

    if args.summary:
        print(f"Baseline: {'STALE' if stale else 'fresh'} ({age or '?'}min)")
        print(f"Scenarios: {len(scenarios_data)}")
        if unique_matched:
            print(f"Top match: {unique_matched[0]['provider']}/{unique_matched[0]['plan']} ${unique_matched[0]['price']:.2f}")
        if break_even:
            print(f"Break-even: {break_even.get('break_even_months', 'N/A')} months")
        print(f"Urgent: {len(urgent)} flags")
        return

    if args.json_only:
        print(builder.to_json(report_data))
        return

    html = builder.to_html(report_data)
    output_dir = Path(config.get("reports", {}).get("output_dir", "reports"))
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    html_path = output_dir / f"vps-sim-{ts}.html"
    json_path = output_dir / f"vps-sim-{ts}.json"

    html_path.write_text(html)
    json_path.write_text(builder.to_json(report_data))

    caddy_base = config.get("reports", {}).get("caddy_base_url", "")
    if caddy_base:
        print(f"{caddy_base}/{html_path.name}")
    else:
        print(f"Report: {html_path}")


def _handle_compare(args, config):
    db = BaselineDB(args.db)
    latest = db.get_latest_baseline()
    if not latest:
        print("ERROR: No baselines.", file=sys.stderr)
        sys.exit(1)

    baseline = latest["data"]
    loader = ScenarioLoader()
    engine = ProjectionEngine(baseline)
    hw_db = HardwareDB("providers.json")

    names = loader.list_scenarios("scenarios/")
    print(f"{'Scenario':<30} {'RAM GB':<10} {'CPU':<6} {'Disk GB':<10} {'Top Match':<25} {'Price':<10}")
    print("-" * 91)
    for name in names:
        scenario = loader.load(f"scenarios/{name}.yaml")
        reqs = engine.project_all(scenario)
        matched = hw_db.match_plans(reqs["cpu_cores"], reqs["ram_gb"], reqs["disk_gb"])
        top = f"{matched[0]['provider']}/{matched[0]['plan']}" if matched else "none"
        price = f"${matched[0]['price']:.2f}" if matched else "-"
        print(f"{scenario.name:<30} {reqs['ram_gb']:<10} {reqs['cpu_cores']:<6} {reqs['disk_gb']:<10} {top:<25} {price:<10}")


if __name__ == "__main__":
    main()
