"""CLI router for vps-sim - main entry point."""
import argparse
import sys
from pathlib import Path

from config_loader import load_config
from collect import MetricsCollector
from db import BaselineDB
from scenario import ScenarioLoader, ProjectionEngine
from hardware_db import HardwareDB
from analyze import BottleneckAnalyzer, BreakEvenCalculator, MigrationPlanner
from report import ReportBuilder


def main():
    """Main CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        description="VPS capacity planning simulator"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # collect command
    collect_parser = subparsers.add_parser("collect", help="Collect baseline metrics")
    collect_parser.add_argument(
        "--tag", default=None, help="Tag for this collection"
    )
    collect_parser.add_argument(
        "--local",
        action="store_true",
        help="Use subprocess mode (VPS-local)"
    )
    collect_parser.add_argument(
        "--db", default="baselines.db", help="Database path"
    )

    # simulate command
    sim_parser = subparsers.add_parser("simulate", help="Run scenario simulation")
    sim_parser.add_argument("scenario", help="Scenario name or path")
    sim_parser.add_argument(
        "--baseline", default="latest", help="Baseline tag or 'latest'"
    )
    sim_parser.add_argument(
        "--output", default="report.html", help="Output report path"
    )
    sim_parser.add_argument(
        "--db", default="baselines.db", help="Database path"
    )

    args = parser.parse_args()

    if args.command == "collect":
        handle_collect(args)
    elif args.command == "simulate":
        handle_simulate(args)
    else:
        parser.print_help()


def handle_collect(args):
    """Handle collect subcommand."""
    config = load_config("config.yaml")

    mode = "subprocess" if args.local else "ssh"
    collector = MetricsCollector(
        mode=mode,
        host=config["vps"]["ssh_host"],
        user=config["vps"]["ssh_user"],
        key=config["vps"]["ssh_key"],
        timeout=config["vps"]["ssh_timeout_seconds"]
    )

    try:
        baseline = collector.collect(tag=args.tag)

        db = BaselineDB(args.db)
        db.create_tables()
        db.insert_baseline(baseline, tag=args.tag)
        print(f"Baseline collected: {baseline['timestamp']}")
    finally:
        collector.close()


def handle_simulate(args):
    """Handle simulate subcommand."""
    db = BaselineDB(args.db)

    # Get baseline
    baseline_record = db.get_latest_baseline()
    if not baseline_record:
        print("Error: No baseline found in database", file=sys.stderr)
        sys.exit(1)
    baseline = baseline_record["data"]

    # Load scenario
    scenario_loader = ScenarioLoader()
    try:
        scenario = scenario_loader.load(args.scenario)
    except FileNotFoundError:
        print(f"Error: Scenario file not found: {args.scenario}", file=sys.stderr)
        sys.exit(1)

    # Project requirements
    engine = ProjectionEngine(baseline)
    requirements = {
        "ram_gb": engine.project_ram(scenario),
        "cpu_cores": engine.project_cpu(scenario),
        "disk_gb": engine.project_disk(scenario)
    }

    # Match hardware plans
    hw_db = HardwareDB("providers.json")
    matched_plans = hw_db.match_plans(
        vcpu_min=requirements["cpu_cores"],
        ram_gb_min=requirements["ram_gb"],
        disk_gb_min=int(requirements["disk_gb"])
    )

    # Analyze bottlenecks
    analyzer = BottleneckAnalyzer()
    current_hw = baseline.get("hardware", {
        "ram_gb": 7.8,
        "cpu_cores": 2,
        "disk_gb": 96
    })
    bottlenecks = analyzer.identify(requirements, current_hw)

    # Generate migration plan
    planner = MigrationPlanner()
    migration = planner.generate(bottlenecks)

    # Build report
    report_data = {
        "scenario": scenario.name,
        "requirements": requirements,
        "matched_plans": matched_plans,
        "bottlenecks": bottlenecks,
        "migration": migration
    }

    builder = ReportBuilder()
    html = builder.to_html(report_data)

    output_path = Path(args.output)
    output_path.write_text(html)
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
