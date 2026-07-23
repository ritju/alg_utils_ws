#!/usr/bin/env python3
"""
Video to Image ROS2 Node

Converts .mov video files to sensor_msgs::msg::Image or CompressedImage
and publishes to specified topics with timestamps from /clock.
"""

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.clock import Clock, ClockType
from rclpy.time import Time
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge
from pathlib import Path


class VideoToImageNode(Node):
    """Node that reads video files and publishes as ROS2 image messages."""

    def __init__(self):
        super().__init__('video_to_image_node')

        # Declare parameters
        self.declare_parameter('video_path', '')
        self.declare_parameter('output_topic', '/camera/image_raw')
        self.declare_parameter('publish_compressed', False)
        self.declare_parameter('compressed_topic', '/camera/image_raw/compressed')
        self.declare_parameter('frame_rate', 30.0)
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        self.declare_parameter('loop', True)
        self.declare_parameter('frame_id', 'camera')
        self.declare_parameter('timestamp_offset', 0.01)

        # Get parameters
        self.video_path = self.get_parameter('video_path').value
        self.output_topic = self.get_parameter('output_topic').value
        self.publish_compressed = self.get_parameter('publish_compressed').value
        self.compressed_topic = self.get_parameter('compressed_topic').value
        self.frame_rate = self.get_parameter('frame_rate').value
        self.target_width = self.get_parameter('width').value
        self.target_height = self.get_parameter('height').value
        self.loop = self.get_parameter('loop').value
        self.frame_id = self.get_parameter('frame_id').value
        self.use_sim_time = self.get_parameter('use_sim_time').value
        self.timestamp_offset = self.get_parameter('timestamp_offset').value

        # Validate video path
        if not self.video_path:
            self.get_logger().error('video_path parameter is required!')
            raise ValueError('video_path parameter is required!')

        if not Path(self.video_path).exists():
            self.get_logger().error(f'Video file not found: {self.video_path}')
            raise FileNotFoundError(f'Video file not found: {self.video_path}')

        # Initialize CV bridge
        self.bridge = CvBridge()

        # Create publishers with volatile QoS
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=3
        )

        if self.publish_compressed:
            self.compressed_publisher = self.create_publisher(
                CompressedImage,
                self.compressed_topic,
                qos_profile
            )
            self.get_logger().info(
                f'Publishing compressed images to: {self.compressed_topic}'
            )
        else:
            self.image_publisher = self.create_publisher(
                Image,
                self.output_topic,
                qos_profile
            )
            self.get_logger().info(
                f'Publishing raw images to: {self.output_topic}'
            )

        # Open video file
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            self.get_logger().error(f'Failed to open video: {self.video_path}')
            raise RuntimeError(f'Failed to open video: {self.video_path}')

        # Get video properties
        self.video_fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.video_frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.video_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.get_logger().info(
            f'Video loaded: {self.video_path}\n'
            f'  Resolution: {self.video_width}x{self.video_height}\n'
            f'  FPS: {self.video_fps}\n'
            f'  Frames: {self.video_frame_count}'
        )
        self.get_logger().info(
            f'Target resolution: {self.target_width}x{self.target_height}'
        )

        # Calculate frame interval based on desired frame rate
        self.frame_interval = 1.0 / self.frame_rate

        # Create timer for publishing frames
        self.timer = self.create_timer(self.frame_interval, self.timer_callback)

        # Frame counter for timing
        self.frame_count = 0

        self.get_logger().info(f'use_sim_time: {self.use_sim_time}')
        if self.use_sim_time:
            self.get_logger().info('Using /clock topic for timestamps')
        self.get_logger().info('Video to Image node started')

    def timer_callback(self):
        """Timer callback to read and publish video frames."""
        ret, frame = self.cap.read()

        if not ret:
            if self.loop:
                self.get_logger().info('Video ended, looping...')
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    self.get_logger().error('Failed to restart video')
                    return
            else:
                self.get_logger().info('Video ended, stopping...')
                self.timer.cancel()
                return

        # Resize frame to target resolution
        if (self.target_width != self.video_width or
            self.target_height != self.video_height):
            frame = cv2.resize(
                frame,
                (self.target_width, self.target_height),
                interpolation=cv2.INTER_LINEAR
            )

        # Get timestamp from /clock (ROS clock) with offset adjustment
        timestamp = self.get_clock().now()
        # Apply timestamp offset (subtract delay)
        timestamp = Time(
            seconds=timestamp.nanoseconds / 1e9 + self.timestamp_offset,
            clock_type=timestamp.clock_type
        )

        if self.publish_compressed:
            self.publish_compressed_image(frame, timestamp)
        else:
            self.publish_raw_image(frame, timestamp)

        self.frame_count += 1

    def publish_raw_image(self, frame: np.ndarray, timestamp):
        """Publish raw sensor_msgs::msg::Image."""
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create Image message
        msg = Image()
        msg.header.stamp = timestamp.to_msg()
        msg.header.frame_id = self.frame_id
        msg.height = frame_rgb.shape[0]
        msg.width = frame_rgb.shape[1]
        msg.encoding = 'rgb8'
        msg.is_bigendian = False
        msg.step = frame_rgb.shape[1] * 3
        msg.data = frame_rgb.tobytes()

        self.image_publisher.publish(msg)

    def publish_compressed_image(self, frame: np.ndarray, timestamp):
        """Publish sensor_msgs::msg::CompressedImage."""
        # Encode frame as JPEG
        success, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not success:
            self.get_logger().error('Failed to encode frame as JPEG')
            return

        # Create CompressedImage message
        msg = CompressedImage()
        msg.header.stamp = timestamp.to_msg()
        msg.header.frame_id = self.frame_id
        msg.format = 'jpeg'
        msg.data = encoded.tobytes()

        self.compressed_publisher.publish(msg)

    def destroy_node(self):
        """Clean up resources."""
        if self.cap is not None:
            self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    try:
        node = VideoToImageNode()
        rclpy.spin(node)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f'Error: {e}')
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()