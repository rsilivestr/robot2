#!/usr/bin/env python3
"""Publish PointCloud2 frames saved by the writer from PostgreSQL to a ROS2 topic."""
import array
from datetime import datetime, timezone

import psycopg2
import rclpy
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import PointCloud2, PointField

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

SELECT = """
SELECT stamp, frame_id, height, width, fields,
       is_bigendian, point_step, row_step, is_dense, data
FROM frames WHERE id = %s
"""


def select_ids(cursor, start, end):
    where = []
    args = []
    if start:
        where.append('stamp >= %s::timestamptz')
        args.append(start)
    if end:
        where.append('stamp < %s::timestamptz')
        args.append(end)
    sql = 'SELECT id FROM frames'
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    cursor.execute(sql + ' ORDER BY stamp, id', args)
    return [row[0] for row in cursor.fetchall()]


def to_cloud(row):
    (stamp, frame_id, height, width, fields,
     is_bigendian, point_step, row_step, is_dense, data) = row
    msg = PointCloud2()
    since_epoch = stamp - EPOCH
    msg.header.stamp.sec = since_epoch.days * 86400 + since_epoch.seconds
    msg.header.stamp.nanosec = since_epoch.microseconds * 1000
    msg.header.frame_id = frame_id
    msg.height = height
    msg.width = width
    msg.fields = [PointField(name=f['name'], offset=f['offset'],
                             datatype=f['datatype'], count=f['count'])
                  for f in fields]
    msg.is_bigendian = is_bigendian
    msg.point_step = point_step
    msg.row_step = row_step
    msg.is_dense = is_dense
    # array.array is assigned as is, other sequences are checked element by element (slow)
    cloud_data = array.array('B')
    cloud_data.frombytes(data)
    msg.data = cloud_data
    return msg


def main():
    rclpy.init()
    node = rclpy.create_node('lidar_db_reader')
    dsn = node.declare_parameter('dsn', 'dbname=lidar').value
    topic = node.declare_parameter('topic', '/rslidar_points').value
    rate = node.declare_parameter('rate', 10.0).value
    loop = node.declare_parameter('loop', False).value
    start = node.declare_parameter('start', '').value
    end = node.declare_parameter('end', '').value

    db = psycopg2.connect(dsn)
    db.autocommit = True
    cursor = db.cursor()
    ids = select_ids(cursor, start, end)
    if not ids:
        node.get_logger().warn('no frames found')
        db.close()
        node.destroy_node()
        rclpy.try_shutdown()
        return

    publisher = node.create_publisher(PointCloud2, topic, 10)
    position = 0
    finished = False

    def publish_next():
        nonlocal position, finished
        cursor.execute(SELECT, (ids[position],))
        publisher.publish(to_cloud(cursor.fetchone()))
        position += 1
        if position < len(ids):
            return
        if loop:
            position = 0
        else:
            finished = True

    node.create_timer(1.0 / rate, publish_next)
    node.get_logger().info(f'publishing {len(ids)} frames to {topic} at {rate} Hz')

    try:
        while rclpy.ok() and not finished:
            rclpy.spin_once(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.get_logger().info(f'published up to frame {position} of {len(ids)}')
        db.close()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
