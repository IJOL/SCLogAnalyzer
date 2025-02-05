import os
import json
import logging
import re
import discord
import asyncio
import requests
from discord.ext import commands, tasks

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("discord_bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class StarCitizenBot(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.log_file_path = config["log_file_path"]
        self.regex_patterns = config["regex_patterns"]
        self.player_name = config.get("player_name", "")
        self.google_sheets_webhook = config.get("google_sheets_webhook", "")
        self.last_position = 0
        self.check_logs.start()

    @tasks.loop(seconds=5)
    async def check_logs(self):
        try:
            with open(self.log_file_path, "r", encoding="utf-8", errors="ignore") as file:
                file.seek(self.last_position)
                new_entries = file.readlines()
                self.last_position = file.tell()
            
            for entry in new_entries:
                await self.process_log_entry(entry)

        except Exception as e:
            logger.error(f"Error leyendo el archivo de logs: {e}")

    async def process_log_entry(self, entry):
        await self.detect_actor_death(entry)

    async def detect_actor_death(self, entry):
        match = re.search(self.regex_patterns["actor_death"], entry)
        if match:
            data = match.groupdict()
            victim = data["victim"]
            killer = data["killer"]
            weapon = data["weapon"]
            damage_type = data["damage_type"]
            timestamp = data["timestamp"]

            if self.player_name and victim != self.player_name and killer != self.player_name:
                return False

            self.update_google_sheets(victim, killer, weapon, damage_type, timestamp)

            message = f"💀 **Star Citizen Death Event**\n" \
                      f"🔹 **Victim:** `{victim}`\n" \
                      f"🔹 **Killer:** `{killer}`\n" \
                      f"🔫 **Weapon:** `{weapon}`\n" \
                      f"🔥 **Damage Type:** `{damage_type}`\n" \
                      f"⏳ **Timestamp:** `{timestamp}`"

            channel = self.bot.get_channel(self.config["technical_channel_id"])
            if channel:
                await channel.send(message)

            return True
        return False

    def update_google_sheets(self, victim, killer, weapon, damage_type, timestamp):
        if not self.google_sheets_webhook:
            logger.error("❌ Webhook de Google Sheets no configurado en config.json.")
            return

        data = {
            "timestamp": timestamp,
            "killer": killer,
            "victim": victim,
            "weapon": weapon,
            "damage_type": damage_type
        }

        try:
            logger.info(f"📡 Enviando datos a Google Sheets: {data}")
            response = requests.post(self.google_sheets_webhook, json=data)
            logger.info(f"📡 Respuesta de Google Sheets: {response.text}")  # <-- Muestra la respuesta

            if response.status_code == 200:
                logger.info("✅ Datos enviados correctamente a Google Sheets.")
            else:
                logger.error(f"❌ Error al enviar datos: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"❌ Excepción al enviar datos a Google Sheets: {e}")

    @commands.command(name="tabla")
    async def tabla(self, ctx):
        if not self.google_sheets_webhook:
            await ctx.send("❌ No hay API configurada para Google Sheets.")
            return
        
        try:
            response = requests.get(self.google_sheets_webhook)
            logger.info(f"📡 Respuesta de Google Sheets (Resumen): {response.text}")

            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    await ctx.send(f"❌ Error: {data['error']}")
                    return
                
                tabla_msg = "**📊 Kills & Deaths en Star Citizen**\n```"
                tabla_msg += "{:<15} {:<6} {:<6}\n".format("Jugador", "Kills", "Deaths")
                tabla_msg += "-" * 30 + "\n"
                for row in data:
                    tabla_msg += "{:<15} {:<6} {:<6}\n".format(row["player"], row["kills"], row["deaths"])
                tabla_msg += "```"

                await ctx.send(tabla_msg)
            else:
                await ctx.send(f"❌ Error obteniendo la tabla: {response.status_code}")
        except Exception as e:
            await ctx.send(f"❌ Error al procesar la tabla: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(self.config["technical_channel_id"])
        if channel:
            await channel.send(f"{self.player_name}🔹 **Star Citizen Bot** iniciado correctamente.")
        logger.info(f"Bot conectado como {self.bot.user}")

async def run_bot(config):
    intents = discord.Intents.default()
    intents.message_content = True  # Habilita permisos para leer mensajes
    bot = commands.Bot(command_prefix="!", intents=intents)

    star_citizen_cog = StarCitizenBot(bot, config)
    await bot.add_cog(star_citizen_cog)  # 🔹 Soluciona problema de `was never awaited`
    
    await bot.start(config["discord_bot_token"])  # 🔹 Ahora usa `await`

def main(config_path):
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    asyncio.run(run_bot(config))  # 🔹 Usa `asyncio.run()` para evitar errores

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        logger.error("Uso: bot.py <config.json>")
        sys.exit(1)

    config_path = sys.argv[1]
    main(config_path)
