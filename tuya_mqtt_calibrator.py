#!/usr/bin/env python3
"""
Tuya MQTT Calibrator (Enhanced Edition)
- Listens to MQTT temperature reference payloads and calibrates Tuya thermostats/sensors via Local LAN (tinytuya).
- Supports external config.json with graceful built-in fallback.
- Auto-reconnects to MQTT broker if broker reboots or network is delayed.
- Supports read-only query topic (tuya/calibrate/get) to fetch status without altering calibration.
- Sets Last Will and Testament (LWT) for availability tracking in Home Assistant / MQTT dashboards.
- Status published with retain=True so current values are immediately available upon client restart.
- Structured rotating file logging.
"""

import argparse
import contextlib
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from typing import Any, Optional

import paho.mqtt.client as mqtt

# Suppress banner from tinytuya if imported
with contextlib.redirect_stdout(io.StringIO()):
    import tinytuya


DEFAULT_CONFIG: dict[str, Any] = {
    "mqtt": {
        "host": "192.168.1.1",
        "port": 1883,
        "topic_set": "tuya/calibrate/set",
        "topic_get": "tuya/calibrate/get",
        "topic_status": "tuya/calibrate/status",
        "topic_availability": "tuya/calibrate/availability",
        "user": "",
        "password": "",
        "retain_status": True,
        "qos": 1,
    },
    "tuya": {
        "device_id": "bf8b29a44ecc9a2477tbgd",
        "local_key": "=*R-Krigxx/Jka5i",
        "ip": "192.168.1.92",
        "version": 3.3,
        "socket_timeout": 5,
    },
    "dps": {
        "temp_dps": "3",
        "work_state_dps": "5",
        "calibration_dps": "20",
        "calibration_min": -99,
        "calibration_max": 99,
        "reference_temp_min": 10.0,
        "reference_temp_max": 35.0,
    },
    "logging": {
        "level": "INFO",
        "log_file": "/opt/var/log/tuya_mqtt_calibrator.log",
    },
}


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merges override dictionary into base."""
    result = dict(base)
    for key, val in override.items():
        if isinstance(val, dict) and key in result and isinstance(result[key], dict):
            result[key] = merge_dicts(result[key], val)
        else:
            result[key] = val
    return result


def load_config(custom_path: Optional[str] = None) -> dict[str, Any]:
    """
    Loads config from file if present, falling back to DEFAULT_CONFIG.
    Checks:
    1. custom_path (CLI argument or env var)
    2. ./config.json (same directory as script)
    3. /opt/etc/tuya_mqtt_calibrator.json
    """
    candidates = []
    if custom_path:
        candidates.append(custom_path)
    if os.environ.get("TUYA_CONFIG"):
        candidates.append(os.environ["TUYA_CONFIG"])

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(script_dir, "config.json"))
    candidates.append("/opt/etc/tuya_mqtt_calibrator.json")

    for path in candidates:
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logging.info(f"Loaded configuration from: {path}")
                    return merge_dicts(DEFAULT_CONFIG, data)
            except Exception as e:
                logging.warning(f"Failed to parse config file {path}: {e}")

    return DEFAULT_CONFIG


def setup_logging(cfg: dict[str, Any]) -> None:
    log_cfg = cfg.get("logging", {})
    level_name = log_cfg.get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    log_file = log_cfg.get("log_file")
    if log_file:
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file, maxBytes=512 * 1024, backupCount=2, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning(f"Could not enable file logging at {log_file}: {e}")


def create_tuya_device(cfg: dict[str, Any]) -> tinytuya.OutletDevice:
    t_cfg = cfg["tuya"]
    device = tinytuya.OutletDevice(
        dev_id=t_cfg["device_id"],
        address=t_cfg["ip"],
        local_key=t_cfg["local_key"],
        version=float(t_cfg["version"]),
    )
    device.set_socketTimeout(t_cfg.get("socket_timeout", 5))
    return device


def parse_temperature_payload(payload: bytes) -> float:
    text = payload.decode("utf-8", errors="replace").strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for k in ("Temperature", "temperature", "temp", "reference_temp", "value"):
                if k in data and isinstance(data[k], (int, float)):
                    return float(data[k])
        if isinstance(data, (int, float)):
            return float(data)
    except json.JSONDecodeError:
        pass

    return float(text)


def get_tuya_status(cfg: dict[str, Any]) -> dict[str, Any]:
    """Read-only query: returns current temperature, work state, and calibration offset."""
    dps_cfg = cfg["dps"]
    device = create_tuya_device(cfg)
    try:
        status = device.status()
        if "dps" not in status:
            raise RuntimeError(f"Tuya status without dps: {status}")

        dps = status["dps"]
        tuya_temp = dps.get(dps_cfg["temp_dps"])
        work_state = dps.get(dps_cfg["work_state_dps"])
        current_calibration = dps.get(dps_cfg["calibration_dps"])

        return {
            "action": "status_query",
            "tuya_temp_raw": tuya_temp,
            "tuya_temp_c": tuya_temp / 10 if isinstance(tuya_temp, (int, float)) else None,
            "work_state": work_state,
            "current_calibration": current_calibration,
            "raw_dps": dps,
        }
    finally:
        with contextlib.suppress(Exception):
            device.close()


def calibrate_tuya(reference_temp: float, cfg: dict[str, Any]) -> dict[str, Any]:
    dps_cfg = cfg["dps"]
    ref_min = dps_cfg["reference_temp_min"]
    ref_max = dps_cfg["reference_temp_max"]
    if not (ref_min <= reference_temp <= ref_max):
        raise ValueError(
            f"Reference temperature {reference_temp} is out of allowed range "
            f"{ref_min}..{ref_max}"
        )

    device = create_tuya_device(cfg)
    try:
        status = device.status()
        if "dps" not in status:
            raise RuntimeError(f"Tuya status without dps: {status}")

        dps = status["dps"]
        tuya_temp = dps.get(dps_cfg["temp_dps"])
        work_state = dps.get(dps_cfg["work_state_dps"])
        current_calibration = dps.get(dps_cfg["calibration_dps"])

        if tuya_temp is None or current_calibration is None:
            raise RuntimeError(f"Required DPS values not found in device status: {dps}")

        requested_calibration = round((reference_temp * 10) - (tuya_temp - current_calibration))
        cal_min = dps_cfg["calibration_min"]
        cal_max = dps_cfg["calibration_max"]
        new_calibration = max(cal_min, min(cal_max, requested_calibration))
        changed = new_calibration != current_calibration
        clamped = new_calibration != requested_calibration

        result: dict[str, Any] = {
            "action": "calibrate",
            "reference_temp": reference_temp,
            "tuya_temp_raw": tuya_temp,
            "tuya_temp_c": tuya_temp / 10 if isinstance(tuya_temp, (int, float)) else None,
            "work_state": work_state,
            "current_calibration": current_calibration,
            "requested_calibration": requested_calibration,
            "new_calibration": new_calibration,
            "changed": changed,
            "clamped": clamped,
        }

        if changed:
            result["set_result"] = device.set_value(int(dps_cfg["calibration_dps"]), new_calibration)

        return result
    finally:
        with contextlib.suppress(Exception):
            device.close()


def run_mqtt_bridge(cfg: dict[str, Any]) -> None:
    m_cfg = cfg["mqtt"]
    status_topic = m_cfg.get("topic_status", "tuya/calibrate/status")
    set_topic = m_cfg.get("topic_set", "tuya/calibrate/set")
    get_topic = m_cfg.get("topic_get", "tuya/calibrate/get")
    avail_topic = m_cfg.get("topic_availability", "tuya/calibrate/availability")
    qos = int(m_cfg.get("qos", 1))
    retain_status = bool(m_cfg.get("retain_status", True))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    if m_cfg.get("user"):
        client.username_pw_set(m_cfg["user"], m_cfg.get("password", ""))

    # LWT: publish "offline" if connection drops abnormally
    client.will_set(avail_topic, payload="offline", qos=qos, retain=True)

    def on_connect(
        c: mqtt.Client,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any = None,
    ) -> None:
        if hasattr(reason_code, "is_failure") and reason_code.is_failure:
            logging.error(f"[MQTT] Connection failed with reason: {reason_code}")
            return

        logging.info(f"[MQTT] Connected successfully to {m_cfg['host']}:{m_cfg['port']} (reason: {reason_code})")
        # Publish availability online
        c.publish(avail_topic, payload="online", qos=qos, retain=True)

        # Subscribe to calibration command topic
        c.subscribe(set_topic, qos=qos)
        logging.info(f"[MQTT] Subscribed to set topic: {set_topic}")

        # Subscribe to read-only status topic
        if get_topic:
            c.subscribe(get_topic, qos=qos)
            logging.info(f"[MQTT] Subscribed to read-only query topic: {get_topic}")

    def on_disconnect(
        _c: mqtt.Client,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any = None,
    ) -> None:
        logging.warning(f"[MQTT] Disconnected from broker: {reason_code}")

    def on_message(c: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
        raw_text = msg.payload.decode("utf-8", errors="replace").strip()
        logging.info(f"[MQTT] Message received: topic={msg.topic} payload={raw_text!r}")

        # Check if read-only get query
        is_get_query = (msg.topic == get_topic) or (raw_text.lower() in ("get", "status", "read", ""))
        if not is_get_query and raw_text.startswith("{"):
            try:
                parsed = json.loads(raw_text)
                if parsed.get("action") in ("get", "status") or parsed.get("get") is True:
                    is_get_query = True
            except Exception:
                pass

        try:
            if is_get_query:
                result = get_tuya_status(cfg)
                logging.info(f"[Tuya] Status read: temp={result.get('tuya_temp_c')}°C, cal={result.get('current_calibration')}")
            else:
                reference_temp = parse_temperature_payload(msg.payload)
                result = calibrate_tuya(reference_temp, cfg)
                logging.info(
                    f"[Tuya] Calibration calculated: ref={reference_temp}°C, "
                    f"cal={result.get('new_calibration')} (changed={result.get('changed')})"
                )

            c.publish(status_topic, json.dumps(result, ensure_ascii=False), qos=qos, retain=retain_status)
        except Exception as exc:
            error_payload = {
                "error": str(exc),
                "payload": raw_text,
            }
            logging.error(f"[Tuya Error] {exc}")
            c.publish(status_topic, json.dumps(error_payload, ensure_ascii=False), qos=qos, retain=False)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    logging.info(f"[MQTT] Connecting asynchronously to {m_cfg['host']}:{m_cfg['port']}...")
    client.connect_async(m_cfg["host"], int(m_cfg["port"]), keepalive=60)

    logging.info(f"[MQTT] Waiting for payloads on {set_topic}")
    logging.info(f"[MQTT] Accepted payloads: {{\"Temperature\": 23.5}}, plain '23.5', or get on {get_topic}")
    logging.info(f"[MQTT] Status topic: {status_topic} (retain={retain_status})")
    logging.info(f"[MQTT] Availability topic: {avail_topic}")

    # loop_forever with retry_first_connection ensures it waits for Mosquitto at router boot
    client.loop_forever(retry_first_connection=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tuya MQTT Calibrator daemon")
    parser.add_argument("--config", "-c", help="Path to custom config.json")
    parser.add_argument("--get", "-g", action="store_true", help="Perform single read-only status query")
    parser.add_argument("temperature", nargs="?", type=float, help="Single-shot calibration reference temperature")
    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg)

    if args.get:
        res = get_tuya_status(cfg)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.temperature is not None:
        res = calibrate_tuya(args.temperature, cfg)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        run_mqtt_bridge(cfg)


if __name__ == "__main__":
    main()
