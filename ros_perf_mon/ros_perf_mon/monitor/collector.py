"""Metrics collector that aggregates Docker and GPU metrics."""

import time
from datetime import datetime
from typing import Optional

from .docker import DockerMonitor
from .gpu import GPUMonitor
from ..models.metrics import MetricsRecord, ContainerMetrics


class MetricsCollector:
    """Collect and aggregate metrics from Docker containers and GPU."""

    def __init__(self):
        """Initialize the metrics collector."""
        self.docker_monitor = DockerMonitor()
        self.gpu_monitor = GPUMonitor()

    def collect(self, container_name: str) -> Optional[MetricsRecord]:
        """Collect metrics for a single container.

        Args:
            container_name: Name or ID of the container to monitor.

        Returns:
            MetricsRecord or None if container not found.
        """
        # Get container metrics
        container_metrics = self.docker_monitor.get_metrics(container_name)
        if container_metrics is None:
            return None

        # Get GPU metrics (use first GPU if available)
        gpu_metrics = None
        if self.gpu_monitor.available:
            gpu_data = self.gpu_monitor.get_metrics()
            if gpu_data:
                gpu_metrics = gpu_data[0]  # Use first GPU

        # Create combined record
        record = MetricsRecord(
            timestamp=container_metrics.timestamp,
            container_name=container_metrics.container_name,
            container_id=container_metrics.container_id,
            cpu_percent=container_metrics.cpu_percent,
            memory_usage_mb=container_metrics.memory_usage / (1024 * 1024),
            memory_limit_mb=container_metrics.memory_limit / (1024 * 1024),
            memory_percent=container_metrics.memory_percent,
            network_rx_mb=container_metrics.network_rx_bytes / (1024 * 1024),
            network_tx_mb=container_metrics.network_tx_bytes / (1024 * 1024),
            block_read_mb=container_metrics.block_read_bytes / (1024 * 1024),
            block_write_mb=container_metrics.block_write_bytes / (1024 * 1024),
        )

        # Add GPU metrics if available
        if gpu_metrics:
            record.gpu_id = gpu_metrics["gpu_id"]
            record.gpu_name = gpu_metrics["gpu_name"]
            record.gpu_utilization = gpu_metrics["gpu_utilization"]
            record.gpu_memory_used_mb = gpu_metrics["memory_used_mb"]
            record.gpu_memory_total_mb = gpu_metrics["memory_total_mb"]
            record.gpu_memory_percent = gpu_metrics["memory_percent"]
            record.gpu_temperature = gpu_metrics["temperature"]
            record.gpu_power_draw = gpu_metrics["power_draw"]

        return record

    def collect_batch(
        self, container_names: list[str]
    ) -> list[MetricsRecord]:
        """Collect metrics for multiple containers.

        Args:
            container_names: List of container names or IDs.

        Returns:
            List of MetricsRecord for successfully monitored containers.
        """
        records = []
        for name in container_names:
            record = self.collect(name)
            if record is not None:
                records.append(record)
        return records

    def collect_continuous(
        self,
        container_name: str,
        interval: float = 1.0,
        duration: Optional[float] = None,
    ):
        """Continuously collect metrics for a container.

        Args:
            container_name: Name or ID of the container.
            interval: Sampling interval in seconds.
            duration: Total duration in seconds. None for infinite.

        Yields:
            MetricsRecord for each sample.
        """
        start_time = time.time()

        while True:
            record = self.collect(container_name)
            if record is not None:
                yield record

            if duration is not None:
                elapsed = time.time() - start_time
                if elapsed >= duration:
                    break

            time.sleep(interval)

    def list_containers(self, all_containers: bool = False) -> list[str]:
        """List available containers.

        Args:
            all_containers: Include stopped containers.

        Returns:
            List of container names.
        """
        return self.docker_monitor.list_containers(all_containers)

    def close(self):
        """Close all monitors."""
        self.docker_monitor.close()