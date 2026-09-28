# Подключение к лидару RoboSense Helios

Схема работы:
- **server** — машина без графического интерфейса, к которой по Ethernet подключён лидар.
  Драйвер лидара (`rslidar_sdk`) собран и запущен в ROS2 Jazzy, установленном на этой машине.
  Драйвер публикует облако точек в топик ROS2 `/rslidar_points`
  (тип `sensor_msgs/PointCloud2`, frame `rslidar`).
- **client** — машина в той же локальной сети с ROS2 Jazzy, получает облако точек по ROS2
  и показывает его в RViz2.

Далее `~/robot2` — путь к этому репозиторию на "server".

## Инициализация git-подмодулей (SDK, драйвер, сообщения)
```bash
git submodule update --init --recursive
```

## Сборка драйвера на "server"
Зависимости SDK и сборщик colcon:
```sh
sudo apt install libyaml-cpp-dev libpcap-dev python3-colcon-common-extensions
```

Рабочее пространство ROS2 (colcon workspace) создаётся вне репозитория, исходники
подключаются символическими ссылками. Каталоги сборки не попадают в репозиторий.
```sh
source /opt/ros/jazzy/setup.bash
mkdir -p ~/rslidar_ws/src
cd ~/rslidar_ws
ln -s ~/robot2/rslidar_sdk ~/robot2/rslidar_msg src/
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release
```
Ожидается: `Summary: 2 packages finished`.

После обновления подмодулей (`git pull`, `git submodule update`) повторите `colcon build`.

## 1. "server": чтение облака точек и проверка лидара без графического интерфейса

Проверки идут от физического подключения к ROS2. Если шаг не проходит, дальнейшие
шаги не имеют смысла: ищите причину на этом шаге.

Обозначения в командах: `<iface>` — сетевой интерфейс "server", к которому подключён
лидар (список: `ip -br link`). Адреса — заводские настройки Helios: лидар `192.168.1.200`,
адрес назначения пакетов ("server") `192.168.1.102`, порты MSOP `6699` и DIFOP `7788`.
Если сеть настроена по-другому, подставьте свои значения.

Если включён брандмауэр ufw (`sudo ufw status`), разрешите порты лидара:
```sh
sudo ufw allow 6699/udp
sudo ufw allow 7788/udp
```

### 1.1 Физическое подключение
```sh
ip -br link show <iface>
cat /sys/class/net/<iface>/carrier
```
Ожидается: состояние `UP` и `1` (кабель подключён, есть линк). `0` — нет линка:
проверьте питание лидара, кабель, блок интерфейса лидара.

### 1.2 Сетевая доступность
```sh
ip -br addr show <iface>          # ожидается 192.168.1.102/24
ping -c 3 192.168.1.200           # ожидаются ответы от лидара
curl -sI http://192.168.1.200 | head -1   # веб-интерфейс лидара, ожидается HTTP/1.1 200
```

### 1.3 UDP-пакеты лидара доходят до "server"
```sh
sudo tcpdump -ni <iface> -c 10 udp port 6699   # MSOP (облако точек)
sudo tcpdump -ni <iface> -c 5 udp port 7788    # DIFOP (служебные данные)
```
Ожидается: строки вида `IP 192.168.1.200.6699 > 192.168.1.102.6699: UDP, length 1248`.
- Пакетов нет, но ping работает: лидар шлёт данные на другой адрес или порты.
  Проверьте в веб-интерфейсе лидара адрес назначения и порты MSOP/DIFOP.
- Пакеты есть, но драйвер (шаг 1.4) их не видит: проверьте ufw и порты в `config/config.yaml`.

### 1.4 Запуск драйвера
Драйвер работает, пока открыт терминал. Для работы по SSH удобно запускать его в [tmux](https://github.com/tmux/tmux/wiki)
и выполнять проверки шага 1.5 во втором окне или втором SSH-подключении.
```sh
source /opt/ros/jazzy/setup.bash
source ~/rslidar_ws/install/setup.bash
ros2 run rslidar_sdk rslidar_sdk_node --ros-args -p config_path:=$HOME/robot2/config/config.yaml
```
Параметр `config_path` обязателен: без него драйвер читает конфигурацию SDK по умолчанию
(`rslidar_sdk/config/config.yaml`, настроена на другую модель лидара).

Ожидается в выводе:
```
Config loaded from PATH:
/home/<user>/robot2/config/config.yaml
...
Receive Packets From : Online LiDAR
...
lidar_type: RSHELIOS
...
RoboSense-LiDAR-Driver is running.....
```
Если раз в секунду появляется `ERRCODE_MSOPTIMEOUT`, драйвер не получает MSOP-пакеты
(таймаут 1 с): вернитесь к шагу 1.3.

Остановка драйвера: `Ctrl+C`.

### 1.5 Облако точек публикуется в ROS2
В другом терминале "server":
```sh
source /opt/ros/jazzy/setup.bash
# частота кадров, ожидается ~10 Hz (при заводской скорости вращения 600 об/мин)
ros2 topic hz /rslidar_points
# один кадр без массива данных: ожидается frame_id: rslidar, ненулевые width/height
ros2 topic echo /rslidar_points --no-arr --once
# поток данных, ожидается порядка 9 MB/s
ros2 topic bw /rslidar_points
```

### 1.6 Изменение конфигурации
После изменения `config/config.yaml` перезапустите драйвер (`Ctrl+C`, затем команда
из шага 1.4). Пересборка не нужна.

## 2. Проверка связи ROS2 между "client" и "server"

Условия, обязательные на обеих машинах:
- одинаковый `ROS_DOMAIN_ID` (по умолчанию `0`; проверить: `echo $ROS_DOMAIN_ID`);
- `ROS_AUTOMATIC_DISCOVERY_RANGE` не равен `LOCALHOST` (по умолчанию `SUBNET`);
- одинаковая реализация DDS (`RMW_IMPLEMENTATION`, по умолчанию Fast DDS);
- в каждом новом терминале выполнен `source /opt/ros/jazzy/setup.bash`.

### 2.1 Сеть
```sh
ping -c 3 <IP другой машины>
```
Если включён ufw, разрешите весь трафик с другой машины (DDS использует UDP multicast
`239.255.0.1` и порты от `7400`):
```sh
sudo ufw allow from <IP другой машины>
```

### 2.2 Multicast (обнаружение узлов ROS2)
На одной машине:
```sh
ros2 multicast receive
```
На другой:
```sh
ros2 multicast send
```
Ожидается на первой машине: `Received from <IP>:<port>: 'Hello World!'`.
Затем поменяйте машины местами.

### 2.3 Обмен сообщениями
На "server":
```sh
ros2 topic pub /chatter std_msgs/msg/String "{data: hello from server}"
```
На "client":
```sh
ros2 topic echo /chatter
```
Ожидается: `data: hello from server` раз в секунду. Затем поменяйте направление
(pub на "client", echo на "server").

### 2.4 Если связи нет
- Устаревший список топиков: `ros2 daemon stop`, затем повторить команду.
- Multicast не работает (Wi-Fi, VPN, некоторые коммутаторы): укажите адрес другой машины
  явно, на обеих машинах перед запуском узлов:
  ```sh
  export ROS_STATIC_PEERS=<IP другой машины>
  ```

## 3. "client": получение облака точек
Драйвер на "server" запущен (шаг 1.4), связь проверена (раздел 2).
```sh
source /opt/ros/jazzy/setup.bash
ros2 topic list | grep rslidar                          # ожидается /rslidar_points
ros2 topic hz /rslidar_points                           # ожидается ~10 Hz
ros2 topic echo /rslidar_points --no-arr --once         # заголовок кадра, frame_id: rslidar
```

Отображение в RViz2 с готовой конфигурацией из SDK (из корня этого репозитория):
```sh
rviz2 -d rslidar_sdk/rviz/rviz2.rviz
```
Без репозитория: запустить `rviz2`, в `Global Options` указать `Fixed Frame` = `rslidar`,
нажать `Add` → `By topic` → `/rslidar_points` → `PointCloud2`.

Объём данных: один кадр Helios (32 луча) около 0.9 MB, при 10 Hz это около 75 Mbit/s.
Рекомендуется проводное подключение 1 Gbit/s. `ros2 topic hz` по сети может показывать
частоту ниже реальной; частоту удобнее смотреть в RViz2 (см.
`rslidar_sdk/doc/howto/13_how_to_solve_ROS2_humble_frame_rate_drop.md`).

## 4. Запись облака точек в rosbag2
rosbag2 — встроенный в ROS2 механизм записи топиков в файлы. В Jazzy формат по умолчанию —
MCAP. Запись сохраняет сообщения с исходными временными метками, её можно воспроизвести
обратно в ROS2 (RViz2, другие узлы) или прочитать из Python.

Записывайте на "server": данные не идут по сети, кадры не теряются.
Драйвер запущен (шаг 1.4).

Если команда `ros2 bag` отсутствует:
```sh
sudo apt install ros-jazzy-rosbag2 ros-jazzy-rosbag2-storage-mcap
```

### 4.1 Свободное место
Без сжатия поток ~9 MB/s, это около 32 GB в час. Проверьте свободное место:
```sh
df -h ~
```

### 4.2 Запись
Запись идёт, пока открыт терминал. По SSH запускайте её в tmux, как драйвер в шаге 1.4.
```sh
source /opt/ros/jazzy/setup.bash
mkdir -p ~/bags
ros2 bag record /rslidar_points \
  -s mcap --storage-preset-profile zstd_fast \
  -d 600 \
  -o ~/bags/lidar_$(date +%F_%H-%M-%S)
```
Параметры:
- `-s mcap` — формат хранения MCAP;
- `--storage-preset-profile zstd_fast` — сжатие zstd внутри файла MCAP с малой нагрузкой на CPU;
- `-d 600` — новый файл каждые 600 с. При аварийном завершении теряется только последний файл;
- `-o` — каталог записи. Каталог не должен существовать, rosbag2 создаёт его сам.

Ожидается в выводе: `Subscribed to topic '/rslidar_points'` и `Recording...`.

Остановка записи: `Ctrl+C`. rosbag2 закрывает файлы и пишет `metadata.yaml`.

### 4.3 Проверка записи
```sh
ros2 bag info ~/bags/lidar_<дата>
```
Ожидается: `Storage id: mcap`, топик `/rslidar_points` типа `sensor_msgs/msg/PointCloud2`,
`Count` примерно равен длительности записи в секундах, умноженной на 10.

### 4.4 Воспроизведение
Скопируйте каталог записи на "client" (например, `scp -r` или `rsync -a`).
Драйвер на "server" при воспроизведении остановите: иначе в топик `/rslidar_points`
публикуют два источника.
```sh
source /opt/ros/jazzy/setup.bash
ros2 bag play ~/bags/lidar_<дата>             # воспроизведение с исходной скоростью
ros2 bag play ~/bags/lidar_<дата> --loop      # по кругу
ros2 bag play ~/bags/lidar_<дата> --rate 0.5  # в 2 раза медленнее
```
Облако точек смотрите в RViz2, как в разделе 3.

### 4.5 Чтение записи из Python
Выполняйте после `source /opt/ros/jazzy/setup.bash`.
```python
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2

reader = rosbag2_py.SequentialReader()
reader.open(
    rosbag2_py.StorageOptions(uri='/home/<user>/bags/lidar_<дата>', storage_id='mcap'),
    rosbag2_py.ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'),
)
while reader.has_next():
    topic, data, stamp_ns = reader.read_next()
    msg = deserialize_message(data, PointCloud2)
    xyz = point_cloud2.read_points_numpy(msg, field_names=('x', 'y', 'z'), skip_nans=True)
    print(stamp_ns, xyz.shape)   # xyz: массив numpy формы (N, 3)
```

## 5. Запись облака точек в PostgreSQL
Каталог `lidar_db` этого репозитория содержит два узла ROS2 — скрипты Python, сборка не нужна:
- `writer.py` — подписывается на `/rslidar_points` и сохраняет каждый кадр в таблицу `frames`;
- `reader.py` — читает кадры из таблицы `frames` и публикует их в топик ROS2 для RViz2.

Одна строка таблицы `frames` — один кадр: время кадра, `frame_id`, описание полей точек
(`fields`, JSON) и массив точек `data` без изменений (`bytea`, как в `PointCloud2.data`).
Отдельная строка на каждую точку не используется: это ~576 000 строк в секунду.

Объём такой же, как у rosbag2 без сжатия: ~32 GB в час. Для уменьшения объёма сохраняйте
каждый N-й кадр (параметр `every_n`, шаг 5.2).

База данных и оба узла работают на "server". RViz2 работает на "client" и получает облако
точек по ROS2, как в разделе 3.

### 5.1 Установка PostgreSQL и создание базы данных на "server"
```sh
sudo apt install postgresql python3-psycopg2
sudo -u postgres createuser $USER      # пользователь PostgreSQL с именем пользователя системы
sudo -u postgres createdb -O $USER lidar
psql lidar -c 'SELECT version();'
```
Ожидается: строка с версией PostgreSQL (в Ubuntu 24.04 — 16). Подключение идёт через
локальный сокет без пароля, поэтому строка подключения узлов — `dbname=lidar`.

### 5.2 Запись (writer.py)
Драйвер запущен (шаг 1.4). Запись идёт, пока открыт терминал. По SSH запускайте её в tmux.
```sh
source /opt/ros/jazzy/setup.bash
python3 ~/robot2/lidar_db/writer.py
```
При первом запуске узел создаёт таблицу `frames` и индекс по времени кадра.

Ожидается в выводе:
```
saving every 1 frame(s) from /rslidar_points to database "lidar"
received 100 frames, saved 100
```
Строка `received ... saved ...` выводится раз в 10 с. Если `received` растёт медленнее
~100 за 10 с, база данных не успевает записывать кадры, и часть кадров теряется.

Параметры (`--ros-args -p <имя>:=<значение>`):
- `dsn` — строка подключения к PostgreSQL, по умолчанию `dbname=lidar`.
  Пример для базы данных на другой машине: `"host=<IP> dbname=lidar user=<user> password=<пароль>"`;
- `topic` — топик облака точек, по умолчанию `/rslidar_points`;
- `every_n` — сохранять каждый N-й кадр, по умолчанию `1` (все кадры).

Пример: сохранять 1 кадр в секунду:
```sh
python3 ~/robot2/lidar_db/writer.py --ros-args -p every_n:=10
```

Остановка записи: `Ctrl+C`.

### 5.3 Проверка записи
```sh
psql lidar -c "SELECT count(*), min(stamp), max(stamp),
               pg_size_pretty(pg_total_relation_size('frames')) FROM frames;"
```
Ожидается: число кадров, время первого и последнего кадра, размер таблицы.

### 5.4 Воспроизведение в RViz2 (reader.py)
На "server" остановите драйвер: `reader.py` публикует в тот же топик `/rslidar_points`,
иначе в топик публикуют два источника. Другой топик задаётся параметром `topic`.

На "server":
```sh
source /opt/ros/jazzy/setup.bash
python3 ~/robot2/lidar_db/reader.py
```
Ожидается: `publishing <N> frames to /rslidar_points at 10.0 Hz`. После последнего кадра
узел завершается.

На "client" запустите RViz2, как в разделе 3:
```sh
source /opt/ros/jazzy/setup.bash
rviz2 -d rslidar_sdk/rviz/rviz2.rviz
```

Параметры (`--ros-args -p <имя>:=<значение>`):
- `dsn` — строка подключения к PostgreSQL, по умолчанию `dbname=lidar`;
- `topic` — топик для публикации, по умолчанию `/rslidar_points`;
- `rate` — частота публикации кадров в Hz, по умолчанию `10.0`. Значение — число
  с точкой (`5.0`, не `5`), иначе узел завершается с ошибкой типа параметра;
- `loop` — воспроизводить по кругу, по умолчанию `false`;
- `start`, `end` — интервал времени кадров, по умолчанию все кадры. Формат — время
  PostgreSQL, например `"2026-09-28 14:00:00"` (часовой пояс сервера PostgreSQL).

Пример: кадры за 5 минут по кругу, в 2 раза медленнее:
```sh
python3 ~/robot2/lidar_db/reader.py --ros-args \
  -p start:="2026-09-28 14:00:00" -p end:="2026-09-28 14:05:00" \
  -p rate:=5.0 -p loop:=true
```

Время в заголовке кадра (`header.stamp`) — исходное время записи с точностью
до микросекунды.

### 5.5 Удаление старых кадров
```sh
psql lidar -c "DELETE FROM frames WHERE stamp < now() - interval '7 days';"
psql lidar -c "VACUUM frames;"
```
`VACUUM` освобождает место для новых кадров, но не уменьшает файлы базы данных на диске.
Вернуть место операционной системе: `VACUUM FULL frames;` (таблица блокируется на время
выполнения).

## Необязательно: Cyclone DDS
С Fast DDS частота кадров больших облаков точек может падать (см. документ SDK выше).
Cyclone DDS часто решает проблему. Реализация DDS должна быть одинаковой на всех машинах.

На "server" и "client":
```sh
sudo apt install ros-jazzy-rmw-cyclonedds-cpp
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp    # добавить в ~/.bashrc
ros2 daemon stop                                # перезапуск демона с новой реализацией DDS
```
Затем перезапустите драйвер на "server" (шаг 1.4) в терминале с этой переменной.

Дополнительно можно увеличить сетевые буферы ядра (на обеих машинах), это
уменьшает потери больших сообщений. Настройки применяются ко всей системе:
- `rmem_max` — верхний предел буфера приёма UDP-сокета, который может запросить
  программа (64 MB, около 70 кадров Helios). Сам по себе память не выделяет;
- `rmem_default` — буфер приёма по умолчанию для каждого нового сокета (8 MB);
- `ipfrag_*` — сборка фрагментированных UDP-пакетов: время ожидания фрагментов (3 с)
  и предел памяти на их сборку (128 MB).
```sh
sudo tee /etc/sysctl.d/60-ros2-dds.conf <<EOF
net.core.rmem_max=67108864
net.core.rmem_default=8388608
net.ipv4.ipfrag_time=3
net.ipv4.ipfrag_high_thresh=134217728
EOF
sudo sysctl --system
```

## Альтернатива: драйвер в Docker
`Dockerfile` и `docker-compose.yaml` собирают и запускают тот же драйвер в контейнере
с ROS2 Jazzy (сеть хоста, `config/config.yaml` подключён как volume).
Для основной схемы работы Docker не нужен.

Установка Docker (Ubuntu):
```sh
# https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# Запуск сервиса docker
sudo systemctl start docker
# Включение автозапуска сервиса docker при старте системы
sudo systemctl enable docker
# Только для машины с графическим интерфейсом (RViz2 внутри контейнера):
# установка утилит графического сервера
sudo apt install x11-xserver-utils
# и разрешение docker доступ к графическому серверу
xhost +local:docker
```

Запуск и проверка (вместо шагов 1.4–1.6):
```sh
docker compose build
docker compose up -d
docker compose logs -f lidar                  # вывод драйвера, как в шаге 1.4
ros2 topic hz /rslidar_points                 # проверки шага 1.5 из ROS2 хоста
docker compose restart lidar                  # после изменения config/config.yaml
docker compose down                           # остановка
```
Для Cyclone DDS выполните `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` перед
`docker compose up -d --force-recreate`: контейнер берёт переменную из окружения.
