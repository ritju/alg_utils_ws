from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'video_to_image'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='sherlock',
    maintainer_email='zxy54@Outlook.com',
    description='Convert video files to ROS2 Image/CompressedImage messages',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'video_to_image_node = video_to_image.video_to_image_node:main',
        ],
    },
)
