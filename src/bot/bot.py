import os
import sys
import json
import logging
import requests
import discord
from discord.ext import commands
import time  # Add this import for measuring execution time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('discord_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG_TEMPLATE = "config.json.template"

def prompt_for_config_values(template):
    config = template.copy()
    for key, value in template.items():
        if isinstance(value, str) and value.startswith("{?") and value.endswith("}"):
            label = value[2:-1]
            user_input = input(f"Please enter a value for {label}: ")
            config[key] = user_input
        elif isinstance(value, dict):
            config[key] = prompt_for_config_values(value)
    return config

def emit_default_config(config_path):
    with open(get_template_path(), 'r', encoding='utf-8') as template_file:
        template_config = json.load(template_file)
    config = prompt_for_config_values(template_config)
    with open(config_path, 'w', encoding='utf-8') as config_file:
        json.dump(config, config_file, indent=4)
    logger.info(f"Default config emitted at {config_path}")

def get_template_path():
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        return os.path.join(sys._MEIPASS, DEFAULT_CONFIG_TEMPLATE)
    else:
        # Running in normal Python environment
        return os.path.join(os.path.dirname(__file__), DEFAULT_CONFIG_TEMPLATE)

def get_application_path():
    """Determine the correct application path whether running as .py or .exe"""
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle (exe)
        return os.path.dirname(sys.executable)
    else:
        # If the application is run as a python script
        return os.path.dirname(os.path.abspath(__file__))

class StatusBoardBot(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.google_sheets_webhook = config.get('google_sheets_webhook', '')

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'Logged in as {self.bot.user}')

    @commands.command(name='stats')
    async def fetch_google_sheets_stats(self, ctx):
        logger.info(f"Command 'stats' invoked by user: {ctx.author} in channel: {ctx.channel}")
        start_time = time.time()  # Start timing the command execution

        if not self.google_sheets_webhook:
            logger.warning("Google Sheets webhook URL is not configured.")
            await ctx.send("Google Sheets webhook URL is not configured.")
            return

        try:
            logger.info(f"Sending GET request to Google Sheets webhook: {self.google_sheets_webhook}")
            response = requests.get(self.google_sheets_webhook)
            logger.info(f"Received response with status code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, list) or not data:
                    logger.warning("The response data is empty or not in the expected format.")
                    await ctx.send("The response data is empty or not in the expected format.")
                    return

                # Determine column widths based on the longest value in each column
                keys = data[0].keys()
                column_widths = {key: max(len(str(key)), max(len(str(item.get(key, ''))) for item in data))}

                # Generate the table header
                summary = "📊 **Google Sheets Summary**\n"
                summary += "```\n"
                summary += " | ".join(f"{key:<{column_widths[key]}}" for key in keys) + "\n"
                summary += "-" * (sum(column_widths.values()) + len(keys) * 3 - 1) + "\n"

                # Populate rows based on the data
                for item in data:
                    summary += " | ".join(f"{str(item.get(key, '')):<{column_widths[key]}}" for key in keys) + "\n"
                summary += "```"
                logger.info("Successfully generated Google Sheets summary.")
                await ctx.send(summary)
            else:
                logger.error(f"Failed to fetch data from Google Sheets. Status code: {response.status_code}")
                await ctx.send(f"Failed to fetch data from Google Sheets. Status code: {response.status_code}")
        except Exception as e:
            logger.exception(f"Error fetching data from Google Sheets: {e}")
            await ctx.send(f"Error fetching data from Google Sheets: {e}")
        finally:
            execution_time = time.time() - start_time
            logger.info(f"Command 'stats' executed in {execution_time:.2f} seconds.")

async def main():
    app_path = get_application_path()
    config_path = os.path.join(app_path, "config.json")

    if not os.path.exists(config_path):
        logger.info(f"Config file not found, creating default at: {config_path}")
        emit_default_config(config_path)

    with open(config_path, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    await bot.add_cog(StatusBoardBot(bot, config))

    await bot.start(config['discord_bot_token'])

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
