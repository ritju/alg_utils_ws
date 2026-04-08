from setuptools import find_packages, setup
import os
import glob

package_name = 'bn_sim_quickload'

# 收集配置文件
config_files = glob.glob('bn_sim_quickload/config/*')

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # 安装配置文件
        (os.path.join('share', package_name, 'config'), config_files),
    ],
    install_requires=['setuptools', 'pyyaml'],
    zip_safe=True,
    maintainer='sherlock',
    maintainer_email='zxy54@Outlook.com',
    description='Simulation test environment quick launch tool for unified management of ROS2 test environment',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'sim_quickload = bn_sim_quickload.sim_quickload:main',
        ],
    },
)
