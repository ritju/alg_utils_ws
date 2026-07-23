"""Command-line interface for ROS Performance Monitor."""

import argparse
import signal
import sys
from pathlib import Path
from typing import Optional

from .monitor import MetricsCollector
from .output import MetricsExporter


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="ros-perf-mon",
        description="Monitor ROS C++ nodes in Docker containers for CPU, GPU, and memory usage.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Monitor command
    monitor_parser = subparsers.add_parser(
        "monitor", help="Monitor specified containers"
    )
    monitor_parser.add_argument(
        "containers",
        nargs="+",
        help="Container names or IDs to monitor",
    )
    monitor_parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=1.0,
        help="Sampling interval in seconds (default: 1.0)",
    )
    monitor_parser.add_argument(
        "-d",
        "--duration",
        type=float,
        default=None,
        help="Total monitoring duration in seconds (default: infinite)",
    )
    monitor_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output file path (supports .csv, .json, .parquet)",
    )
    monitor_parser.add_argument(
        "-f",
        "--format",
        choices=["csv", "json", "parquet", "dataframe"],
        default="csv",
        help="Output format (default: csv)",
    )
    monitor_parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary after monitoring",
    )

    # List command
    list_parser = subparsers.add_parser(
        "list", help="List available containers"
    )
    list_parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        dest="all_containers",
        help="Include stopped containers",
    )

    # Single sample command
    sample_parser = subparsers.add_parser(
        "sample", help="Take a single sample of container metrics"
    )
    sample_parser.add_argument(
        "containers",
        nargs="+",
        help="Container names or IDs to sample",
    )
    sample_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output file path",
    )
    sample_parser.add_argument(
        "-f",
        "--format",
        choices=["csv", "json", "parquet"],
        default="csv",
        help="Output format (default: csv)",
    )

    return parser


def handle_list(args: argparse.Namespace) -> int:
    """Handle list command."""
    collector = MetricsCollector()
    try:
        containers = collector.list_containers(all_containers=args.all_containers)
        if containers:
            print("Available containers:")
            for name in containers:
                print(f"  - {name}")
        else:
            print("No containers found.")
        return 0
    finally:
        collector.close()


def handle_sample(args: argparse.Namespace) -> int:
    """Handle sample command."""
    collector = MetricsCollector()
    try:
        records = collector.collect_batch(args.containers)

        if not records:
            print("Error: No containers found with the specified names.", file=sys.stderr)
            return 1

        # Output results
        if args.output:
            output_path = Path(args.output)
            if args.format == "csv":
                MetricsExporter.to_csv(records, output_path)
            elif args.format == "json":
                MetricsExporter.to_json(records, output_path)
            elif args.format == "parquet":
                MetricsExporter.to_parquet(records, output_path)
            print(f"Results saved to {output_path}")
        else:
            # Print to stdout
            MetricsExporter.print_summary(records)
            for record in records:
                print(record.to_dict())

        return 0
    finally:
        collector.close()


def handle_monitor(args: argparse.Namespace) -> int:
    """Handle monitor command."""
    collector = MetricsCollector()
    records = []
    interrupted = False

    def signal_handler(sig, frame):
        nonlocal interrupted
        interrupted = True
        print("\nStopping monitoring...")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        print(f"Monitoring containers: {', '.join(args.containers)}")
        print(f"Interval: {args.interval}s")
        if args.duration:
            print(f"Duration: {args.duration}s")
        print("Press Ctrl+C to stop...\n")

        # Monitor first container continuously
        container = args.containers[0]
        generator = collector.collect_continuous(
            container,
            interval=args.interval,
            duration=args.duration,
        )

        for record in generator:
            if interrupted:
                break

            records.append(record)

            # Print live update
            gpu_info = ""
            if record.gpu_utilization is not None:
                gpu_info = f" | GPU: {record.gpu_utilization:.1f}% ({record.gpu_memory_used_mb:.0f}/{record.gpu_memory_total_mb:.0f} MB)"

            print(
                f"[{record.timestamp.strftime('%H:%M:%S')}] "
                f"CPU: {record.cpu_percent:.1f}% | "
                f"Mem: {record.memory_usage_mb:.0f}/{record.memory_limit_mb:.0f} MB ({record.memory_percent:.1f}%)"
                f"{gpu_info}"
            )

        # Collect final samples for other containers
        if len(args.containers) > 1:
            for container in args.containers[1:]:
                record = collector.collect(container)
                if record:
                    records.append(record)

        # Output results
        if args.output and records:
            output_path = Path(args.output)
            if args.format == "csv":
                MetricsExporter.to_csv(records, output_path)
            elif args.format == "json":
                MetricsExporter.to_json(records, output_path)
            elif args.format == "parquet":
                MetricsExporter.to_parquet(records, output_path)
            print(f"\nResults saved to {output_path}")

        if args.summary and records:
            MetricsExporter.print_summary(records)

        return 0

    finally:
        collector.close()


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.command is None:
        parser.print_help()
        return 0

    if parsed_args.command == "list":
        return handle_list(parsed_args)
    elif parsed_args.command == "sample":
        return handle_sample(parsed_args)
    elif parsed_args.command == "monitor":
        return handle_monitor(parsed_args)

    return 0


if __name__ == "__main__":
    sys.exit(main())