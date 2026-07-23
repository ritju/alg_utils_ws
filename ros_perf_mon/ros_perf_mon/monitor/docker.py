"""Docker container monitoring module."""

import docker
from docker.models.containers import Container
from datetime import datetime
from typing import Optional

from ..models.metrics import ContainerMetrics


class DockerMonitor:
    """Monitor Docker containers for CPU and memory usage."""

    def __init__(self):
        """Initialize Docker client."""
        self.client = docker.from_env()

    def get_container(self, container_name: str) -> Optional[Container]:
        """Get container by name or ID.

        Args:
            container_name: Container name or ID.

        Returns:
            Container object or None if not found.
        """
        try:
            return self.client.containers.get(container_name)
        except docker.errors.NotFound:
            return None
        except docker.errors.APIError as e:
            raise RuntimeError(f"Docker API error: {e}") from e

    def list_containers(self, all_containers: bool = False) -> list[str]:
        """List all container names.

        Args:
            all_containers: Include stopped containers.

        Returns:
            List of container names.
        """
        containers = self.client.containers.list(all=all_containers)
        return [c.name for c in containers]

    def get_metrics(self, container_name: str) -> Optional[ContainerMetrics]:
        """Get current metrics for a container.

        Args:
            container_name: Container name or ID.

        Returns:
            ContainerMetrics or None if container not found.
        """
        container = self.get_container(container_name)
        if container is None:
            return None

        # Get stats from Docker API
        stats = container.stats(stream=False)

        # Parse CPU percentage
        cpu_stats = stats.get("cpu_stats", {})
        precpu_stats = stats.get("precpu_stats", {})
        cpu_percent = self._calculate_cpu_percent(cpu_stats, precpu_stats)

        # Parse memory
        memory_stats = stats.get("memory_stats", {})
        memory_usage = memory_stats.get("usage", 0)
        memory_limit = memory_stats.get("limit", 0)
        memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0.0

        # Parse network I/O
        network_stats = stats.get("networks", {})
        network_rx = sum(net.get("rx_bytes", 0) for net in network_stats.values())
        network_tx = sum(net.get("tx_bytes", 0) for net in network_stats.values())

        # Parse block I/O
        blkio_stats = stats.get("blkio_stats", {})
        io_service_bytes = blkio_stats.get("io_service_bytes_recursive", [])
        block_read = sum(
            entry.get("value", 0)
            for entry in io_service_bytes
            if entry.get("op", "").lower() == "read"
        )
        block_write = sum(
            entry.get("value", 0)
            for entry in io_service_bytes
            if entry.get("op", "").lower() == "write"
        )

        return ContainerMetrics(
            container_id=container.id[:12],
            container_name=container.name,
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_usage=memory_usage,
            memory_limit=memory_limit,
            memory_percent=memory_percent,
            network_rx_bytes=network_rx,
            network_tx_bytes=network_tx,
            block_read_bytes=block_read,
            block_write_bytes=block_write,
        )

    def _calculate_cpu_percent(
        self, cpu_stats: dict, precpu_stats: dict
    ) -> float:
        """Calculate CPU percentage from Docker stats.

        Args:
            cpu_stats: Current CPU stats.
            precpu_stats: Previous CPU stats.

        Returns:
            CPU usage percentage.
        """
        cpu_usage = cpu_stats.get("cpu_usage", {})
        precpu_usage = precpu_stats.get("cpu_usage", {})

        total_usage = cpu_usage.get("total_usage", 0)
        pre_total_usage = precpu_usage.get("total_usage", 0)

        system_usage = cpu_stats.get("system_cpu_usage", 0)
        pre_system_usage = precpu_stats.get("system_cpu_usage", 0)

        # Get number of CPUs
        percpu_usage = cpu_usage.get("percpu_usage", [])
        cpu_count = len(percpu_usage) if percpu_usage else 1

        # Calculate delta
        cpu_delta = total_usage - pre_total_usage
        system_delta = system_usage - pre_system_usage

        if system_delta > 0 and cpu_delta > 0:
            return (cpu_delta / system_delta) * cpu_count * 100.0

        return 0.0

    def close(self):
        """Close Docker client."""
        self.client.close()