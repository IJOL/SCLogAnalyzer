import time
import requests
import json

# Leer configuración desde el archivo JSON
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

log_file_path = config["log_file_path"]
player_ids = config["player_ids"]
webhook_url = config["webhook_url"]

# Función para enviar mensajes a Discord usando el Webhook
def send_discord_notification(message):
    data = {
        "content": message,  # El contenido del mensaje
        "username": "La vecina de Arriba",  # Nombre del bot (opcional)
    }
    response = requests.post(webhook_url, json=data)
    if response.status_code == 204:
        print("Mensaje enviado a Discord")
    else:
        print(f"Error al enviar el mensaje: {response.status_code}")

# Diccionario para almacenar las ubicaciones actuales de los jugadores
player_locations = {}

# Leer el archivo en tiempo real
def monitor_log(file_path, players):
    with open(file_path, "r", encoding="latin-1") as log_file:
        log_file.seek(0)  # Leer desde el inicio
        print("Monitoreando el archivo log...")
        while True:
            line = log_file.readline()
            if not line:
                time.sleep(0.1)  # Esperar por nuevas líneas
                continue
            print(f"Línea leída: {line.strip()}")  # Verificar si está leyendo correctamente

            # Verificar si alguna ID de jugador está en la línea
            for player in players:
                if player in line:
                    print(f"¡Detectado jugador {player}!")

                    # Verificar ubicación
                    ubicacion = "Desconocida"
                    if "lorevile" in line:
                        ubicacion = "Lorville"
                    elif "orison" in line:
                        ubicacion = "Orison"
                    elif "A18" in line:
                        ubicacion = "A18"
                    elif "newbab" in line:
                        ubicacion = "New Babbage"
                    elif "InstancedInterior" in line:
                        ubicacion = "Estación Espacial"

                    # Comprobar si la ubicación del jugador ha cambiado
                    if player not in player_locations or player_locations[player] != ubicacion:
                        # Actualizar la ubicación en el diccionario
                        player_locations[player] = ubicacion
                        # Enviar la notificación solo si hay cambio
                        send_discord_notification(f"¡Jugador detectado! {player} en {ubicacion}.")
                    else:
                        print(f"Sin cambios para {player}, ya está en {ubicacion}. No se envía notificación.")
                    
# Iniciar el monitoreo
monitor_log(log_file_path, player_ids)
input("Presiona Enter para salir...")
