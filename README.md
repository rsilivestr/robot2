# Подключение к лидару RoboSense Helios

## Инициализация git-подмодулей (SDK, драйвер, сообщения)
```bash
git submodule update --init --recursive
```

## Установка Docker
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
# Установка утилит графического сервера
sudo apt install x11-xserver-utils
# Разрешение docker доступ к графическому серверу
xhost +local:docker
```
