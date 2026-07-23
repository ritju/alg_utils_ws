cmake_minimum_required(VERSION 3.8)
project(robot_sim_bn)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch worlds rviz urdf models
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/relocalize_node.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
