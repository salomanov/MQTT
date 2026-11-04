#!/usr/bin/env python3
"""
MQTT Broker Connectivity & Health Test
Verifies TCP socket and pub/sub roundtrip.
"""

import argparse
import json
import socket
import sys
import time
import paho.mqtt.client as mqtt

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def test_broker(host: str, port: int, topic: str, user: str, secret: str) -> bool:
    print(f"=== Проверка доступности MQTT-брокера {host}:{port} ===")

    # 1. Проверка TCP сокета
    try:
        s = socket.create_connection((host, port), timeout=3)
        s.close()
        print(f"[OK] Порт {port} открыт (TCP handshake успешен).")
    except Exception as e:
        print(f"[FAIL] Не удалось подключиться к порту {port}: {e}")
        return False

    # 2. Проверка публикации и эхо-ответа
    received = []

    def on_connect(c, userdata, flags, rc, properties=None):
        c.subscribe(topic)
        payload = json.dumps({"test": "ping", "timestamp": time.time()})
        c.publish(topic, payload)

    def on_message(c, userdata, msg):
        received.append(msg.payload.decode("utf-8", errors="replace"))
        c.disconnect()

    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    else:
        client = mqtt.Client()

    if user:
        client.username_pw_set(user, secret)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(host, port, 10)
        client.loop_start()
        for _ in range(40):
            if received:
                break
            time.sleep(0.1)
        client.loop_stop()
        client.disconnect()

        if received:
            print(f"[OK] Успешная публикация и подписка! Получено: {received[0]}")
            print("[SUCCESS] MQTT-брокер полностью исправен и отвечает на запросы!")
            return True
        else:
            print("[FAIL] Сообщение отправлено, но эхо не получено в течение 4 секунд.")
            return False
    except Exception as e:
        print(f"[FAIL] Ошибка взаимодействия по протоколу MQTT: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test MQTT broker connectivity")
    parser.add_argument("--host", default="192.168.1.1", help="Broker IP")
    parser.add_argument("--port", type=int, default=1883, help="Broker Port")
    parser.add_argument("--topic", default="router/test/ping", help="Test Topic")
    parser.add_argument("--user", default="", help="MQTT Username")
    parser.add_argument("--password", default="", help="MQTT Password")
    args = parser.parse_args()

    success = test_broker(args.host, args.port, args.topic, args.user, args.password)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
