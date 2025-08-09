"""
CLI de test de presencia y broadcast para SCLogAnalyzer
Permite simular múltiples usuarios, cada uno con su propia instancia de RealtimeBridge.
No usa wx ni GUI, solo stdout. Uso: python src/test_realtime_cli.py --users 3
"""
import argparse
import subprocess
import sys
import time
import os
from datetime import datetime
import random

# Desactivar la redirección de stdout a message_bus
os.environ['SCLOG_DISABLE_STDOUT_REDIRECT'] = '1'

sys.path.append('./src')
from helpers.core.realtime_bridge import RealtimeBridge
from helpers.core.config_utils import ConfigManager
from helpers.core.message_bus import message_bus, setup_console_handler
from helpers.core import supabase_manager

setup_console_handler(debug=True, replay_history=False)
message_bus.set_debug_mode(True)

class TestUser:
    def __init__(self, username, shard="TestShard", version="test-v1.0"):
        self.username = username
        self.shard = shard
        self.version = version
        self.bridge = None
        self.running = False

    def start(self):
        try:
            print(f"[{self.username}] Starting simulated user...")
            config = ConfigManager()
            supabase_client = supabase_manager.supabase_manager.connect(config)
            print(f"[{self.username}] Obtenido supabase_client: {supabase_client}")
            self.bridge = RealtimeBridge(config_manager=config, supabase_client=supabase_client, use_singleton=True)
            print(f"[{self.username}] Instanciado RealtimeBridge")
            self.bridge.shard = self.shard
            self.bridge.version = self.version
            print(f"[{self.username}] Seteados username, shard y version")
            self.bridge.set_username(self.username)
            print(f"[{self.username}] RealtimeBridge conectado (canales y heartbeat inicializados)")
            self.running = True
            message_bus.on("users_online_updated", self.on_users_online)
            message_bus.on("remote_realtime_event", self.on_remote_event)
            print(f"[{self.username}] Suscrito a eventos de presencia y broadcast")
            self.activity_loop()
        except Exception as e:
            print(f"[{self.username}] ERROR en start: {e}")
            import traceback
            print(traceback.format_exc())

    def activity_loop(self):
        while self.running:
            try:
                msg = {
                    "content": f"Hello from {self.username} at {datetime.now().isoformat()}",
                    "type": "test_broadcast",
                    "timestamp": datetime.now().isoformat(),
                    "username": self.username
                }
                self.bridge._handle_realtime_event(msg)
                print(f"[{self.username}] Sent broadcast message: {msg}")
            except Exception as e:
                print(f"[{self.username}] ERROR enviando broadcast: {e}")
            time.sleep(random.randint(10, 20))

    def on_users_online(self, users_online):
        print(f"[{self.username}] Users online (evento): {users_online}")

    def on_remote_event(self, username, event_data):
        print(f"[{self.username}] Received event from {username}: {event_data}")
        if username != self.username:
            print(f"[{self.username}] (evento externo) {event_data}")

    def stop(self):
        self.running = False
        if self.bridge:
            self.bridge._stop_heartbeat()
            self.bridge.disconnect()
        print(f"[{self.username}] Stopped.")

def print_all_messages(*args, **kwargs):
    print(f"[MessageBus] args={args} kwargs={kwargs}")

message_bus.on("*", print_all_messages)

def main():
    parser = argparse.ArgumentParser(description="Test CLI for SCLogAnalyzer RealtimeBridge (multiproceso)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--users', type=int, help='Número de usuarios simulados (multiproceso)')
    group.add_argument('--username', type=str, help='Nombre de usuario simulado (modo usuario único)')
    parser.add_argument('--shard', type=str, default='TestShard', help='Shard a usar (opcional)')
    parser.add_argument('--version', type=str, default='test-v1.0', help='Versión a usar (opcional)')
    args = parser.parse_args()

    if args.users:
        # Multiproceso: lanzar N procesos independientes
        processes = []
        for i in range(args.users):
            username = f"testuser{i+1}"
            cmd = [sys.executable, __file__, '--username', username, '--shard', args.shard, '--version', args.version]
            print(f"[Main] Lanzando proceso para {username}: {cmd}")
            proc = subprocess.Popen(cmd)
            processes.append(proc)
            time.sleep(2)  # Escalonar conexiones
        print(f"[Main] Lanzados {args.users} procesos de usuario. Ctrl+C para detener.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Main] Deteniendo todos los procesos de usuario...")
            for proc in processes:
                proc.terminate()
            for proc in processes:
                proc.wait()
            print("[Main] Todos los procesos detenidos.")
    elif args.username:
        # Modo usuario único: simular un usuario en este proceso
        user = TestUser(args.username, shard=args.shard, version=args.version)
        user.running = True
        try:
            user.start()
        except KeyboardInterrupt:
            print("\n[SingleUser] Deteniendo usuario...")
            user.stop()

if __name__ == "__main__":
    main()
