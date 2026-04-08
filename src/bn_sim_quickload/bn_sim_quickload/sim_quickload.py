#!/usr/bin/env python3
"""
仿真测试环境快速启动工具
Simulation test environment quick launch tool
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml


def get_config_dir() -> Path:
    """获取配置文件目录"""
    return Path(__file__).parent / "config"


def load_config(config_file: Optional[str] = None) -> Dict:
    """加载配置文件"""
    if config_file is None:
        config_file = get_config_dir() / "sim_env.yaml"
    else:
        config_file = Path(config_file)

    if not config_file.exists():
        print(f"配置文件不存在: {config_file}")
        sys.exit(1)

    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def set_environment(config: Dict) -> None:
    """设置环境变量"""
    env_config = config.get("environment", {})
    for key, value in env_config.items():
        os.environ[key] = value
        print(f"设置环境变量: {key}={value}")


def source_workspace(workspace_path: str) -> Dict[str, str]:
    """获取 source 工作空间后的环境变量"""
    # 注意: Python subprocess 无法直接 source，需要通过 bash -c 执行
    return workspace_path


def build_ros_command(
    workspace: str,
    command: str,
    use_sim_time: bool = False,
    additional_args: Optional[List[str]] = None,
) -> str:
    """构建 ROS 命令"""
    cmd_parts = [f"source {workspace}", command]
    if use_sim_time:
        cmd_parts.append("--use-sim-time" if "ros2 run" in command else "use_sim_time:=true")
    if additional_args:
        cmd_parts.extend(additional_args)
    return " && ".join(cmd_parts)


class SimQuickload:
    """仿真环境管理类"""

    def __init__(self, config: Dict):
        self.config = config
        self.processes: List[subprocess.Popen] = []
        self.config_dir = get_config_dir()

    def start_rosbag_playback(
        self,
        bag_path: Optional[str] = None,
        topics: Optional[List[str]] = None,
        clock: bool = True,
    ) -> subprocess.Popen:
        """启动 rosbag 回放"""
        rosbag_config = self.config.get("rosbag", {})

        if bag_path is None:
            bag_path = os.path.expanduser(rosbag_config.get("default_bag_path", ""))
        if topics is None:
            topics = rosbag_config.get("default_topics", [])

        workspace = self.config.get("workspaces", {}).get("ritju_ws", "")
        topics_str = ",".join(topics)

        cmd = f"source {workspace} && ros2 bag play {bag_path}"
        if topics:
            cmd += f" --topics {topics_str}"
        if clock:
            cmd += " --clock"

        print(f"启动 rosbag 回放: {bag_path}")
        print(f"Topics: {topics_str}")

        proc = subprocess.Popen(
            ["bash", "-c", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.processes.append(proc)
        return proc

    def start_camera(
        self,
        camera: str = "front",
        mode: str = "raw",
        video_path: Optional[str] = None,
    ) -> subprocess.Popen:
        """启动相机数据发布

        Args:
            camera: 相机选择 (front/back)
            mode: 发布模式 (raw/compressed)
            video_path: 视频文件路径
        """
        cameras_config = self.config.get("cameras", {})
        camera_config = cameras_config.get(camera, {})

        if video_path is None:
            video_path = camera_config.get("video_path", "")

        workspace = self.config.get("workspaces", {}).get("utils_ws", "")

        if mode == "raw":
            topic = camera_config.get("raw_topic", f"/rgb_camera_{camera}/image_raw")
            cmd = (
                f"source {workspace} && "
                f"ros2 launch video_to_image_cpp video_to_image_cpp.launch.py "
                f"video_path:={video_path} output_topic:={topic}"
            )
        else:  # compressed
            topic = camera_config.get("compressed_topic", f"/rgb_camera_{camera}/compressed")
            cmd = (
                f"source {workspace} && "
                f"ros2 launch video_to_image_cpp video_to_image_cpp.launch.py "
                f"video_path:={video_path} compressed_topic:={topic} publish_compressed:=true"
            )

        print(f"启动相机 {camera} ({mode}模式): {topic}")

        proc = subprocess.Popen(
            ["bash", "-c", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.processes.append(proc)
        return proc

    def start_lidar_simulation(
        self,
        lidar: str = "front",
        config_file: Optional[str] = None,
    ) -> subprocess.Popen:
        """启动激光雷达模拟

        Args:
            lidar: 激光雷达选择 (front/back)
            config_file: 配置文件路径
        """
        lidar_config = self.config.get("lidar_simulation", {}).get(lidar, {})

        if config_file is None:
            # 使用包内的配置文件
            config_file = self.config_dir / lidar_config.get(
                "config_file", f"world_to_scan_{lidar}.json"
            )
        else:
            config_file = Path(config_file)

        workspace = self.config.get("workspaces", {}).get("nav2_ws", "")
        use_sim_time = lidar_config.get("use_sim_time", True)

        cmd = (
            f"source {workspace} && "
            f"ros2 launch cpp_pubsub world_to_scan.launch.py "
            f"config_file:={config_file}"
        )
        if use_sim_time:
            cmd += " use_sim_time:=true"

        print(f"启动激光雷达模拟 {lidar}: {config_file}")

        proc = subprocess.Popen(
            ["bash", "-c", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.processes.append(proc)
        return proc

    def start_all(
        self,
        camera_mode: str = "raw",
        bag_path: Optional[str] = None,
    ) -> None:
        """启动所有组件"""
        print("=" * 50)
        print("启动仿真测试环境")
        print("=" * 50)

        # 设置环境变量
        set_environment(self.config)

        # 启动 rosbag 回放
        self.start_rosbag_playback(bag_path=bag_path)

        # 启动前后相机
        self.start_camera("front", mode=camera_mode)
        self.start_camera("back", mode=camera_mode)

        # 启动激光雷达模拟
        self.start_lidar_simulation("front")
        self.start_lidar_simulation("back")

        print("=" * 50)
        print("所有组件已启动")
        print("=" * 50)

    def stop_all(self) -> None:
        """停止所有进程"""
        print("停止所有进程...")
        for proc in self.processes:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.processes.clear()
        print("所有进程已停止")

    def list_processes(self) -> None:
        """列出所有运行的进程"""
        print(f"当前运行进程数: {len(self.processes)}")
        for i, proc in enumerate(self.processes):
            status = "运行中" if proc.poll() is None else f"已退出 (code: {proc.returncode})"
            print(f"  [{i}] PID: {proc.pid} - {status}")


def main():
    parser = argparse.ArgumentParser(
        description="仿真测试环境快速启动工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 启动所有组件 (使用压缩相机数据)
  sim_quickload --all --camera-mode compressed

  # 只启动 rosbag 回放
  sim_quickload --bag-only

  # 启动 rosbag 和相机
  sim_quickload --bag --cameras --camera-mode raw

  # 启动激光雷达模拟
  sim_quickload --lidar front
  sim_quickload --lidar back
  sim_quickload --lidar both

  # 使用自定义配置文件
  sim_quickload --config /path/to/config.yaml --all

  # 使用自定义 bag 文件
  sim_quickload --all --bag-path ~/data/my_bag
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="配置文件路径 (默认使用包内配置)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="启动所有组件",
    )

    parser.add_argument(
        "--bag-only",
        action="store_true",
        help="只启动 rosbag 回放",
    )

    parser.add_argument(
        "--bag",
        action="store_true",
        help="启动 rosbag 回放",
    )

    parser.add_argument(
        "--bag-path",
        type=str,
        default=None,
        help="自定义 bag 文件路径",
    )

    parser.add_argument(
        "--cameras",
        action="store_true",
        help="启动前后相机",
    )

    parser.add_argument(
        "--camera",
        type=str,
        choices=["front", "back"],
        default=None,
        help="启动指定相机",
    )

    parser.add_argument(
        "--camera-mode",
        type=str,
        choices=["raw", "compressed"],
        default="compressed",
        help="相机数据模式 (默认: compressed)",
    )

    parser.add_argument(
        "--lidar",
        type=str,
        choices=["front", "back", "both"],
        default=None,
        help="启动激光雷达模拟",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="列出当前运行的进程",
    )

    parser.add_argument(
        "--stop",
        action="store_true",
        help="停止所有进程",
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 创建管理器
    manager = SimQuickload(config)

    # 如果没有参数，显示帮助
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    # 处理命令
    if args.stop:
        manager.stop_all()
        return

    if args.list:
        manager.list_processes()
        return

    # 设置环境变量
    set_environment(config)

    # 启动组件
    if args.all:
        manager.start_all(camera_mode=args.camera_mode, bag_path=args.bag_path)
    else:
        if args.bag_only or args.bag:
            manager.start_rosbag_playback(bag_path=args.bag_path)

        if args.camera:
            manager.start_camera(args.camera, mode=args.camera_mode)

        if args.cameras:
            manager.start_camera("front", mode=args.camera_mode)
            manager.start_camera("back", mode=args.camera_mode)

        if args.lidar:
            if args.lidar == "both":
                manager.start_lidar_simulation("front")
                manager.start_lidar_simulation("back")
            else:
                manager.start_lidar_simulation(args.lidar)


if __name__ == "__main__":
    main()