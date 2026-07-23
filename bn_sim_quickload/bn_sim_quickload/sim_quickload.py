#!/usr/bin/env python3
"""
仿真测试环境快速启动工具
Simulation test environment quick launch tool
"""

import argparse
import atexit
import os
import signal
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
        loop: Optional[bool] = None,
        rate: Optional[float] = None,
        start_offset: Optional[float] = None,
        start_paused: Optional[bool] = None,
        qos_profile_overrides_path: Optional[str] = None,
    ) -> subprocess.Popen:
        """启动 rosbag 回放

        Args:
            bag_path: bag 文件路径
            topics: 回放的 topics 列表
            clock: 是否发布 clock
            loop: 是否循环播放，None 则从配置读取
            rate: 播放速率，None 则从配置读取
            start_offset: 播放起始时间偏移（秒），None 则从配置读取
            start_paused: 启动时是否暂停，None 则从配置读取
            qos_profile_overrides_path: QoS profile 配置文件路径，None 则从配置读取
        """
        rosbag_config = self.config.get("rosbag", {})

        if bag_path is None:
            bag_path = os.path.expanduser(rosbag_config.get("default_bag_path", ""))
        if topics is None:
            topics = rosbag_config.get("default_topics", [])

        # 获取参数：参数 > 配置
        if loop is None:
            loop = rosbag_config.get("loop", False)
        if rate is None:
            rate = float(rosbag_config.get("rate", 1.0))
        else:
            rate = float(rate)
        if start_offset is None:
            start_offset = rosbag_config.get("start_offset", 0.0)
        else:
            start_offset = float(start_offset)
        if start_paused is None:
            start_paused = rosbag_config.get("start_paused", False)
        if qos_profile_overrides_path is None:
            qos_profile_overrides_path = rosbag_config.get("qos_profile_overrides_path", None)

        workspace = self.config.get("workspaces", {}).get("ritju_ws", "")
        topics_str = " ".join(topics)

        cmd = f"source {workspace} && ros2 bag play {bag_path}"
        if topics:
            cmd += f" --topics {topics_str}"
        if clock:
            cmd += f" --clock"
        if loop:
            cmd += " --loop"
        cmd += f" --rate {rate}"
        if start_offset > 0:
            cmd += f" --start-offset {start_offset}"
        if start_paused:
            cmd += " --start-paused"
        if qos_profile_overrides_path:
            cmd += f" --qos-profile-overrides-path {qos_profile_overrides_path}"

        print(f"启动 rosbag 回放: {bag_path}")
        print(f"Topics: {topics_str}")
        print(f"播放速率: {rate}")
        if start_offset > 0:
            print(f"起始偏移: {start_offset}秒")
        if start_paused:
            print(f"启动暂停: 开启")
        if qos_profile_overrides_path:
            print(f"QoS 配置文件: {qos_profile_overrides_path}")
        if loop:
            print(f"循环播放: 开启")
        print(f"命令: {cmd}")

        proc = subprocess.Popen(
            ["bash", "-c", cmd],
        )
        self.processes.append(proc)
        return proc

    def start_camera(
        self,
        camera: str = "front",
        mode: str = "raw",
        video_path: Optional[str] = None,
        frame_rate: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        use_sim_time: Optional[bool] = None,
    ) -> subprocess.Popen:
        """启动相机数据发布

        Args:
            camera: 相机选择 (front/back)
            mode: 发布模式 (raw/compressed)
            video_path: 视频文件路径
            frame_rate: 发布帧率 (Hz)，None 则从配置读取
            width: 图像宽度，None 则从配置读取
            height: 图像高度，None 则从配置读取
            use_sim_time: 是否使用仿真时间，None 则从配置读取
        """
        cameras_config = self.config.get("cameras", {})
        camera_config = cameras_config.get(camera, {})

        if video_path is None:
            video_path = camera_config.get("video_path", "")

        # 获取帧率：参数 > 相机配置 > 默认配置 (转为 float)
        if frame_rate is None:
            frame_rate = float(camera_config.get(
                "frame_rate", cameras_config.get("default_frame_rate", 30.0)
            ))
        else:
            frame_rate = float(frame_rate)

        # 获取图像尺寸：参数 > 相机配置 > 默认配置
        if width is None:
            width = camera_config.get(
                "width", cameras_config.get("default_width", 1920)
            )
        if height is None:
            height = camera_config.get(
                "height", cameras_config.get("default_height", 1080)
            )

        # 获取 use_sim_time：参数 > 相机配置 > 默认配置
        if use_sim_time is None:
            use_sim_time = camera_config.get(
                "use_sim_time", cameras_config.get("default_use_sim_time", True)
            )

        workspace = self.config.get("workspaces", {}).get("utils_ws", "")

        if mode == "raw":
            topic = camera_config.get("raw_topic", f"/rgb_camera_{camera}/image_raw")
            cmd = (
                f"source {workspace} && "
                f"ros2 launch video_to_image_cpp video_to_image_cpp.launch.py "
                f"video_path:={video_path} output_topic:={topic} "
                f"frame_rate:={frame_rate} width:={width} height:={height}"
            )
        else:  # compressed
            topic = camera_config.get("compressed_topic", f"/rgb_camera_{camera}/compressed")
            cmd = (
                f"source {workspace} && "
                f"ros2 launch video_to_image_cpp video_to_image_cpp.launch.py "
                f"video_path:={video_path} compressed_topic:={topic} "
                f"publish_compressed:=true frame_rate:={frame_rate} "
                f"width:={width} height:={height}"
            )

        if use_sim_time:
            cmd += " use_sim_time:=true"

        print(f"启动相机 {camera} ({mode}模式, {frame_rate}Hz, {width}x{height}, use_sim_time={use_sim_time}): {topic}")
        print(f"命令: {cmd}")

        proc = subprocess.Popen(
            ["bash", "-c", cmd],
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
        print(f"命令: {cmd}")

        proc = subprocess.Popen(
            ["bash", "-c", cmd],
        )
        self.processes.append(proc)
        return proc

    def start_all(
        self,
        camera_mode: str = "raw",
        bag_path: Optional[str] = None,
        frame_rate: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        use_sim_time: Optional[bool] = None,
        loop: Optional[bool] = None,
        rate: Optional[float] = None,
        start_offset: Optional[float] = None,
        start_paused: Optional[bool] = None,
        qos_profile_overrides_path: Optional[str] = None,
    ) -> None:
        """启动所有组件

        Args:
            camera_mode: 相机模式 (raw/compressed)
            bag_path: rosbag 文件路径
            frame_rate: 相机帧率 (Hz)
            width: 图像宽度
            height: 图像高度
            use_sim_time: 是否使用仿真时间
            loop: rosbag 是否循环播放
            rate: rosbag 播放速率
            start_offset: rosbag 播放起始时间偏移（秒）
            start_paused: rosbag 启动时是否暂停
            qos_profile_overrides_path: rosbag QoS profile 配置文件路径
        """
        print("=" * 50)
        print("启动仿真测试环境")
        print("=" * 50)

        # 设置环境变量
        set_environment(self.config)

        # 启动 rosbag 回放
        self.start_rosbag_playback(
            bag_path=bag_path,
            loop=loop,
            rate=rate,
            start_offset=start_offset,
            start_paused=start_paused,
            qos_profile_overrides_path=qos_profile_overrides_path,
        )

        # 启动前后相机
        self.start_camera("front", mode=camera_mode, frame_rate=frame_rate, width=width, height=height, use_sim_time=use_sim_time)
        self.start_camera("back", mode=camera_mode, frame_rate=frame_rate, width=width, height=height, use_sim_time=use_sim_time)

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
        "--loop",
        action="store_true",
        default=None,
        help="rosbag 循环播放",
    )

    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="rosbag 播放速率 (默认: 1.0)",
    )

    parser.add_argument(
        "--start-offset",
        type=float,
        default=None,
        help="rosbag 播放起始时间偏移（秒），默认从配置文件读取",
    )

    parser.add_argument(
        "--start-paused",
        action="store_true",
        default=None,
        help="rosbag 启动时暂停",
    )

    parser.add_argument(
        "--qos-profile-overrides-path",
        type=str,
        default=None,
        help="rosbag QoS profile 配置文件路径",
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
        default=None,
        help="相机数据模式，默认从配置文件读取",
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

    parser.add_argument(
        "--frame-rate",
        type=float,
        default=None,
        help="相机发布帧率 (Hz)，默认从配置文件读取",
    )

    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="图像宽度，默认从配置文件读取",
    )

    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="图像高度，默认从配置文件读取",
    )

    parser.add_argument(
        "--use-sim-time",
        action="store_true",
        default=None,
        help="相机使用仿真时间，默认从配置文件读取",
    )

    parser.add_argument(
        "--no-sim-time",
        action="store_true",
        default=None,
        help="相机不使用仿真时间",
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

    # 从配置文件获取默认 camera_mode
    cameras_config = config.get("cameras", {})
    default_camera_mode = cameras_config.get("default_mode", "compressed")
    camera_mode = args.camera_mode if args.camera_mode else default_camera_mode

    # 从配置文件获取 rosbag 参数默认值
    rosbag_config = config.get("rosbag", {})
    default_loop = rosbag_config.get("loop", False)
    default_rate = float(rosbag_config.get("rate", 1.0))
    default_start_offset = float(rosbag_config.get("start_offset", 0.0))
    default_start_paused = rosbag_config.get("start_paused", False)
    default_qos_profile_overrides_path = rosbag_config.get("qos_profile_overrides_path", None)
    loop = args.loop if args.loop else default_loop
    rate = float(args.rate) if args.rate else default_rate
    start_offset = float(args.start_offset) if args.start_offset else default_start_offset
    start_paused = args.start_paused if args.start_paused else default_start_paused
    qos_profile_overrides_path = args.qos_profile_overrides_path if args.qos_profile_overrides_path else default_qos_profile_overrides_path

    # 从配置文件获取默认值
    default_frame_rate = float(cameras_config.get("default_frame_rate", 30.0))
    default_width = cameras_config.get("default_width", 1920)
    default_height = cameras_config.get("default_height", 1080)
    default_use_sim_time = cameras_config.get("default_use_sim_time", True)

    frame_rate = float(args.frame_rate) if args.frame_rate else default_frame_rate
    width = args.width if args.width else default_width
    height = args.height if args.height else default_height

    # 处理 use_sim_time 参数
    if args.no_sim_time:
        use_sim_time = False
    elif args.use_sim_time:
        use_sim_time = True
    else:
        use_sim_time = default_use_sim_time

    # 注册清理函数
    atexit.register(manager.stop_all)

    # 注册信号处理
    def signal_handler(signum, frame):
        print(f"\n收到信号 {signum}，正在停止...")
        manager.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动组件
    if args.all:
        manager.start_all(
            camera_mode=camera_mode,
            bag_path=args.bag_path,
            frame_rate=frame_rate,
            width=width,
            height=height,
            use_sim_time=use_sim_time,
            loop=loop,
            rate=rate,
            start_offset=start_offset,
            start_paused=start_paused,
            qos_profile_overrides_path=qos_profile_overrides_path,
        )
    else:
        if args.bag_only or args.bag:
            manager.start_rosbag_playback(
                bag_path=args.bag_path,
                loop=loop,
                rate=rate,
                start_offset=start_offset,
                start_paused=start_paused,
                qos_profile_overrides_path=qos_profile_overrides_path,
            )

        if args.camera:
            manager.start_camera(args.camera, mode=camera_mode, frame_rate=frame_rate, width=width, height=height, use_sim_time=use_sim_time)

        if args.cameras:
            manager.start_camera("front", mode=camera_mode, frame_rate=frame_rate, width=width, height=height, use_sim_time=use_sim_time)
            manager.start_camera("back", mode=camera_mode, frame_rate=frame_rate, width=width, height=height, use_sim_time=use_sim_time)

        if args.lidar:
            if args.lidar == "both":
                manager.start_lidar_simulation("front")
                manager.start_lidar_simulation("back")
            else:
                manager.start_lidar_simulation(args.lidar)

    # 如果启动了进程，保持主进程运行
    if manager.processes:
        print("\n按 Ctrl+C 停止所有进程...")
        try:
            # 等待所有进程结束或信号
            for proc in manager.processes:
                proc.wait()
        except KeyboardInterrupt:
            pass
        finally:
            manager.stop_all()


if __name__ == "__main__":
    main()