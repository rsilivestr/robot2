#!/usr/bin/env python3
"""Save PointCloud2 frames from a ROS2 topic to PostgreSQL, one row per frame."""
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import Json
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2

# Everything needed to rebuild the PointCloud2 message, point data stays a raw blob.
SCHEMA = """
CREATE TABLE IF NOT EXISTS frames (
    id           bigserial PRIMARY KEY,
    stamp        timestamptz NOT NULL,
    frame_id     text NOT NULL,
    height       integer NOT NULL,
    width        integer NOT NULL,
    fields       jsonb NOT NULL,
    is_bigendian boolean NOT NULL,
    point_step   integer NOT NULL,
    row_step     integer NOT NULL,
    is_dense     boolean NOT NULL,
    data         bytea COMPRESSION lz4 NOT NULL
);
CREATE INDEX IF NOT EXISTS frames_stamp_idx ON frames (stamp);
"""

INSERT = """
INSERT INTO frames (stamp, frame_id, height, width, fields,
                    is_bigendian, point_step, row_step, is_dense, data)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def to_row(msg):
    # timestamptz keeps microseconds, the rest of nanoseconds is dropped
    stamp = (datetime.fromtimestamp(msg.header.stamp.sec, timezone.utc)
             + timedelta(microseconds=msg.header.stamp.nanosec // 1000))
    fields = [{'name': f.name, 'offset': f.offset, 'datatype': f.datatype, 'count': f.count}
              for f in msg.fields]
    return (stamp, msg.header.frame_id, msg.height, msg.width, Json(fields),
            msg.is_bigendian, msg.point_step, msg.row_step, msg.is_dense, bytes(msg.data))


def main():
    rclpy.init()
    node = rclpy.create_node('lidar_db_writer')
    dsn = node.declare_parameter('dsn', 'dbname=lidar').value
    topic = node.declare_parameter('topic', '/rslidar_points').value
    every_n = node.declare_parameter('every_n', 1).value

    db = psycopg2.connect(dsn)
    db.autocommit = True
    cursor = db.cursor()
    cursor.execute(SCHEMA)

    received = 0
    saved = 0

    def save(msg):
        nonlocal received, saved
        received += 1
        if (received - 1) % every_n:
            return
        cursor.execute(INSERT, to_row(msg))
        saved += 1

    def report():
        node.get_logger().info(f'received {received} frames, saved {saved}')

    # best effort: if the database is slow, frames are dropped instead of queued
    node.create_subscription(PointCloud2, topic, save, qos_profile_sensor_data)
    node.create_timer(10.0, report)
    node.get_logger().info(
        f'saving every {every_n} frame(s) from {topic} to database "{db.info.dbname}"')

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        report()
        db.close()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
