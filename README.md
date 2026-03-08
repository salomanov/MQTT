# MQTT на Xiaomi R3G v1 (KeeneticOS 5) с nfqws2

Ниже инструкция для KeeneticOS 5 через Entware (`opkg` в `/opt`).
`nfqws2` с MQTT обычно не конфликтует.

## Установка MQTT

Подключение:

```sh
ssh admin@192.168.1.1
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

## Запуск и автозапуск

На Keenetic с Entware сервис обычно запускается скриптом в `/opt/etc/init.d`.
Проверьте имя скрипта:

```sh
ls /opt/etc/init.d | grep -i mosq
```

Обычно запуск такой:

```sh
/opt/etc/init.d/S50mosquitto start
```

Перезапуск:

```sh
/opt/etc/init.d/S50mosquitto restart
```

Остановка:

```sh
/opt/etc/init.d/S50mosquitto stop
```

Проверка статуса процесса:

```sh
ps | grep mosquitto
```

### Автозапуск через Entware

На Keenetic автозапуск Entware-сервисов обычно работает, если включен запуск скриптов из `/opt/etc/init.d`.
Проверьте после перезагрузки роутера:

```sh
ps | grep mosquitto
```

Если процесса нет, можно добавить запуск в пользовательский скрипт Keenetic.
Практический вариант: вызвать Entware-скрипт после старта системы.

Пример команды для пользовательского старта:

```sh
/opt/etc/init.d/S50mosquitto start
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
/opt/etc/init.d/S50mosquitto restart
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
/opt/etc/init.d/S50mosquitto stop
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
/opt/etc/init.d/S50mosquitto restart
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

## Сохранить инструкцию в git

В этой папке:

```sh
git init
git add README.md
git commit -m "MQTT guide for KeeneticOS 5 (Xiaomi R3G v1)"
```
