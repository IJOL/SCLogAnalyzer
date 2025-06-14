import os
import json
import logging
import requests
import discord
from discord.ext import commands, tasks
import time
import sys

# Add parent directory to path to allow importing helpers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the config manager and data provider from helpers
from helpers.config_utils import get_config_manager
from helpers.data_provider import get_data_provider

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
    def __init__(self, bot, config_manager):
        self.bot = bot
        self.config_manager = config_manager
        
        # Use config manager to get configuration values
        self.google_sheets_webhook = self.config_manager.get('google_sheets_webhook', '')
        self.stats_channel_id = self.config_manager.get('stats_channel_id', '1334816643339128872')
        self.update_period = self.config_manager.get('update_period_minutes', 5)
        
        # Initialize data provider
        self.data_provider = get_data_provider(self.config_manager)
        
        # Field mappings between different data source formats
        self.field_mappings = {
            # Supabase field names to standardized field names
            'supabase': {
                'username': 'Jugador',
                'kills_live': 'Kills/Live',
                'deaths_live': 'Deaths/Live',
                'kdr_live': 'Ratio/Live',
                'kills_sb': 'Kills/SB',
                'deaths_sb': 'Deaths/SB',
                'kdr_sb': 'Ratio/SB',
                'total_kills': 'Total Kills',
                'total_deaths': 'Total Deaths',
                'kdr_total': 'Ratio Total'
            },
            # Google Sheets field names (already standardized format)
            'googlesheets': {
                'Jugador': 'Jugador',
                'Kills/Live': 'Kills/Live',
                'Deaths/Live': 'Deaths/Live',
                'Ratio/Live': 'Ratio/Live',
                'Kills/SB': 'Kills/SB',
                'Deaths/SB': 'Deaths/SB',
                'Ratio/SB': 'Ratio/SB'
            }
        }
        
        # Initialize message IDs
        self.stats_live_message_id = None  # ID of the Live stats message
        self.stats_sb_message_id = None    # ID of the Squadron Battle stats message
        self.ratio_live_message_id = None  # ID of the Ratio/Live leaderboard embed
        self.ratio_sb_message_id = None    # ID of the Ratio/SB leaderboard embed
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
        # Convert string channel ID to integer if needed
        channel_id = int(channel_id) if isinstance(channel_id, str) else channel_id
        
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
        """Create or fetch the combined leaderboard embed message."""
        channel = await self.get_channel(self.stats_channel_id)
        if not channel:
            return

        try:
            # Search for existing leaderboard embeds in the channel
            async for message in channel.history(limit=100):
                if message.embeds:
                    embed = message.embeds[0]
                    if "Leaderboards" in embed.title:
                        self.ratio_live_message_id = message.id
                        self.ratio_sb_message_id = None  # We don't need this anymore
                        logger.info("Found existing combined leaderboard message.")
                        return
                    elif "Ratio/Live" in embed.title or "Ratio/SB" in embed.title:
                        # Found an old format message, will replace it
                        await message.delete()
                        logger.info("Deleted old format leaderboard message.")

            # Create new combined embed if not found
            embed = discord.Embed(
                title="🏆 Leaderboards",
                description="Top players ranked by performance metrics",
                color=discord.Color.gold()
            )
            embed.add_field(name="🟢 Ratio/Live", value="Loading data...", inline=True)
            embed.add_field(name="🟣 Ratio/SB", value="Loading data...", inline=True)
            
            message = await channel.send(embed=embed)
            self.ratio_live_message_id = message.id
            self.ratio_sb_message_id = None  # We don't need this anymore
            logger.info(f"Created new combined leaderboard message with ID: {message.id}")

        except Exception as e:
            logger.exception(f"Error initializing combined leaderboard message: {e}")

    async def update_leaderboard_embeds(self, data):
        """Update the combined leaderboard embed with sorted data."""
        channel = await self.get_channel(self.stats_channel_id)
        if not channel:
            return

        try:
            # Check if message ID is valid before attempting to fetch
            if self.ratio_live_message_id is None:
                logger.warning("Leaderboard message ID is not initialized. Running initialization...")
                await self.initialize_leaderboard_messages()
                # If still None after initialization, abort the update
                if self.ratio_live_message_id is None:
                    logger.error("Failed to initialize leaderboard message ID. Skipping update.")
                    return

            # Create a combined embed with both leaderboards side by side
            embed = discord.Embed(
                title="🏆 Leaderboards",
                description="Top players ranked by performance metrics",
                color=discord.Color.gold()
            )
            
            # Process Ratio/Live data
            sorted_ratio_live = sorted(data, key=lambda x: float(x.get("Ratio/Live", 0)), reverse=True)
            live_content = ""
            for i, row in enumerate(sorted_ratio_live[:3], start=1):
                player_name = row.get("Jugador", "Unknown")
                ratio_value = row.get('Ratio/Live', 'N/A')
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🎖️"
                live_content += f"{medal} {player_name}: {ratio_value}\n"
            
            # Process Ratio/SB data
            sorted_ratio_sb = sorted(data, key=lambda x: float(x.get("Ratio/SB", 0)), reverse=True)
            sb_content = ""
            for i, row in enumerate(sorted_ratio_sb[:3], start=1):
                player_name = row.get("Jugador", "Unknown")
                ratio_value = row.get('Ratio/SB', 'N/A')
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🎖️"
                sb_content += f"{medal} {player_name}: {ratio_value}\n"
            
            # Add the fields side by side (inline=True for side-by-side display)
            embed.add_field(name="🟢 Ratio/Live", value=live_content, inline=True)
            embed.add_field(name="🟣 Ratio/SB", value=sb_content, inline=True)
            
            # Update existing message or create a new one if needed
            try:
                message = await channel.fetch_message(self.ratio_live_message_id)
                await message.edit(embed=embed)
                logger.info("Combined leaderboard message updated successfully.")
            except discord.NotFound:
                # If the message is not found, create a new one
                message = await channel.send(embed=embed)
                self.ratio_live_message_id = message.id
                logger.info(f"Created new combined leaderboard message with ID: {message.id}")
            
        except Exception as e:
            logger.exception(f"Error updating combined leaderboard: {e}")

    async def initialize_stats_message(self):
        """Create or fetch the stats text messages and initialize leaderboards."""
        channel = await self.get_channel(self.stats_channel_id)
        if not channel:
            return
        try:
            # Search for existing stats messages in the channel
            async for message in channel.history(limit=100):  # Adjust limit as needed
                if message.embeds and message.embeds[0].title == "Real-Time Statistics":
                    # This is an old embed-based stats message, delete it so we can replace with text messages
                    await message.delete()
                    logger.info("Found and deleted old stats embed message.")
                    continue
                elif message.content and message.content.startswith("🟢 **Live Mode Statistics - Current Month**"):
                    # Found an existing Live mode stats message
                    self.stats_live_message_id = message.id
                    logger.info("Found existing Live mode stats message.")
                    continue
                elif message.content and message.content.startswith("🟣 **Squadron Battle Statistics - Current Month**"):
                    # Found an existing Squadron Battle stats message
                    self.stats_sb_message_id = message.id
                    logger.info("Found existing Squadron Battle stats message.")
                    continue
                elif message.content and (message.content.startswith("🟢 **Live Mode Statistics**") or message.content.startswith("🟣 **Squadron Battle Statistics**")):
                    # Found an old format message without "- Current Month", delete it
                    await message.delete()
                    logger.info("Found and deleted old stats message without 'Current Month' suffix.")
                    continue
                elif message.content and message.content.startswith("📊 **Real-Time Statistics**"):
                    # Found an old single stats message, delete it
                    await message.delete()
                    logger.info("Found and deleted old combined stats message.")
                    continue            # Create new messages if not found
            if not self.stats_live_message_id:
                message = await channel.send("🟢 **Live Mode Statistics - Current Month**\n```Loading data...```")
                self.stats_live_message_id = message.id
                logger.info(f"Created new Live mode stats message with ID: {message.id}")
            
            if not self.stats_sb_message_id:
                message = await channel.send("🟣 **Squadron Battle Statistics - Current Month**\n```Loading data...```")
                self.stats_sb_message_id = message.id
                logger.info(f"Created new Squadron Battle stats message with ID: {message.id}")
            
            # Initialize leaderboard messages and start update task
            await self.initialize_leaderboard_messages()
            self.update_stats_task.start()  # Start periodic updates

        except discord.NotFound:
            logger.error("Channel not found or inaccessible.")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while initializing the stats messages: {e}")

    @tasks.loop(minutes=1)  # Use a fixed interval of 1 minute
    async def update_stats_task(self):
        """Periodic task to update the stats and leaderboard embed messages."""
        # Get the configured update period (in minutes)
        update_period = self.config_manager.get('update_period_minutes', 1)
        current_time = time.time()
        
        # Check if enough time has passed since the last update
        # Convert update_period from minutes to seconds for comparison
        if current_time - self.last_update_time < (update_period * 60):
            return  # Skip this iteration if not enough time has passed
            
        # Update the last update time
        self.last_update_time = current_time
            
        if not self.stats_channel_id or not self.stats_live_message_id or not self.stats_sb_message_id:
            logger.warning("Cannot update stats messages: incomplete configuration.")
            return

        try:
            # Use data provider to fetch data
            if not self.data_provider.is_connected():
                logger.error("Data provider is not connected. Cannot update stats.")
                return            # Fetch data from the configured data source
            data = self.data_provider.fetch_data("Resumen_Mes_Actual")
            
            if not isinstance(data, list) or not data:
                logger.warning("Data from data provider is empty or in an unexpected format.")
                return

            # Normalize the data
            data = self.normalize_data(data)
            
            channel = await self.get_channel(self.stats_channel_id)
            if not channel:
                return

            # Generate and update Live mode stats
            live_stats_text = self.generate_stats_text(data, mode="live")
            try:
                live_message = await channel.fetch_message(self.stats_live_message_id)
                await live_message.edit(content=live_stats_text)
                logger.info("Live mode stats message updated successfully.")
            except discord.NotFound:
                # If the message was deleted, create a new one
                new_live_message = await channel.send(live_stats_text)
                self.stats_live_message_id = new_live_message.id
                logger.info(f"Created new Live mode stats message with ID: {new_live_message.id}")
            
            # Generate and update Squadron Battle stats
            sb_stats_text = self.generate_stats_text(data, mode="sb")
            try:
                sb_message = await channel.fetch_message(self.stats_sb_message_id)
                await sb_message.edit(content=sb_stats_text)
                logger.info("Squadron Battle stats message updated successfully.")
            except discord.NotFound:
                # If the message was deleted, create a new one
                new_sb_message = await channel.send(sb_stats_text)
                self.stats_sb_message_id = new_sb_message.id
                logger.info(f"Created new Squadron Battle stats message with ID: {new_sb_message.id}")

            # Update the leaderboard embeds
            await self.update_leaderboard_embeds(data)

            logger.info(f"All stats and leaderboard messages updated successfully. Next update in {update_period} minutes.")
        except Exception as e:
            logger.exception(f"Error updating stats messages: {e}")

    def generate_stats_text(self, data, mode="live"):
        """Generate a formatted text message with statistics fetched from the data provider.
        
        Args:
            data (list): The normalized data to display
            mode (str): Which mode to display - "live" or "sb"
            
        Returns:
            str: Formatted message text
        """
        # Define which columns to display based on mode
        if mode.lower() == "live":
            column_names = {
                "Jugador": "Player",
                "Kills/Live": "Kills",
                "Deaths/Live": "Deaths", 
                "Ratio/Live": "Ratio"
            }
            title = "🟢 **Live Mode Statistics - Current Month**"
            sort_key = "Ratio/Live"
            kills_key = "Kills/Live"
            deaths_key = "Deaths/Live"
        else:  # Squadron Battle
            column_names = {
                "Jugador": "Player",
                "Kills/SB": "Kills",
                "Deaths/SB": "Deaths",
                "Ratio/SB": "Ratio"
            }
            title = "🟣 **Squadron Battle Statistics - Current Month**"
            sort_key = "Ratio/SB"
            kills_key = "Kills/SB"
            deaths_key = "Deaths/SB"
        
        # Ensure all required columns exist, add empty values if they don't
        for row in data:
            for col in column_names.keys():
                if col not in row:
                    row[col] = ""
        
        # Filter out players with 0 kills AND 0 deaths
        filtered_data = []
        for row in data:
            # Convert values to float, handle empty strings or non-numeric values
            try:
                kills = float(row.get(kills_key, 0))
            except (ValueError, TypeError):
                kills = 0
                
            try:
                deaths = float(row.get(deaths_key, 0))
            except (ValueError, TypeError):
                deaths = 0
                
            # Only include players with non-zero kills or deaths
            if kills > 0 or deaths > 0:
                filtered_data.append(row)
                  # If all players are filtered out, show a message instead
        if not filtered_data:
            message = f"{title}\n```No activity recorded this month yet.```"
            datasource = self.config_manager.get('datasource', 'googlesheets')
            message += f"\nData source: {datasource}"
            return message
        
        # Sort the data by ratio (higher values first)
        try:
            sorted_data = sorted(filtered_data, key=lambda x: float(x.get(sort_key, 0)), reverse=True)
        except (ValueError, TypeError):
            # If sorting fails (e.g., non-numeric values), use the filtered data
            sorted_data = filtered_data
            logger.warning(f"Failed to sort data by {sort_key}, displaying unsorted data.")
    
        # Calculate column widths based on content
        column_widths = {}
        for col, short in column_names.items():
            # Get maximum width needed for this column
            header_width = len(short)
            content_width = max(len(str(row.get(col, ''))) for row in sorted_data) if sorted_data else 0
            column_widths[col] = max(header_width, content_width)
    
        # Build the table header
        header_parts = []
        for col, short in column_names.items():
            if col == "Jugador":
                header_parts.append(f"{short:<{column_widths[col]}}")
            else:
                # Align numeric column headers to the right
                header_parts.append(f"{short:>{column_widths[col]}}")
        
        header = " | ".join(header_parts)
        separator = "-" * (sum(column_widths.values()) + len(column_names) * 3 - 1)
    
        # Create the message with header and separator
        message = f"{title}\n```\n{header}\n{separator}\n"
    
        # Add rows to the table, handling missing values
        for row in sorted_data:
            row_parts = []
            for col in column_names:
                value = str(row.get(col, ''))[:column_widths[col]]
                if col == "Jugador":
                    # Align player names to the left
                    row_parts.append(f"{value:<{column_widths[col]}}")
                else:
                    # Align numeric values to the right
                    row_parts.append(f"{value:>{column_widths[col]}}")
            
            message += f"{' | '.join(row_parts)}\n"

        # Calculate total kills and deaths
        total_kills = 0
        total_deaths = 0
        for row in sorted_data:
            try:
                kills = float(row.get(kills_key, 0))
                total_kills += kills
            except (ValueError, TypeError):
                pass
                
            try:
                deaths = float(row.get(deaths_key, 0))
                total_deaths += deaths
            except (ValueError, TypeError):
                pass

        # Add a separator line
        message += f"{separator}\n"
        
        # Add the totals row with proper alignment
        totals_row = []
        for col in column_names.keys():
            if col == "Jugador":
                totals_row.append(f"{'TOTAL':<{column_widths[col]}}")
            elif col == kills_key:
                total_kills_str = str(int(total_kills) if total_kills.is_integer() else total_kills)
                totals_row.append(f"{total_kills_str:>{column_widths[col]}}")
            elif col == deaths_key:
                total_deaths_str = str(int(total_deaths) if total_deaths.is_integer() else total_deaths)
                totals_row.append(f"{total_deaths_str:>{column_widths[col]}}")
            else:
                totals_row.append(f"{'':<{column_widths[col]}}")
        
        message += f"{' | '.join(totals_row)}\n"

        # Add the timestamp of last update after the totals
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message += f"\nLast updated: {current_time}"
    
        message += "```"
        
        # Add data source info
        datasource = self.config_manager.get('datasource', 'googlesheets')
        message += f"\nData source: {datasource}"
        
        return message

    def normalize_data(self, data):
        """
        Normalize data from different sources to a standardized format.
        
        Args:
            data (list): A list of dictionaries with data from the provider
            
        Returns:
            list: The normalized data with standardized field names
        """
        if not data or not isinstance(data, list):
            return data
            
        # Determine the data source format by looking at the first record's keys
        data_format = 'googlesheets'  # Default format
        first_record_keys = set(data[0].keys())
        
        # Check if this is Supabase data by looking for specific field names
        if 'username' in first_record_keys and 'kills_live' in first_record_keys:
            data_format = 'supabase'
        
        # If it's already in the expected format, return as is
        if data_format == 'googlesheets':
            return data
            
        # For Supabase data, map to Google Sheets format
        normalized_data = []
        for record in data:
            normalized_record = {}
            for source_field, target_field in self.field_mappings[data_format].items():
                if source_field in record:
                    normalized_record[target_field] = record[source_field]
            normalized_data.append(normalized_record)
            
        return normalized_data

    @update_stats_task.before_loop
    async def before_update_stats_task(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()
        
    @commands.command(name='stats')
    async def fetch_stats(self, ctx):
        logger.info(f"Command 'stats' invoked by user: {ctx.author} in channel: {ctx.channel}")
        start_time = time.time()  # Start timing the command execution

        if not self.data_provider.is_connected():
            logger.warning("Data provider is not connected.")
            await ctx.send("Data provider is not connected. Please check the configuration.")
            return

        try:            # Fetch data from the configured data provider
            logger.info("Fetching data from data provider")
            data = self.data_provider.fetch_data("Resumen_Mes_Actual")
            logger.info(f"Received data with {len(data)} records")

            if not isinstance(data, list) or not data:
                logger.warning("The response data is empty or not in the expected format.")
                await ctx.send("The response data is empty or not in the expected format.")
                return

            # Normalize the data
            data = self.normalize_data(data)

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
            summary = "📊 **Statistics Summary**\n"
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
            logger.info("Successfully generated statistics summary.")
            await ctx.send(summary)
        except Exception as e:
            logger.exception(f"Error fetching data from data provider: {e}")
            await ctx.send(f"Error fetching data: {e}")
        finally:
            execution_time = time.time() - start_time
            logger.info(f"Command 'stats' executed in {execution_time:.2f} seconds.")

    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx, metric: str = "Kills/SB"):
        """Generate a leaderboard based on a specific metric."""
        logger.info(f"Command 'leaderboard' invoked by user: {ctx.author} with metric: {metric}")

        if not self.data_provider.is_connected():
            logger.warning("Data provider is not connected.")
            await ctx.send("Data provider is not connected. Please check the configuration.")
            return

        try:
            # Fetch data from the data provider
            data = self.data_provider.fetch_data("Resumen")
            
            if not isinstance(data, list) or not data:
                logger.warning("Data from data provider is empty or in an unexpected format.")
                await ctx.send("Data is empty or in an unexpected format.")
                return

            # Normalize the data
            data = self.normalize_data(data)

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
    # Get the config manager instance
    config_manager = get_config_manager()
    
    # Check if we have a Discord bot token
    if not config_manager.get('discord_bot_token'):
        logger.error("Discord bot token is not configured in the config file")
        return
    
    # Initialize bot with required intents
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    # Add the bot cog, passing the config_manager instead of raw config
    await bot.add_cog(StatusBoardBot(bot, config_manager))
    
    # Start the bot using the token from config_manager
    await bot.start(config_manager.get('discord_bot_token'))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
