import os
import random

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


ROBOT_MODEL = 'outdoor_cleaner'
INITIAL_X = 0.0
INITIAL_Y = 5.0
RANDOM_RANGE = 0.2


def _randomized_pose(context, *args, **kwargs):
    """Compute randomized initial spawn pose and return launch actions."""
    x = INITIAL_X + random.uniform(-RANDOM_RANGE, RANDOM_RANGE)
    y = INITIAL_Y + random.uniform(-RANDOM_RANGE, RANDOM_RANGE)
    print(f'[simulation] Randomized initial pose: x={x:.4f}, y={y:.4f}')

    pkg_sim = get_package_share_directory('robot_sim_bn')
    urdf_path = os.path.join(pkg_sim, 'urdf', f'{ROBOT_MODEL}.urdf')
    sdf_path = os.path.join(pkg_sim, 'models', ROBOT_MODEL, 'model.sdf')

    with open(urdf_path, 'r') as f:
        robot_desc = f.read()

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'robot_description': robot_desc,
        }],
    )

    spawn_entity = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-entity', ROBOT_MODEL,
            '-file', sdf_path,
            '-x', str(x),
            '-y', str(y),
            '-z', '0.01',
        ],
        output='screen',
    )

    return [robot_state_publisher, spawn_entity]


def generate_launch_description():
    pkg_sim = get_package_share_directory('robot_sim_bn')
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')

    world = os.path.join(pkg_sim, 'worlds', 'sim_world.world')
    rviz_config = os.path.join(pkg_sim, 'rviz', 'sim.rviz')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true',
    )

    gzserver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzserver.launch.py')
        ),
        launch_arguments={'world': world}.items(),
    )

    gzclient = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzclient.launch.py')
        ),
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
    )

    relocalize_node = Node(
        package='robot_sim_bn',
        executable='relocalize_node.py',
        name='relocalize_node',
        output='screen',
    )

    ld = LaunchDescription()
    ld.add_action(declare_use_sim_time)
    ld.add_action(gzserver)
    ld.add_action(gzclient)
    ld.add_action(OpaqueFunction(function=_randomized_pose))
    ld.add_action(rviz)
    ld.add_action(relocalize_node)
    return ld
