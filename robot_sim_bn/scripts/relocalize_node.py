#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, Twist
from gazebo_msgs.srv import SetEntityState

ENTITY_NAME = 'outdoor_cleaner'


class RelocalizeNode(Node):
    def __init__(self):
        super().__init__('relocalize_node')
        self.create_subscription(PoseStamped, '/relocalize', self._relocalize_cb, 10)
        self._client = self.create_client(SetEntityState, '/gazebo/set_entity_state')
        self.get_logger().info(
            f'Relocalize node ready. Publish PoseStamped to /relocalize to move '
            f'"{ENTITY_NAME}" in Gazebo.'
        )

    def _relocalize_cb(self, msg: PoseStamped):
        if not self._client.wait_for_service(timeout_sec=2.0):
            self.get_logger().error('Gazebo /gazebo/set_entity_state service not available')
            return

        request = SetEntityState.Request()
        request.state.name = ENTITY_NAME
        request.state.pose = msg.pose
        request.state.twist = Twist()
        request.state.reference_frame = 'world'

        future = self._client.call_async(request)
        future.add_done_callback(self._done_callback)

    def _done_callback(self, future):
        try:
            result = future.result()
        except Exception as e:
            self.get_logger().error(f'Service call failed: {e}')
            return

        if result and result.success:
            pose = result.status_message
            self.get_logger().info(f'Robot relocalized successfully: {pose}')
        else:
            msg = result.status_message if result else 'no response'
            self.get_logger().error(f'Relocalize failed: {msg}')


def main():
    rclpy.init()
    node = RelocalizeNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
