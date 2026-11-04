#!/usr/bin/env python3
"""
Mosquitto Configuration Deployer for KeeneticOS / Entware
Uploads modular configuration to router via SSH base64 stream, validates daemon status,
and performs automatic rollback in case of restart failure.
"""

import argparse
import base64
import os
import sys
import time
import paramiko

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def upload_file_b64(ssh: paramiko.SSHClient, local_path: str, remote_path: str) -> bool:
    with open(local_path, "rb") as f:
        data = f.read()
    b64_str = base64.b64encode(data).decode("ascii")
    cmd = f"/opt/bin/base64 -d <<'EOF' > '{remote_path}'\n{b64_str}\nEOF"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        err = stderr.read().decode("utf-8", errors="replace").strip()
        print(f"[FAIL] Ошибка записи в {remote_path}: {err}")
        return False
    return True


def deploy(
    host: str,
    port: int,
    user: str,
    secret: str,
    configs_dir: str,
    skip_restart: bool,
    accept_new_host_key: bool = True,
) -> bool:
    print(f"=== Развертывание конфигурации Mosquitto на {host}:{port} ===")
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()

    if accept_new_host_key:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())

    connected = False
    for attempt in range(1, 4):
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
            connected = True
            break
        except Exception as e:
            if attempt < 3:
                time.sleep(1)
            else:
                print(f"[FAIL] Ошибка подключения к SSH {host}:{port}: {e}")
                return False

    try:
        # 1. Обеспечить наличие всех необходимых каталогов
        for remote_dir in [
            "/opt/etc/mosquitto",
            "/opt/etc/mosquitto/conf.d",
            "/opt/etc/mosquitto/.backup",
            "/opt/var/lib/mosquitto",
            "/opt/var/log",
        ]:
            stdin, stdout, stderr = ssh.exec_command(f"mkdir -p '{remote_dir}'")
            stdout.channel.recv_exit_status()

        # 2. Создание резервной копии текущей рабочей конфигурации роутера перед изменением
        ssh.exec_command(
            "cp -f /opt/etc/mosquitto/mosquitto.conf /opt/etc/mosquitto/.backup/mosquitto.conf 2>/dev/null || true; "
            "rm -rf /opt/etc/mosquitto/.backup/conf.d 2>/dev/null || true; "
            "cp -rf /opt/etc/mosquitto/conf.d /opt/etc/mosquitto/.backup/conf.d 2>/dev/null || true"
        )

        # 3. Загрузка mosquitto.conf
        local_main_conf = os.path.join(configs_dir, "mosquitto.conf")
        if os.path.isfile(local_main_conf):
            if upload_file_b64(ssh, local_main_conf, "/opt/etc/mosquitto/mosquitto.conf"):
                print("[OK] Загружен /opt/etc/mosquitto/mosquitto.conf")
            else:
                return False
        else:
            print(f"[FAIL] Файл не найден: {local_main_conf}")
            return False

        # 4. Загрузка conf.d/*.conf
        local_conf_d = os.path.join(configs_dir, "conf.d")
        if os.path.isdir(local_conf_d):
            for fname in sorted(os.listdir(local_conf_d)):
                if fname.endswith(".conf"):
                    lpath = os.path.join(local_conf_d, fname)
                    rpath = f"/opt/etc/mosquitto/conf.d/{fname}"
                    if upload_file_b64(ssh, lpath, rpath):
                        print(f"[OK] Загружен модуль: {fname}")
                    else:
                        return False

        # 5. Обработка режима перезапуска
        if skip_restart:
            print("[OK] Конфигурация успешно загружена. Служба Mosquitto не перезапускалась (--skip-restart).")
            return True

        print("[INFO] Перезапуск службы Mosquitto...")
        stdin, stdout, stderr = ssh.exec_command("/opt/etc/init.d/S80mosquitto restart")
        stdout.channel.recv_exit_status()
        restart_out = stdout.read().decode("utf-8", errors="replace").strip()
        print(restart_out)

        time.sleep(1)
        stdin, stdout, stderr = ssh.exec_command("/opt/etc/init.d/S80mosquitto check")
        status = stdout.read().decode("utf-8", errors="replace").strip()
        print(f"[STATUS] {status}")

        if "alive" not in status:
            print("[EMERGENCY] Mosquitto не запустился с новой конфигурацией! Запуск аварийного отката...")
            ssh.exec_command(
                "cp -f /opt/etc/mosquitto/.backup/mosquitto.conf /opt/etc/mosquitto/mosquitto.conf 2>/dev/null; "
                "cp -rf /opt/etc/mosquitto/.backup/conf.d /opt/etc/mosquitto/conf.d 2>/dev/null; "
                "/opt/etc/init.d/S80mosquitto restart"
            )
            time.sleep(1)
            stdin, stdout, stderr = ssh.exec_command("/opt/etc/init.d/S80mosquitto check")
            rollback_status = stdout.read().decode("utf-8", errors="replace").strip()
            print(f"[ROLLBACK STATUS] {rollback_status}")
            return False

        print("[SUCCESS] Конфигурация успешно развернута и проверена: брокер активен!")
        return True

    except Exception as e:
        print(f"[FAIL] Ошибка при развертывании: {e}")
        return False
    finally:
        ssh.close()


def main():
    parser = argparse.ArgumentParser(description="Deploy Mosquitto config to Keenetic router")
    parser.add_argument("--host", default="192.168.1.1", help="Router IP")
    parser.add_argument("--port", type=int, default=222, help="SSH Port")
    parser.add_argument("--user", default="root", help="SSH User")
    parser.add_argument("--password", default="keenetic", help="SSH Password")
    parser.add_argument("--configs-dir", default=None, help="Path to configs directory")
    parser.add_argument("--skip-restart", action="store_true", help="Do not restart mosquitto service")
    parser.add_argument("--strict-host-key", action="store_true", help="Reject unknown SSH host keys")
    args = parser.parse_args()

    if not args.configs_dir:
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        configs_dir = os.path.join(repo_dir, "configs")
    else:
        configs_dir = args.configs_dir

    success = deploy(
        args.host,
        args.port,
        args.user,
        args.password,
        configs_dir,
        args.skip_restart,
        accept_new_host_key=not args.strict_host_key,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
