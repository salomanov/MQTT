# MQTT на Xiaomi R3G v1 (KeeneticOS 5) с nfqws2

Ниже инструкция для KeeneticOS 5 через Entware (`opkg` в `/opt`).
`nfqws2` с MQTT обычно не конфликтует.

Важно: команды `ssh admin@192.168.1.1`, `sh`, `exec sh`, `ps | grep mosquitto` и похожие не вставляйте одной пачкой.
Их нужно выполнять по очереди, дожидаясь нового приглашения в терминале после каждой команды.

## Установка MQTT

Подключение:

```sh
ssh admin@192.168.1.1
```

Если SSH на нестандартном порту:

```sh
ssh admin@192.168.1.1 -p 222
```

После входа сначала перейдите из `(config)>` в `(show)>`:

```sh
sh
```

То есть порядок такой:

```sh
ssh admin@192.168.1.1
```

Потом, уже после входа на роутер:

```sh
sh
```

И только потом:

```sh
exec sh
```

Обновить индекс пакетов Entware:

```sh
opkg update
```

Установить брокер и клиент:

```sh
opkg install mosquitto-ssl mosquitto-client-ssl
```

Проверить, какие пакеты `mosquitto` доступны:

```sh
opkg list | grep mosquitto
```

Фактически у вас установились:

- `mosquitto-ssl`
- `mosquitto-client-ssl`

## Запуск и автозапуск

На Keenetic с Entware сервис обычно запускается скриптом в `/opt/etc/init.d`.
Проверьте имя скрипта:

```sh
ls /opt/etc/init.d | grep -i mosq
```

Обычно запуск такой:

```sh
/opt/etc/init.d/S80mosquitto start
```

Перезапуск:

```sh
/opt/etc/init.d/S80mosquitto restart
```

Остановка:

```sh
/opt/etc/init.d/S80mosquitto stop
```

Проверка статуса процесса:

```sh
ps | grep mosquitto
```

Эту команду выполняйте только после входа на роутер, `sh`, а затем `exec sh`.

### Автозапуск через Entware

На Keenetic автозапуск Entware-сервисов обычно работает, если USB-накопитель с `/opt` успешно смонтирован и включен запуск скриптов из `/opt/etc/init.d`.
У вас это уже подтверждено: после повторного входа `mosquitto` был запущен автоматически.

Проверка после перезагрузки роутера:

```sh
ps | grep mosquitto
```

И отдельно:

```sh
netstat -lntp | grep 1883
```

Если видите процесс `mosquitto` и порт `1883` в режиме `LISTEN`, автозапуск работает.

Если после перезагрузки роутера сервисы из `/opt` не стартуют, проверьте состояние USB-накопителя и файловой системы.
При ошибках вида `EXT4-fs`, `JBD2`, `failed to mount`, `input/output error` проблема уже не в `mosquitto`, а в поврежденном разделе с Entware.

Если процесса нет, можно добавить запуск в пользовательский скрипт Keenetic.
Практический вариант: вызвать Entware-скрипт после старта системы.

Пример команды для пользовательского старта:

```sh
/opt/etc/init.d/S80mosquitto start
```

Где именно добавить этот вызов, зависит от того, как у вас настроены пользовательские скрипты в KeeneticOS 5.
Смысл один: после монтирования `/opt` должен выполниться старт `mosquitto`.

## Настройка логина и пароля

Для постоянной работы не оставляйте открытый MQTT без авторизации.

Создайте каталог для конфигурации и паролей:

```sh
mkdir -p /opt/etc/mosquitto
mkdir -p /opt/var/lib/mosquitto
```

Создайте файл паролей:

```sh
mosquitto_passwd -c /opt/etc/mosquitto/passwd mqttuser
```

Команда попросит ввести пароль для пользователя `mqttuser`.

Минимальный конфиг `/opt/etc/mosquitto/mosquitto.conf`:

```conf
listener 1883
allow_anonymous false
password_file /opt/etc/mosquitto/passwd
persistence true
persistence_location /opt/var/lib/mosquitto/
```

Если файл уже есть, отредактируйте его:

```sh
vi /opt/etc/mosquitto/mosquitto.conf
```

После изменения конфига перезапустите сервис:

```sh
/opt/etc/init.d/S80mosquitto restart
```

Проверка входа с логином и паролем:

Подписка:

```sh
mosquitto_sub -h 127.0.0.1 -p 1883 -u mqttuser -P "YOUR_PASSWORD" -t test/topic
```

Публикация:

```sh
mosquitto_pub -h 127.0.0.1 -p 1883 -u mqttuser -P "YOUR_PASSWORD" -t test/topic -m "MQTT auth works"
```

Если нужно сменить пароль существующего пользователя:

```sh
mosquitto_passwd /opt/etc/mosquitto/passwd mqttuser
```

## Команды удаления MQTT

Остановить сервис:

```sh
/opt/etc/init.d/S80mosquitto stop
```

Удалить пакеты:

```sh
opkg remove mosquitto-client-ssl mosquitto-ssl
```

Если хотите удалить неиспользуемые зависимости:

```sh
opkg remove --autoremove mosquitto-client-ssl mosquitto-ssl
```

## Команды обновления MQTT

Обновить индекс:

```sh
opkg update
```

Обновить только MQTT-пакеты:

```sh
opkg upgrade mosquitto-ssl mosquitto-client-ssl
```

Обновить все пакеты Entware (осторожно на проде):

```sh
opkg upgrade
```

После обновления перезапустить сервис:

```sh
/opt/etc/init.d/S80mosquitto restart
```

## Быстрая проверка

Подписка:

```sh
mosquitto_sub -h 127.0.0.1 -t test/topic
```

Публикация:

```sh
mosquitto_pub -h 127.0.0.1 -t test/topic -m "MQTT works"
```

## Доступ по 192.168.1.1

Сейчас у вас рабочий режим такой: `mosquitto` слушает `0.0.0.0:1883`, и MQTT Explorer уже видит брокер по адресу `192.168.1.1`.

Проверьте текущий конфиг:

```sh
cat /opt/etc/mosquitto/mosquitto.conf
```

Чтобы брокер принимал подключения по адресу роутера `192.168.1.1`, укажите прослушивание на всех IPv4-интерфейсах.

Временный рабочий вариант без пароля:

```conf
listener 1883 0.0.0.0
allow_anonymous true
```

Команда для записи такого конфига:

```sh
cat > /opt/etc/mosquitto/mosquitto.conf <<'EOF'
listener 1883 0.0.0.0
allow_anonymous true
EOF
```

Более безопасный вариант с паролем:

```conf
listener 1883 0.0.0.0
allow_anonymous false
password_file /opt/etc/mosquitto/passwd
persistence true
persistence_location /opt/var/lib/mosquitto/
```

Изменить файл:

```sh
vi /opt/etc/mosquitto/mosquitto.conf
```

После этого перезапустить сервис:

```sh
/opt/etc/init.d/S80mosquitto restart
```

Проверить, что порт слушается не только локально:

```sh
netstat -lntp | grep 1883
```

Если все правильно, вы увидите `0.0.0.0:1883` или прослушивание на адресе `192.168.1.1`.

Проверка с другого устройства в локальной сети:

Без пароля:

```sh
mosquitto_sub -h 192.168.1.1 -p 1883 -t test/topic
```

Во втором окне:

```sh
mosquitto_pub -h 192.168.1.1 -p 1883 -t test/topic -m "test from lan"
```

С паролем:

```sh
mosquitto_sub -h 192.168.1.1 -p 1883 -u mqttuser -P "YOUR_PASSWORD" -t test/topic
```

Во втором окне:

```sh
mosquitto_pub -h 192.168.1.1 -p 1883 -u mqttuser -P "YOUR_PASSWORD" -t test/topic -m "test from lan"
```

Если подключение не проходит, проверьте:

- что в конфиге нет `bind_address 127.0.0.1`
- что `listener` задан как `listener 1883 0.0.0.0`
- что локальный firewall Keenetic не режет доступ из `LAN`
- что пароль в `/opt/etc/mosquitto/passwd` действительно создан

Фактический успешный результат у вас выглядел так:

```sh
ps | grep mosquitto
netstat -lntp | grep 1883
```

Ожидаемый вывод по смыслу:

- процесс `mosquitto` запущен
- порт `1883` слушается на `0.0.0.0`

## MQTT и nfqws2 на Keenetic

По вашей схеме `nfqws2` установлен через Entware, поэтому MQTT тоже логично держать в Entware.
Оба сервиса могут работать одновременно.

Почему обычно нет конфликта:

- `nfqws2` модифицирует трафик по правилам `iptables/NFQUEUE`
- `mosquitto` просто слушает TCP-порт `1883`
- локальный MQTT внутри `LAN` обычно работает отдельно от сценариев, ради которых ставят `nfqws2`

Что рекомендуется:

- использовать MQTT только в локальной сети
- не открывать порт `1883` в интернет без необходимости
- не включать в политику `NFQWS` устройства, для которых важен предсказуемый локальный MQTT
- после установки MQTT проверить, что `nfqws2` и `mosquitto` одновременно запущены

Проверка процессов:

```sh
ps | grep nfqws2
ps | grep mosquitto
```

Это две отдельные команды внутри уже открытой shell-сессии на роутере.

Проверка сервиса `nfqws2`:

```sh
/opt/etc/init.d/S51nfqws2 status
```

Проверка MQTT локально на роутере:

```sh
mosquitto_sub -h 127.0.0.1 -t test/topic
mosquitto_pub -h 127.0.0.1 -t test/topic -m "test from router"
```

Проверка с устройства в локальной сети:

```sh
mosquitto_sub -h 192.168.1.1 -t test/topic
mosquitto_pub -h 192.168.1.1 -t test/topic -m "test from lan"
```

Если локально MQTT работает, а с устройств в сети нет, проверьте:

- на каком адресе слушает `mosquitto`
- открыт ли доступ к порту `1883` внутри `LAN`
- нет ли пользовательских правил, которые заворачивают этот трафик в лишнюю обработку

Если есть сомнения, слушает ли брокер нужный порт:

```sh
netstat -lntp | grep 1883
```

Практический вывод:

`nfqws2` оставляете для обходных сетевых сценариев, а MQTT используете как локальный брокер для датчиков, автоматизации и Home Assistant.
Эти роли друг другу обычно не мешают.

## Сохранить инструкцию в git

В этой папке:

```sh
git init
git add README.md
git commit -m "MQTT guide for KeeneticOS 5 (Xiaomi R3G v1)"
```
