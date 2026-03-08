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

Остановка:

```sh
/opt/etc/init.d/S50mosquitto stop
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
