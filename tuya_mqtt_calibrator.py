import contextlib
import io
import json
import sys
from typing import Any

import paho.mqtt.client as mqtt

with contextlib.redirect_stdout(io.StringIO()):
    import tinytuya


# === MQTT ===
MQTT_HOST = "192.168.1.1"
MQTT_PORT = 1883
MQTT_TOPIC = "tuya/calibrate/set"
MQTT_STATUS_TOPIC = "tuya/calibrate/status"

# === Tuya ===
TUYA_DEVICE_ID = "bf8b29a44ecc9a2477tbgd"
TUYA_LOCAL_KEY = "=*R-Krigxx/Jka5i"
TUYA_IP = "192.168.1.92"
TUYA_VERSION = 3.3

# === Tuya DPS ===
TUYA_TEMP_DPS = "3"
TUYA_WORK_STATE_DPS = "5"
TUYA_CALIBRATION_DPS = "20"
TUYA_CALIBRATION_MIN = -99
TUYA_CALIBRATION_MAX = 99
REFERENCE_TEMP_MIN = 10.0
REFERENCE_TEMP_MAX = 35.0


def create_tuya_device() -> tinytuya.OutletDevice:
    device = tinytuya.OutletDevice(
        dev_id=TUYA_DEVICE_ID,
        address=TUYA_IP,
        local_key=TUYA_LOCAL_KEY,
        version=TUYA_VERSION,
    )
    device.set_socketTimeout(5)
    return device


def parse_temperature_payload(payload: bytes) -> float:
    text = payload.decode("utf-8").strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict) and "Temperature" in data:
            return float(data["Temperature"])
        if isinstance(data, (int, float)):
            return float(data)
    except json.JSONDecodeError:
        pass

    return float(text)


def calibrate_tuya(reference_temp: float) -> dict[str, Any]:
    if not REFERENCE_TEMP_MIN <= reference_temp <= REFERENCE_TEMP_MAX:
        raise ValueError(
            f"Reference temperature {reference_temp} is out of allowed range "
            f"{REFERENCE_TEMP_MIN}..{REFERENCE_TEMP_MAX}"
        )

    device = create_tuya_device()
    status = device.status()

    if "dps" not in status:
        raise RuntimeError(f"Tuya status without dps: {status}")

    dps = status["dps"]
    tuya_temp = dps.get(TUYA_TEMP_DPS)
    work_state = dps.get(TUYA_WORK_STATE_DPS)
    current_calibration = dps.get(TUYA_CALIBRATION_DPS)

    if tuya_temp is None or current_calibration is None:
        raise RuntimeError(f"Required DPS values not found: {dps}")

    requested_calibration = round((reference_temp * 10) - (tuya_temp - current_calibration))
    new_calibration = max(TUYA_CALIBRATION_MIN, min(TUYA_CALIBRATION_MAX, requested_calibration))
    changed = new_calibration != current_calibration
    clamped = new_calibration != requested_calibration

    result: dict[str, Any] = {
        "reference_temp": reference_temp,
        "tuya_temp_raw": tuya_temp,
        "tuya_temp_c": tuya_temp / 10,
        "work_state": work_state,
        "current_calibration": current_calibration,
        "requested_calibration": requested_calibration,
        "new_calibration": new_calibration,
        "changed": changed,
        "clamped": clamped,
    }

    if changed:
        result["set_result"] = device.set_value(int(TUYA_CALIBRATION_DPS), new_calibration)

    return result


def on_connect(
    client: mqtt.Client,
    _userdata: Any,
    _flags: Any,
    reason_code: Any,
    _properties: Any = None,
) -> None:
    print(f"[MQTT] connected: reason_code={reason_code}")
    client.subscribe(MQTT_TOPIC)
    print(f"[MQTT] subscribed: {MQTT_TOPIC}")


def on_message(client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
    print(f"[MQTT] message: topic={msg.topic} payload={msg.payload!r}")

    try:
        reference_temp = parse_temperature_payload(msg.payload)
        result = calibrate_tuya(reference_temp)
        print("[Tuya] calibration result:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        client.publish(MQTT_STATUS_TOPIC, json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        error_payload = {"error": str(exc), "payload": msg.payload.decode("utf-8", "replace")}
        print(f"[ERROR] {exc}")
        client.publish(MQTT_STATUS_TOPIC, json.dumps(error_payload, ensure_ascii=False))


def run_mqtt_bridge() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    print(f"[MQTT] waiting for payloads on {MQTT_HOST}:{MQTT_PORT} topic={MQTT_TOPIC}")
    print('[MQTT] accepted payloads: {"Temperature": 23.5} or plain "23.5"')
    print(f"[MQTT] status topic: {MQTT_STATUS_TOPIC}")
    client.loop_forever()


def run_once_from_cli(reference_temp: float) -> None:
    result = calibrate_tuya(reference_temp)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_once_from_cli(float(sys.argv[1]))
    else:
        run_mqtt_bridge()
