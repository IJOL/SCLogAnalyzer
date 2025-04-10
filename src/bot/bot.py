import os
import json
import logging
import requests
import discord
from discord.ext import commands, tasks
import time  # Add this import

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
        self.stats_channel_id = config.get('stats_channel_id', '1334816643339128872')
        self.stats_message_id = None  # ID of the embed message

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'Logged in as {self.bot.user}')
        if not self.stats_channel_id:
            logger.error("Stats channel ID is not configured.")
            return
        await self.initialize_stats_message()

    async def get_channel(self, channel_id):
        """Fetch a channel by ID, handling errors gracefully."""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.warning(f"Channel with ID {channel_id} not found in cache. Attempting to fetch it.")
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                logger.error(f"Channel with ID {channel_id} does not exist.")
                return None
            except discord.Forbidden:
                logger.error(f"Bot does not have permission to access channel with ID {channel_id}.")
                return None
            except Exception as e:
                logger.exception(f"An unexpected error occurred while fetching the channel: {e}")
                return None
        return channel

    async def initialize_stats_message(self):
        """Create or fetch the stats embed message."""
        channel = await self.get_channel(self.stats_channel_id)
        if not channel:
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
                self.update_stats_task.start()  # Start periodic updates
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
            channel = await self.get_channel(self.stats_channel_id)
            if not channel:
                return

            message = await channel.fetch_message(self.stats_message_id)
            await message.edit(embed=embed)
            logger.info("Stats message updated successfully.")
        except Exception as e:
            logger.exception(f"Error updating stats message: {e}")

    def generate_stats_embed(self, data):
        """Generate an embed with statistics fetched from Google Sheets."""
        embed = discord.Embed(title="Real-Time Statistics", color=discord.Color.blue())
    
        # Abbreviate column names to save space
        column_names = {
            "Jugador": "Player",
            "Deaths/SB": "D/SB",
            "Kills/SB": "K/SB",
            "Ratio/SB": "R/SB",
            "Deaths/Live": "D/L",
            "Kills/Live": "K/L",
            "Ratio/Live": "R/L"
        }
    
        # Calculate column widths
        column_widths = {col: max(len(short), max(len(str(row.get(col, ''))) for row in data)) for col, short in column_names.items()}
    
        # Build the table header
        header = " | ".join(f"{column_names[col]:<{column_widths[col]}}" for col in column_names)
        separator = "-" * (sum(column_widths.values()) + len(column_names) * 3 - 1)
    
        # Add header and separator to the embed description
        description = f"```\n{header}\n{separator}\n"
    
        # Add rows to the table, truncating long values
        for row in data:
            row_data = " | ".join(
                f"{str(row.get(col, '')[:column_widths[col]]):<{column_widths[col]}}" for col in column_names
            )
            description += f"{row_data}\n"
    
        description += "```"
        embed.description = description
        return embed
    @update_stats_task.before_loop
    async def before_update_stats_task(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()
        
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

                # Determine column widths and types based on column names and contents
                keys = data[0].keys()
                column_widths = {}
                column_types = {}

                for i, key in enumerate(keys):
                    values = [item.get(key, '') for item in data]

                    if i == 0:
                        # First column is always treated as a string and has a fixed width
                        column_types[key] = 'str'
                        column_widths[key] = max(len(str(key)), max(len(str(v)) for v in values))
                    elif "Ratio" in key:
                        # Columns containing "Ratio" are treated as floats
                        column_types[key] = 'float'
                    elif all(isinstance(v, (int, float)) or str(v).replace('.', '', 1).isdigit() for v in values if v != ''):
                        if any(isinstance(v, float) or (isinstance(v, str) and '.' in v) for v in values):
                            column_types[key] = 'float'
                        else:
                            column_types[key] = 'int'
                    else:
                        column_types[key] = 'str'

                    if i != 0:  # Skip recalculating width for the first column
                        column_widths[key] = max(
                            len(str(key)),
                            max(len(f"{float(v):.2f}" if column_types[key] == 'float' else str(v)) for v in values)
                        )

                # Generate the table header
                summary = "📊 **Google Sheets Summary**\n"
                summary += "```\n"
                summary += " | ".join(f"{key:<{column_widths[key]}}" for key in keys) + "\n"
                summary += "-" * (sum(column_widths.values()) + len(keys) * 3 - 1) + "\n"

                # Populate rows based on the data
                for item in data:
                    summary += " | ".join(
                        f"{(f'{float(item.get(key, 0)):.2f}' if column_types[key] == 'float' else str(item.get(key, ''))):<{column_widths[key]}}"
                        for key in keys
                    ) + "\n"
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
