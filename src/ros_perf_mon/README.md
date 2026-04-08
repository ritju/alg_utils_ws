# ROS Performance Monitor

A Python toolkit for monitoring ROS C++ nodes running in Docker containers. Focuses on CPU, GPU, and memory usage analysis.

## Features

- **Docker Container Monitoring**: CPU and memory usage via Docker Stats API
- **GPU Monitoring**: NVIDIA GPU metrics via nvidia-smi
- **Multiple Output Formats**: CSV, JSON, Parquet, and pandas DataFrame
- **CLI Interface**: Easy-to-use command-line tool
- **Continuous Monitoring**: Real-time metrics collection with configurable intervals

## Installation

```bash
pip install ros-perf-mon
```

Or install from source:

```bash
cd ros_perf_mon
pip install -e .
```

## Requirements

- Python 3.10+
- Docker (with docker-py)
- NVIDIA drivers and nvidia-smi (for GPU monitoring)

## Usage

### List available containers

```bash
ros-perf-mon list
ros-perf-mon list --all  # Include stopped containers
```

### Take a single sample

```bash
ros-perf-mon sample my_container
ros-perf-mon sample container1 container2 -o metrics.csv
```

### Continuous monitoring

```bash
# Monitor indefinitely (Ctrl+C to stop)
ros-perf-mon monitor my_container

# Monitor for 60 seconds with 2-second interval
ros-perf-mon monitor my_container -i 2 -d 60

# Save results to file
ros-perf-mon monitor my_container -o results.csv --summary
```

### Output formats

```bash
# CSV format (default)
ros-perf-mon monitor my_container -o metrics.csv

# JSON format
ros-perf-mon monitor my_container -o metrics.json -f json

# Parquet format (for large datasets)
ros-perf-mon monitor my_container -o metrics.parquet -f parquet
```

## Python API

```python
from ros_perf_mon.monitor import MetricsCollector
from ros_perf_mon.output import MetricsExporter

# Create collector
collector = MetricsCollector()

# Single sample
record = collector.collect("my_container")
print(record.to_dict())

# Continuous monitoring
for record in collector.collect_continuous("my_container", interval=1.0, duration=60):
    print(f"CPU: {record.cpu_percent:.1f}%, Memory: {record.memory_usage_mb:.0f} MB")

# Export to pandas DataFrame
records = list(collector.collect_continuous("my_container", interval=1.0, duration=10))
df = MetricsExporter.to_dataframe(records)

# Export to file
MetricsExporter.to_csv(records, "metrics.csv")
MetricsExporter.to_json(records, "metrics.json")
MetricsExporter.to_parquet(records, "metrics.parquet")

# Print summary
MetricsExporter.print_summary(records)

# Cleanup
collector.close()
```

## Output Columns

| Column | Description |
|--------|-------------|
| `timestamp` | Sample timestamp |
| `container_name` | Container name |
| `container_id` | Container ID (short) |
| `cpu_percent` | CPU usage percentage |
| `memory_usage_mb` | Memory usage in MB |
| `memory_limit_mb` | Memory limit in MB |
| `memory_percent` | Memory usage percentage |
| `gpu_id` | GPU index (if available) |
| `gpu_name` | GPU name (if available) |
| `gpu_utilization` | GPU utilization percentage |
| `gpu_memory_used_mb` | GPU memory used in MB |
| `gpu_memory_total_mb` | GPU memory total in MB |
| `gpu_memory_percent` | GPU memory usage percentage |
| `gpu_temperature` | GPU temperature in Celsius |
| `gpu_power_draw` | GPU power draw in watts |
| `network_rx_mb` | Network received in MB |
| `network_tx_mb` | Network transmitted in MB |
| `block_read_mb` | Block I/O read in MB |
| `block_write_mb` | Block I/O write in MB |

## License

MIT License