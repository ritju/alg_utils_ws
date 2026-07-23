"""Metrics export utilities for pandas DataFrame output."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Union

from ..models.metrics import MetricsRecord


class MetricsExporter:
    """Export metrics to various formats for pandas analysis."""

    @staticmethod
    def to_dataframe(records: list[MetricsRecord]):
        """Convert records to pandas DataFrame.

        Args:
            records: List of MetricsRecord objects.

        Returns:
            pandas.DataFrame with all metrics.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for DataFrame export. "
                "Install it with: pip install pandas"
            )

        data = [record.to_dict() for record in records]
        return pd.DataFrame(data)

    @staticmethod
    def to_csv(
        records: list[MetricsRecord],
        filepath: Union[str, Path],
        include_header: bool = True,
    ) -> None:
        """Export records to CSV file.

        Args:
            records: List of MetricsRecord objects.
            filepath: Output file path.
            include_header: Whether to include header row.
        """
        if not records:
            return

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = list(records[0].to_dict().keys())

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if include_header:
                writer.writeheader()
            for record in records:
                row = record.to_dict()
                # Convert datetime to ISO format string
                row["timestamp"] = row["timestamp"].isoformat()
                writer.writerow(row)

    @staticmethod
    def to_json(
        records: list[MetricsRecord],
        filepath: Union[str, Path],
        indent: int = 2,
    ) -> None:
        """Export records to JSON file.

        Args:
            records: List of MetricsRecord objects.
            filepath: Output file path.
            indent: JSON indentation level.
        """
        if not records:
            return

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        data = []
        for record in records:
            row = record.to_dict()
            row["timestamp"] = row["timestamp"].isoformat()
            data.append(row)

        with open(filepath, "w") as f:
            json.dump(data, f, indent=indent)

    @staticmethod
    def to_parquet(
        records: list[MetricsRecord],
        filepath: Union[str, Path],
    ) -> None:
        """Export records to Parquet file.

        Args:
            records: List of MetricsRecord objects.
            filepath: Output file path.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for Parquet export. "
                "Install it with: pip install pandas pyarrow"
            )

        df = MetricsExporter.to_dataframe(records)
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(filepath, index=False)

    @staticmethod
    def to_dict_list(records: list[MetricsRecord]) -> list[dict]:
        """Convert records to list of dictionaries.

        Args:
            records: List of MetricsRecord objects.

        Returns:
            List of dictionaries with all metrics.
        """
        return [record.to_dict() for record in records]

    @staticmethod
    def print_summary(records: list[MetricsRecord]) -> None:
        """Print a summary of the collected metrics.

        Args:
            records: List of MetricsRecord objects.
        """
        if not records:
            print("No records to summarize.")
            return

        print(f"\n{'='*60}")
        print("Metrics Summary")
        print(f"{'='*60}")
        print(f"Total samples: {len(records)}")
        print(f"Time range: {records[0].timestamp} - {records[-1].timestamp}")
        print(f"Container: {records[0].container_name} ({records[0].container_id})")

        # CPU stats
        cpu_values = [r.cpu_percent for r in records]
        print(f"\nCPU Usage (%):")
        print(f"  Min: {min(cpu_values):.2f}")
        print(f"  Max: {max(cpu_values):.2f}")
        print(f"  Avg: {sum(cpu_values)/len(cpu_values):.2f}")

        # Memory stats
        mem_values = [r.memory_usage_mb for r in records]
        print(f"\nMemory Usage (MB):")
        print(f"  Min: {min(mem_values):.2f}")
        print(f"  Max: {max(mem_values):.2f}")
        print(f"  Avg: {sum(mem_values)/len(mem_values):.2f}")
        print(f"  Limit: {records[0].memory_limit_mb:.2f}")

        # GPU stats (if available)
        if records[0].gpu_utilization is not None:
            gpu_values = [r.gpu_utilization for r in records if r.gpu_utilization is not None]
            if gpu_values:
                print(f"\nGPU Utilization (%):")
                print(f"  Min: {min(gpu_values):.2f}")
                print(f"  Max: {max(gpu_values):.2f}")
                print(f"  Avg: {sum(gpu_values)/len(gpu_values):.2f}")

            gpu_mem = [r.gpu_memory_used_mb for r in records if r.gpu_memory_used_mb is not None]
            if gpu_mem:
                print(f"\nGPU Memory (MB):")
                print(f"  Min: {min(gpu_mem):.2f}")
                print(f"  Max: {max(gpu_mem):.2f}")
                print(f"  Avg: {sum(gpu_mem)/len(gpu_mem):.2f}")

        print(f"{'='*60}\n")