#!/usr/bin/env python3
"""
Launch file for video_to_image node.

Example usage:
  ros2 launch video_to_image video_to_image.launch.py video_path:=/path/to/video.mov
  ros2 launch video_to_image video_to_image.launch.py video_path:=/path/to/video.mov publish_compressed:=true
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for video_to_image node."""

    # Declare launch arguments
    video_path_arg = DeclareLaunchArgument(
        'video_path',
        default_value='',
        description='Path to the video file (.mov)'
    )

    output_topic_arg = DeclareLaunchArgument(
        'output_topic',
        default_value='/rgb_camera_front/image_raw',
        description='Output topic for raw images'
    )

    publish_compressed_arg = DeclareLaunchArgument(
        'publish_compressed',
        default_value='false',
        description='Whether to publish compressed images'
    )

    compressed_topic_arg = DeclareLaunchArgument(
        'compressed_topic',
        default_value='/camera/image_raw/compressed',
        description='Output topic for compressed images'
    )

    frame_rate_arg = DeclareLaunchArgument(
        'frame_rate',
        default_value='12.0',
        description='Frame rate for publishing images'
    )

    width_arg = DeclareLaunchArgument(
        'width',
        default_value='640',
        description='Target image width'
    )

    height_arg = DeclareLaunchArgument(
        'height',
        default_value='480',
        description='Target image height'
    )

    loop_arg = DeclareLaunchArgument(
        'loop',
        default_value='true',
        description='Whether to loop the video'
    )

    frame_id_arg = DeclareLaunchArgument(
        'frame_id',
        default_value='camera',
        description='Frame ID for image header'
    )

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use /clock topic for timestamps (simulation time)'
    )

    timestamp_offset_arg = DeclareLaunchArgument(
        'timestamp_offset',
        default_value='-0.03',
        description='Timestamp offset in seconds (negative to subtract delay)'
    )

    # Create node
    video_to_image_node = Node(
        package='video_to_image',
        executable='video_to_image_node',
        name='video_to_image_node',
        output='screen',
        parameters=[{
            'video_path': LaunchConfiguration('video_path'),
            'output_topic': LaunchConfiguration('output_topic'),
            'publish_compressed': LaunchConfiguration('publish_compressed'),
            'compressed_topic': LaunchConfiguration('compressed_topic'),
            'frame_rate': LaunchConfiguration('frame_rate'),
            'width': LaunchConfiguration('width'),
            'height': LaunchConfiguration('height'),
            'loop': LaunchConfiguration('loop'),
            'frame_id': LaunchConfiguration('frame_id'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'timestamp_offset': LaunchConfiguration('timestamp_offset'),
        }]
    )

    return LaunchDescription([
        video_path_arg,
        output_topic_arg,
        publish_compressed_arg,
        compressed_topic_arg,
        frame_rate_arg,
        width_arg,
        height_arg,
        loop_arg,
        frame_id_arg,
        use_sim_time_arg,
        timestamp_offset_arg,
        video_to_image_node,
    ])