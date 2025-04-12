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
        self.ratio_live_message_id = None  # ID of the Ratio/Live leaderboard embed
        self.ratio_sb_message_id = None  # ID of the Ratio/SB leaderboard embed
        self.last_update_time = 0  # Track the last update time

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

    async def initialize_leaderboard_messages(self):
        """Create or fetch the leaderboard embed messages."""
        channel = await self.get_channel(self.stats_channel_id)
        if not channel:
            return

        try:
            # Search for existing leaderboard embeds in the channel
            async for message in channel.history(limit=100):
                if message.embeds:
                    embed = message.embeds[0]
                    if embed.title == "Leaderboard - Ratio/Live":
                        self.ratio_live_message_id = message.id
                        logger.info("Found existing Ratio/Live leaderboard message.")
                    elif embed.title == "Leaderboard - Ratio/SB":
                        self.ratio_sb_message_id = message.id
                        logger.info("Found existing Ratio/SB leaderboard message.")

            # Create new embeds if not found
            if self.ratio_live_message_id is None:
                embed = discord.Embed(title="Leaderboard - Ratio/Live", description="Loading data...", color=discord.Color.green())
                message = await channel.send(embed=embed)
                self.ratio_live_message_id = message.id
                logger.info(f"Created new Ratio/Live leaderboard message with ID: {message.id}")

            if self.ratio_sb_message_id is None:
                embed = discord.Embed(title="Leaderboard - Ratio/SB", description="Loading data...", color=discord.Color.purple())
                message = await channel.send(embed=embed)
                self.ratio_sb_message_id = message.id
                logger.info(f"Created new Ratio/SB leaderboard message with ID: {message.id}")

        except Exception as e:
            logger.exception(f"Error initializing leaderboard messages: {e}")

    async def update_leaderboard_embeds(self, data):
        """Update the leaderboard embeds with sorted data."""
        channel = await self.get_channel(self.stats_channel_id)
        if not channel:
            return

        try:
            # Check if message IDs are valid before attempting to fetch
            if self.ratio_live_message_id is None or self.ratio_sb_message_id is None:
                logger.warning("Leaderboard message IDs are not initialized. Running initialization...")
                await self.initialize_leaderboard_messages()
                # If still None after initialization, abort the update
                if self.ratio_live_message_id is None or self.ratio_sb_message_id is None:
                    logger.error("Failed to initialize leaderboard message IDs. Skipping update.")
                    return

            # Update Ratio/Live leaderboard
            sorted_ratio_live = sorted(data, key=lambda x: float(x.get("Ratio/Live", 0)), reverse=True)
            embed_live = discord.Embed(
                title="🏆 Leaderboard - Ratio/Live",
                description="Top players ranked by **Ratio/Live**. 🟢",
                color=discord.Color.green()
            )

            for i, row in enumerate(sorted_ratio_live[:3], start=1):
                player_name = row.get("Jugador", "Unknown")
                ratio_value = row.get('Ratio/Live', 'N/A')
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🎖️"
                embed_live.add_field(
                    name=f"{medal} {player_name} - {ratio_value}",
                    value="\u200b",  # Zero-width space as a placeholder
                    inline=False
                )

            message_live = await channel.fetch_message(self.ratio_live_message_id)
            await message_live.edit(embed=embed_live)

            # Update Ratio/SB leaderboard
            sorted_ratio_sb = sorted(data, key=lambda x: float(x.get("Ratio/SB", 0)), reverse=True)
            embed_sb = discord.Embed(
                title="🏆 Leaderboard - Ratio/SB",
                description="Top players ranked by **Ratio/SB**. 🟣",
                color=discord.Color.purple()
            )

            for i, row in enumerate(sorted_ratio_sb[:3], start=1):
                player_name = row.get("Jugador", "Unknown")
                ratio_value = row.get('Ratio/SB', 'N/A')
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🎖️"
                embed_sb.add_field(
                    name=f"{medal} {player_name} - {ratio_value}",
                    value="\u200b",  # Zero-width space as a placeholder
                    inline=False
                )

            message_sb = await channel.fetch_message(self.ratio_sb_message_id)
            await message_sb.edit(embed=embed_sb)

            logger.info("Leaderboard embeds updated successfully.")

        except discord.NotFound:
            logger.error("One or more leaderboard messages not found. Re-initializing...")
            self.ratio_live_message_id = None
            self.ratio_sb_message_id = None
            await self.initialize_leaderboard_messages()
        except Exception as e:
            logger.exception(f"Error updating leaderboard embeds: {e}")

    async def initialize_stats_message(self):
        """Create or fetch the stats embed message and initialize leaderboards."""
        channel = await self.get_channel(self.stats_channel_id)
        if not channel:
            return
        try:
            # Search for an existing embed in the channel
            async for message in channel.history(limit=100):  # Adjust limit as needed
                if message.embeds:
                    embed = message.embeds[0]
                    if embed.title == "Real-Time Statistics":
                        self.stats_message_id = message.id
                        logger.info("Found existing stats embed message.")
                        await self.initialize_leaderboard_messages()
                        self.update_stats_task.start()  # Start periodic updates
                        return

            # If no existing embed is found, create a new one
            embed = discord.Embed(title="Real-Time Statistics", description="Loading data...", color=discord.Color.blue())
            message = await channel.send(embed=embed)
            self.stats_message_id = message.id
            await self.initialize_leaderboard_messages()
            self.update_stats_task.start()  # Start periodic updates
        except discord.NotFound:
            logger.error("Channel not found or inaccessible.")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while initializing the stats message: {e}")

    @tasks.loop(minutes=1)  # Use a fixed interval of 1 minute
    async def update_stats_task(self):
        """Periodic task to update the stats and leaderboard embed messages."""
        # Get the configured update period (in minutes)
        update_period = self.config.get('update_period_minutes', 1)
        current_time = time.time()
        
        # Check if enough time has passed since the last update
        # Convert update_period from minutes to seconds for comparison
        if current_time - self.last_update_time < (update_period * 60):
            return  # Skip this iteration if not enough time has passed
            
        # Update the last update time
        self.last_update_time = current_time
            
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

            # Update the stats embed
            embed = self.generate_stats_embed(data)
            channel = await self.get_channel(self.stats_channel_id)
            if not channel:
                return

            message = await channel.fetch_message(self.stats_message_id)
            await message.edit(embed=embed)

            # Update the leaderboard embeds
            await self.update_leaderboard_embeds(data)

            logger.info(f"Stats and leaderboard messages updated successfully. Next update in {update_period} minutes.")
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
                f"{str(row.get(col, ''))[:column_widths[col]]:<{column_widths[col]}}" for col in column_names
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

    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx, metric: str = "Kills/SB"):
        """Generate a leaderboard based on a specific metric."""
        logger.info(f"Command 'leaderboard' invoked by user: {ctx.author} with metric: {metric}")

        if not self.google_sheets_webhook:
            logger.warning("Google Sheets webhook URL is not configured.")
            await ctx.send("Google Sheets webhook URL is not configured.")
            return

        try:
            # Fetch data from Google Sheets
            response = requests.get(self.google_sheets_webhook)
            if response.status_code != 200:
                logger.error(f"Error fetching data from Google Sheets: {response.status_code}")
                await ctx.send(f"Error fetching data from Google Sheets: {response.status_code}")
                return

            data = response.json()
            if not isinstance(data, list) or not data:
                logger.warning("Data from Google Sheets is empty or in an unexpected format.")
                await ctx.send("Data from Google Sheets is empty or in an unexpected format.")
                return

            # Validate the metric
            if metric not in data[0]:
                await ctx.send(f"Invalid metric: {metric}. Please choose a valid column name.")
                return

            # Sort the data by the specified metric
            try:
                sorted_data = sorted(data, key=lambda x: float(x.get(metric, 0)), reverse=True)
            except ValueError:
                await ctx.send(f"The metric '{metric}' contains non-numeric values and cannot be used for ranking.")
                return

            # Generate the leaderboard embed
            embed = discord.Embed(title=f"Leaderboard - {metric}", color=discord.Color.gold())
            embed.description = "Top players ranked by the selected metric."

            for i, row in enumerate(sorted_data[:10], start=1):  # Show top 10 players
                player_name = row.get("Jugador", "Unknown")
                metric_value = row.get(metric, "N/A")
                embed.add_field(name=f"#{i} {player_name}", value=f"{metric}: {metric_value}", inline=False)

            await ctx.send(embed=embed)
            logger.info("Leaderboard generated and sent successfully.")

        except Exception as e:
            logger.exception(f"Error generating leaderboard: {e}")
            await ctx.send(f"Error generating leaderboard: {e}")

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
