import os
import json
import logging
import requests
import discord
from discord.ext import commands, tasks

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

class StatusBoardBot(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.google_sheets_webhook = config.get('google_sheets_webhook', '')
        self.stats_channel_id = config.get('stats_channel_id', None)
        self.stats_message_id = None  # ID of the embed message
        self.update_stats_task.start()  # Start periodic updates

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'Logged in as {self.bot.user}')
        if not self.stats_channel_id:
            logger.error("Stats channel ID is not configured.")
            return
        await self.initialize_stats_message()

    async def initialize_stats_message(self):
        """Create or fetch the stats embed message."""
        channel = self.bot.get_channel(self.stats_channel_id)
        if not channel:
            logger.error(f"Could not find channel with ID {self.stats_channel_id}.")
            return

        try:
            if self.stats_message_id:
                # Try to fetch the existing message
                await channel.fetch_message(self.stats_message_id)
            else:
                # Create a new embed message if it doesn't exist
                embed = discord.Embed(title="Real-Time Statistics", description="Loading data...", color=discord.Color.blue())
                message = await channel.send(embed=embed)
                self.stats_message_id = message.id
        except discord.NotFound:
            # If the message doesn't exist, create a new one
            embed = discord.Embed(title="Real-Time Statistics", description="Loading data...", color=discord.Color.blue())
            message = await channel.send(embed=embed)
            self.stats_message_id = message.id

    @tasks.loop(minutes=5)  # Update every 5 minutes
    async def update_stats_task(self):
        """Periodic task to update the stats embed message."""
        if not self.google_sheets_webhook or not self.stats_channel_id or not self.stats_message_id:
            logger.warning("Cannot update stats message: incomplete configuration.")
            return

        try:
            # Fetch data from Google Sheets
            response = requests.get(self.google_sheets_webhook)
            if response.status_code != 200:
                logger.error(f"Error fetching data from Google Sheets: {response.status_code}")
                return

            data = response.json()
            if not isinstance(data, list) or not data:
                logger.warning("Data from Google Sheets is empty or in an unexpected format.")
                return

            # Generate the embed with the statistics
            embed = self.generate_stats_embed(data)

            # Update the embed message
            channel = self.bot.get_channel(self.stats_channel_id)
            if not channel:
                logger.error(f"Could not find channel with ID {self.stats_channel_id}.")
                return

            message = await channel.fetch_message(self.stats_message_id)
            await message.edit(embed=embed)
            logger.info("Stats message updated successfully.")
        except Exception as e:
            logger.exception(f"Error updating stats message: {e}")

    def generate_stats_embed(self, data):
        """Generate an embed with statistics fetched from Google Sheets."""
        embed = discord.Embed(title="Real-Time Statistics", color=discord.Color.blue())

        # Extract column names and calculate column widths
        column_names = list(data[0].keys())
        column_widths = {col: max(len(col), max(len(str(row.get(col, ''))) for row in data)) for col in column_names}

        # Build the table header
        header = " | ".join(f"{col:<{column_widths[col]}}" for col in column_names)
        separator = "-" * (sum(column_widths.values()) + len(column_names) * 3 - 1)

        # Add header and separator to the embed description
        description = f"```\n{header}\n{separator}\n"

        # Add rows to the table
        for row in data:
            row_data = " | ".join(f"{str(row.get(col, '')):<{column_widths[col]}}" for col in column_names)
            description += f"{row_data}\n"

        description += "```"
        embed.description = description
        return embed

    @update_stats_task.before_loop
    async def before_update_stats_task(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()

async def main():
    app_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(app_path, "config.json")

    if not os.path.exists(config_path):
        logger.error(f"Config file not found at: {config_path}")
        return

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
