#!/usr/bin/env python3
"""
Mosquitto Configuration Backup for KeeneticOS / Entware
Downloads current configuration files from router to a local timestamped backup folder.
"""

import argparse
import base64
import os
import sys
import time
from datetime import datetime
import paramiko

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def backup(host: str, port: int, user: str, secret: str, target_dir: str) -> bool:
    print(f"=== Резервное копирование конфигурации Mosquitto с {host}:{port} ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            host,
            port=port,
            username=user,
            password=secret,
            timeout=8,
            look_for_keys=False,
            allow_agent=False,
        )

        os.makedirs(target_dir, exist_ok=True)

        # Список файлов для скачивания
        cmd = "find /opt/etc/mosquitto -type f -not -name '*.db' 2>/dev/null"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        files = [line.strip() for line in stdout.readlines() if line.strip()]

        if not files:
            print("[WARNING] Не найдено файлов в /opt/etc/mosquitto/")
            return False

        for rpath in files:
            rel = os.path.relpath(rpath, "/opt/etc/mosquitto")
            lpath = os.path.join(target_dir, rel)
            os.makedirs(os.path.dirname(lpath), exist_ok=True)

            read_cmd = f"/opt/bin/base64 '{rpath}' 2>/dev/null"
            stdin, stdout, stderr = ssh.exec_command(read_cmd)
            b64_data = stdout.read().decode("ascii").replace("\n", "").replace("\r", "")
            if b64_data:
                with open(lpath, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                print(f"[OK] Сохранен: {rel}")

        print(f"[SUCCESS] Резервная копия успешно создана в: {target_dir}")
        return True

    except Exception as e:
        print(f"[FAIL] Ошибка резервного копирования: {e}")
        return False
    finally:
        ssh.close()


def main():
    parser = argparse.ArgumentParser(description="Backup Mosquitto config from Keenetic router")
    parser.add_argument("--host", default="192.168.1.1", help="Router IP")
    parser.add_argument("--port", type=int, default=222, help="SSH Port")
    parser.add_argument("--user", default="root", help="SSH User")
    parser.add_argument("--password", default="keenetic", help="SSH Password")
    parser.add_argument("--target-dir", default=None, help="Path to backup target directory")
    args = parser.parse_args()

    if not args.target_dir:
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = os.path.join(repo_dir, "backups", f"backup_{timestamp}")
    else:
        target_dir = args.target_dir

    success = backup(args.host, args.port, args.user, args.password, target_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
