# Образ ROS2 Humble Hawksbill (LTS).
# rslidar_sdk официально поддерживает ROS2 Eloquent/Galactic/Humble.
FROM osrf/ros:humble-desktop
# Запуск команд при сборке будет производиться в оболочке /bin/bash.
# По умолчанию используется /bin/sh, которая не подходит для данных скриптов.
SHELL ["/bin/bash", "-c"]

# Зависимости rslidar_sdk, отсутствующие в базовом образе ROS2.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libyaml-cpp-dev \
      libpcap-dev \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочего пространства ROS2 (colcon workspace).

# TODO

# Копирование исходного кода SDK лидара и пакета сообщений в создаваемый образ.

# TODO

# Замена конфигурации по умолчанию на конфигурацию для RS-Helios.

# TODO

# Сборка SDK лидара из исходного кода.
RUN source /ros_entrypoint.sh && colcon build
