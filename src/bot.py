
import os
import json
import logging
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
        self.actor_state = {}
        self.important_players = config['important_players']
        self.update_status_board.start()

    @tasks.loop(minutes=10)
    async def update_status_board(self):
        channel = self.bot.get_channel(self.config['technical_channel_id'])
        if channel:
            status_board = "📊 **Special Players Status Board**\n"
            for player, state in self.actor_state.items():
                if player in self.important_players:
                    status_board += f"**Player:** {player}\n"
                    for key, value in state.items():
                        status_board += f"**{key.capitalize()}:** {value}\n"
                    status_board += "\n"
            await channel.send(status_board)
        else:
            logger.error("Technical channel not found")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'Logged in as {self.bot.user}')
        await self.update_status_board()

def main(config_path):
    with open(config_path, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)

    bot = commands.Bot(command_prefix='!')
    bot.add_cog(StatusBoardBot(bot, config))

    bot.run(config['discord_bot_token'])

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Usage: bot.py <path_to_config_file>")
        sys.exit(1)

    config_path = sys.argv[1]
    main(config_path)