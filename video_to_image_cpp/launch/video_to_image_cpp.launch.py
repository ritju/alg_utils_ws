#!/usr/bin/env python3
"""
Launch file for video_to_image_cpp node.

Uses YAML config file as the primary configuration source.
All parameters should be configured in the YAML file.

Example usage:
  Default config:
    ros2 launch video_to_image_cpp video_to_image_cpp.launch.py

  Custom config file:
    ros2 launch video_to_image_cpp video_to_image_cpp.launch.py config_file:=/path/to/custom_params.yaml
"""

import uuid
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_unique_id():
    """Generate a short unique identifier."""
    return uuid.uuid4().hex[:8]


def generate_launch_description():
    """Generate launch description for video_to_image_cpp node."""
    pkg_share = FindPackageShare('video_to_image_cpp')
    default_config = PathJoinSubstitution([pkg_share, 'config', 'video_to_image_params.yaml'])

    # Declare launch arguments
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value=default_config,
        description='Path to YAML config file (default: package config/video_to_image_params.yaml)'
    )

    unique_id = generate_unique_id()

    video_to_image_node = Node(
        package='video_to_image_cpp',
        executable='video_to_image_node',
        name=f'video_to_image_node_{unique_id}',
        output='screen',
        parameters=[LaunchConfiguration('config_file')]
    )

    return LaunchDescription([
        config_file_arg,
        video_to_image_node,
    ])