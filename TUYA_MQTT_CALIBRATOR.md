# Tuya MQTT Calibrator

Скрипт `tuya_mqtt_calibrator.py` запускается на роутере и делает одно действие:

- принимает MQTT-команду с температурой
- читает текущее значение температуры и калибровки у Tuya-устройства
- пересчитывает `dps[20]`
- отправляет новую калибровку в устройство

Поддерживаемые payload:

```json
{"Temperature": 23.5}
```

Или просто число:

```text
23.5
```

## Что нужно заранее

- на роутере уже работает MQTT-брокер `mosquitto`
- Tuya-устройство доступно по локальному IP
- известны:
  - `TUYA_DEVICE_ID`
  - `TUYA_LOCAL_KEY`
  - `TUYA_IP`
- на роутере установлен Entware
- на роутере есть Python
- USB-накопитель с `/opt` должен быть исправен и смонтирован без ошибок

## Где лежит скрипт

Рекомендуемый путь на роутере:

```sh
/opt/scripts/tuya_mqtt_calibrator.py
```

## Установка

### 1. Подключиться к роутеру

Эти команды выполняйте по очереди, не одной вставкой:

```sh
ssh admin@192.168.1.1
```

Потом:

```sh
sh
```

Потом:

```sh
exec sh
```

### 2. Установить зависимости

Проверьте Python:

```sh
python3 --version
```

Если `python3` нет, попробуйте:

```sh
python --version
```

Установить Python и `pip` при необходимости:

```sh
opkg update
opkg install python3 python3-pip
```

Для `paho-mqtt`:

```sh
python3 -m pip install paho-mqtt
```

Для `tinytuya` на Keenetic лучше использовать рабочую схему без сборки `cryptography` через Rust:

```sh
opkg install python3-cryptography
python3 -m pip install tinytuya --no-deps
```

Предупреждение про отсутствие `requests` для cloud-функций можно игнорировать.
Для локального сценария через `local_key` это не мешает работе.

### 3. Создать каталог для скрипта

```sh
mkdir -p /opt/scripts
```

### 4. Создать файл прямо на роутере

Практически для вашего сценария удобнее создавать файл сразу на роутере через `cat > ... <<'EOF'`, а не через `scp`.
`scp` нужно запускать с компьютера, а не внутри SSH-сессии роутера.

### 5. Отредактировать настройки в скрипте

Откройте файл:

```sh
vi /opt/scripts/tuya_mqtt_calibrator.py
```

Проверьте и при необходимости измените:

```python
MQTT_HOST = "192.168.1.1"
MQTT_PORT = 1883
MQTT_TOPIC = "tuya/calibrate/set"
MQTT_STATUS_TOPIC = "tuya/calibrate/status"

TUYA_DEVICE_ID = "..."
TUYA_LOCAL_KEY = "..."
TUYA_IP = "..."
TUYA_VERSION = 3.3

TUYA_TEMP_DPS = "3"
TUYA_CALIBRATION_DPS = "20"
TUYA_CALIBRATION_MIN = -99
TUYA_CALIBRATION_MAX = 99
REFERENCE_TEMP_MIN = 10.0
REFERENCE_TEMP_MAX = 35.0
```

### 6. Тестовый запуск без MQTT

Эта команда сразу применит калибровку для тестовой температуры:

```sh
python3 /opt/scripts/tuya_mqtt_calibrator.py 23.5
```

Если у вас используется `python`:

```sh
python /opt/scripts/tuya_mqtt_calibrator.py 23.5
```

### 7. Запуск в режиме MQTT

```sh
python3 /opt/scripts/tuya_mqtt_calibrator.py
```

Скрипт подпишется на тему:

```text
tuya/calibrate/set
```

## Как отправлять команды

### Вариант 1. JSON

```sh
mosquitto_pub -h 192.168.1.1 -t tuya/calibrate/set -m "{\"Temperature\":23.5}"
```

### Вариант 2. Просто число

```sh
mosquitto_pub -h 192.168.1.1 -t tuya/calibrate/set -m "23.5"
```

## Автозапуск скрипта

Создайте файл:

```sh
vi /opt/etc/init.d/S99tuya-mqtt-calibrator
```

Содержимое:

```sh
#!/opt/bin/sh

PYTHON_BIN=/opt/bin/python3
SCRIPT=/opt/scripts/tuya_mqtt_calibrator.py
PIDFILE=/opt/var/run/tuya_mqtt_calibrator.pid

case "$1" in
  start)
    echo "Starting tuya_mqtt_calibrator"
    mkdir -p /opt/var/run
    sleep 10
    "$PYTHON_BIN" "$SCRIPT" >/dev/null 2>&1 &
    echo $! > "$PIDFILE"
    ;;
  stop)
    echo "Stopping tuya_mqtt_calibrator"
    if [ -f "$PIDFILE" ]; then
      kill "$(cat "$PIDFILE")" 2>/dev/null
      rm -f "$PIDFILE"
    fi
    ;;
  restart)
    "$0" stop
    sleep 1
    "$0" start
    ;;
  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "tuya_mqtt_calibrator is running"
    else
      echo "tuya_mqtt_calibrator is not running"
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
```

Сделайте файл исполняемым:

```sh
chmod +x /opt/etc/init.d/S99tuya-mqtt-calibrator
```

Запуск:

```sh
/opt/etc/init.d/S99tuya-mqtt-calibrator start
```

Проверка:

```sh
/opt/etc/init.d/S99tuya-mqtt-calibrator status
ps | grep tuya_mqtt_calibrator
```

Если нужен режим диагностики, можно временно заменить строку запуска на:

```sh
"$PYTHON_BIN" "$SCRIPT" >> /opt/var/log/tuya_mqtt_calibrator.log 2>&1 &
```

Потом смотреть лог:

```sh
tail -f /opt/var/log/tuya_mqtt_calibrator.log
```

## Обновление

### Обновить код скрипта

На практике у вас обновление удобнее делать прямо на роутере: заменить файл через `cat > /opt/scripts/tuya_mqtt_calibrator.py <<'EOF'`.

После этого перезапустите сервис:

```sh
ssh admin@192.168.1.1
```

Потом:

```sh
sh
```

Потом:

```sh
exec sh
```

И затем:

```sh
/opt/etc/init.d/S99tuya-mqtt-calibrator restart
```

### Обновить Python-зависимости

```sh
exec sh
python3 -m pip install --upgrade tinytuya paho-mqtt
```

## Удаление

### Остановить сервис

```sh
/opt/etc/init.d/S99tuya-mqtt-calibrator stop
```

### Удалить init-скрипт

```sh
rm -f /opt/etc/init.d/S99tuya-mqtt-calibrator
```

### Удалить основной файл

```sh
rm -f /opt/scripts/tuya_mqtt_calibrator.py
```

### При необходимости удалить pid

```sh
rm -f /opt/var/run/tuya_mqtt_calibrator.pid
```

### При необходимости удалить Python-библиотеки

```sh
python3 -m pip uninstall tinytuya paho-mqtt
```

## Быстрая диагностика

Проверить, запущен ли скрипт:

```sh
ps | grep tuya_mqtt_calibrator
```

Проверить MQTT вручную:

```sh
mosquitto_pub -h 192.168.1.1 -t tuya/calibrate/set -m "23.5"
```

Проверить ответный топик:

```sh
mosquitto_sub -h 192.168.1.1 -t tuya/calibrate/status
```

Проверить Tuya вручную без MQTT:

```sh
python3 /opt/scripts/tuya_mqtt_calibrator.py 23.5
```

## Что уже проверено у вас

Подтверждено на вашем роутере:

- `mosquitto` работает на `192.168.1.1:1883`
- `python3` установлен в `/opt/bin/python3`
- `paho-mqtt` установлен
- `python3-cryptography` установлен через `opkg`
- `tinytuya` установлен через `python3 -m pip install tinytuya --no-deps`
- локальная запись в `dps[20]` работает
- MQTT-мост принимает команды и публикует ответ в `tuya/calibrate/status`

Критично:

- если USB-накопитель с `/opt` поврежден или не монтируется, ни `mosquitto`, ни Python-скрипты из Entware нормально не стартуют
- ошибки `EXT4-fs`, `JBD2`, `input/output error`, `failed to mount` означают проблему с носителем, а не с кодом
