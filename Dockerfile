# Образ ROS2 Jazzy Jalisco (LTS, Ubuntu 24.04) — та же версия ROS2, что установлена
# на машинах "server" и "client".
# rslidar_sdk официально поддерживает ROS2 Eloquent/Galactic/Humble,
# с Jazzy собирается и работает без изменений.
FROM osrf/ros:jazzy-desktop
# Запуск команд при сборке будет производиться в оболочке /bin/bash.
# По умолчанию используется /bin/sh, которая не подходит для данных скриптов.
SHELL ["/bin/bash", "-c"]

# Зависимости rslidar_sdk, отсутствующие в базовом образе ROS2.
# rmw-cyclonedds-cpp — альтернативная реализация DDS (необязательная, см. README).
RUN apt-get update && apt-get install -y --no-install-recommends \
      libyaml-cpp-dev \
      libpcap-dev \
      ros-jazzy-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочего пространства ROS2 (colcon workspace).
WORKDIR /rslidar_ws

# Копирование исходного кода SDK лидара и пакета сообщений в создаваемый образ.
COPY rslidar_msg src/rslidar_msg
COPY rslidar_sdk src/rslidar_sdk

# Замена конфигурации по умолчанию на конфигурацию для RS-Helios.
# Узел rslidar_sdk_node читает конфигурацию из <исходники SDK>/config/config.yaml.
COPY config/config.yaml src/rslidar_sdk/config/config.yaml

# Сборка SDK лидара из исходного кода.
RUN source /ros_entrypoint.sh && colcon build
