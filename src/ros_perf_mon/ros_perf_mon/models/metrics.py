"""Data models for performance metrics."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ContainerMetrics:
    """Container-level metrics from Docker."""

    container_id: str
    container_name: str
    timestamp: datetime
    cpu_percent: float  # CPU usage percentage
    memory_usage: int  # Memory usage in bytes
    memory_limit: int  # Memory limit in bytes
    memory_percent: float  # Memory usage percentage
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0
    block_read_bytes: int = 0
    block_write_bytes: int = 0


@dataclass
class GPUMetrics:
    """GPU metrics from nvidia-smi."""

    gpu_id: int
    gpu_name: str
    timestamp: datetime
    gpu_utilization: float  # GPU utilization percentage
    memory_used: int  # GPU memory used in bytes
    memory_total: int  # GPU memory total in bytes
    memory_percent: float  # GPU memory usage percentage
    temperature: int  # GPU temperature in Celsius
    power_draw: float  # Power draw in watts


@dataclass
class MetricsRecord:
    """Combined metrics record for a container."""

    timestamp: datetime
    container_name: str
    container_id: str
    # CPU metrics
    cpu_percent: float
    # Memory metrics
    memory_usage_mb: float
    memory_limit_mb: float
    memory_percent: float
    # GPU metrics (optional, may not be available)
    gpu_id: Optional[int] = None
    gpu_name: Optional[str] = None
    gpu_utilization: Optional[float] = None
    gpu_memory_used_mb: Optional[float] = None
    gpu_memory_total_mb: Optional[float] = None
    gpu_memory_percent: Optional[float] = None
    gpu_temperature: Optional[int] = None
    gpu_power_draw: Optional[float] = None
    # Network metrics
    network_rx_mb: float = 0.0
    network_tx_mb: float = 0.0
    # Block I/O metrics
    block_read_mb: float = 0.0
    block_write_mb: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for pandas DataFrame."""
        return {
            "timestamp": self.timestamp,
            "container_name": self.container_name,
            "container_id": self.container_id,
            "cpu_percent": self.cpu_percent,
            "memory_usage_mb": self.memory_usage_mb,
            "memory_limit_mb": self.memory_limit_mb,
            "memory_percent": self.memory_percent,
            "gpu_id": self.gpu_id,
            "gpu_name": self.gpu_name,
            "gpu_utilization": self.gpu_utilization,
            "gpu_memory_used_mb": self.gpu_memory_used_mb,
            "gpu_memory_total_mb": self.gpu_memory_total_mb,
            "gpu_memory_percent": self.gpu_memory_percent,
            "gpu_temperature": self.gpu_temperature,
            "gpu_power_draw": self.gpu_power_draw,
            "network_rx_mb": self.network_rx_mb,
            "network_tx_mb": self.network_tx_mb,
            "block_read_mb": self.block_read_mb,
            "block_write_mb": self.block_write_mb,
        }