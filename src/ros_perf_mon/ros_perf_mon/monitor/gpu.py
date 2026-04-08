"""GPU monitoring module using nvidia-smi."""

import subprocess
import json
from datetime import datetime
from typing import Optional


class GPUMonitor:
    """Monitor GPU usage using nvidia-smi."""

    def __init__(self):
        """Initialize GPU monitor."""
        self._available = self._check_nvidia_smi()

    def _check_nvidia_smi(self) -> bool:
        """Check if nvidia-smi is available."""
        try:
            subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    @property
    def available(self) -> bool:
        """Check if GPU monitoring is available."""
        return self._available

    def get_metrics(self) -> list[dict]:
        """Get GPU metrics for all GPUs.

        Returns:
            List of GPU metric dictionaries.
        """
        if not self._available:
            return []

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            metrics = []
            timestamp = datetime.now()

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue

                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 7:
                    continue

                try:
                    gpu_id = int(parts[0])
                    gpu_name = parts[1]
                    gpu_util = float(parts[2]) if parts[2] != "[N/A]" else 0.0
                    mem_used = float(parts[3]) if parts[3] != "[N/A]" else 0.0
                    mem_total = float(parts[4]) if parts[4] != "[N/A]" else 0.0
                    mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0.0
                    temp = int(parts[5]) if parts[5] != "[N/A]" else 0
                    power = float(parts[6]) if parts[6] != "[N/A]" else 0.0

                    metrics.append({
                        "gpu_id": gpu_id,
                        "gpu_name": gpu_name,
                        "timestamp": timestamp,
                        "gpu_utilization": gpu_util,
                        "memory_used_mb": mem_used,
                        "memory_total_mb": mem_total,
                        "memory_percent": mem_percent,
                        "temperature": temp,
                        "power_draw": power,
                    })
                except (ValueError, IndexError):
                    continue

            return metrics

        except subprocess.CalledProcessError:
            return []

    def get_gpu_count(self) -> int:
        """Get the number of available GPUs.

        Returns:
            Number of GPUs, or 0 if nvidia-smi is not available.
        """
        if not self._available:
            return 0

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=count", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True,
            )
            return int(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            return 0

    def get_gpu_names(self) -> list[str]:
        """Get the names of all available GPUs.

        Returns:
            List of GPU names.
        """
        if not self._available:
            return []

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                check=True,
            )
            return [name.strip() for name in result.stdout.strip().split("\n") if name.strip()]
        except subprocess.CalledProcessError:
            return []