"""
CLI de test de presencia y broadcast para SCLogAnalyzer
Permite simular múltiples usuarios, cada uno con su propia instancia de RealtimeBridge.
No usa wx ni GUI, solo stdout. Uso: python src/test_realtime_cli.py --users 3
"""
import argparse
import threading
import time
import random
import sys
from datetime import datetime
import os

# Desactivar la redirección de stdout a message_bus
os.environ['SCLOG_DISABLE_STDOUT_REDIRECT'] = '1'

# Importar los módulos de helpers del proyecto
sys.path.append('./src')
from helpers.realtime_bridge import RealtimeBridge
from helpers.config_utils import ConfigManager
from helpers.message_bus import message_bus, setup_console_handler
from helpers import supabase_manager

# Forzar la impresión de todos los mensajes del message_bus en la consola
setup_console_handler(debug=True, replay_history=False)

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
            self.bridge = RealtimeBridge(config_manager=config, supabase_client=supabase_client)
            print(f"[{self.username}] Instanciado RealtimeBridge")
            self.bridge.username = self.username
            self.bridge.shard = self.shard
            self.bridge.version = self.version
            print(f"[{self.username}] Seteados username, shard y version")
            # Llamar a connect() para inicializar canales y presencia/broadcast correctamente
            self.bridge.connect()
            print(f"[{self.username}] RealtimeBridge conectado (canales y heartbeat inicializados)")
            self.running = True
            # Suscribirse a eventos relevantes
            message_bus.on("users_online_updated", self.on_users_online)
            message_bus.on("remote_realtime_event", self.on_remote_event)
            print(f"[{self.username}] Suscrito a eventos de presencia y broadcast")
            # Lanzar bucle de actividad
            threading.Thread(target=self.activity_loop, daemon=True).start()
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

# Añadir un subscriber global para imprimir absolutamente todos los argumentos y keywords recibidos, para asegurar que no se pierda ningún mensaje por firma inesperada.

def print_all_messages(*args, **kwargs):
    print(f"[MessageBus] args={args} kwargs={kwargs}")

message_bus.on("*", print_all_messages)

def main():
    parser = argparse.ArgumentParser(description="Test CLI for SCLogAnalyzer RealtimeBridge")
    parser.add_argument('--users', type=int, default=2, help='Number of simulated users')
    args = parser.parse_args()

    users = []
    for i in range(args.users):
        username = f"testuser{i+1}"
        user = TestUser(username)
        users.append(user)
        user.start()
        time.sleep(2)  # Pequeño retardo para escalonar conexiones

    print(f"Started {args.users} simulated users. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping all users...")
        for user in users:
            user.stop()
        print("All users stopped.")

if __name__ == "__main__":
    main()
