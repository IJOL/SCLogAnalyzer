import os
import time
import re
import sys
import json
import logging
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('sc_discord_logger.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, config, process_all=False, use_discord=False):
        self.log_file_path = config['log_file_path']
        self.discord_webhook_url = config['discord_webhook_url']
        self.technical_webhook_url = config['technical_webhook_url']
        self.regex_patterns = config['regex_patterns']
        self.important_players = config['important_players']
        self.last_position = 0
        self.actor_state = {}
        self.process_all = process_all
        self.use_discord = use_discord

        if self.process_all:
            self.process_entire_log()

    def send_discord_message(self, message, technical=False):
        """Send a message to Discord via webhook or stdout"""
        if not self.use_discord:
            print(message)
            return

        try:
            payload = {
                "content": message
            }
            url = self.technical_webhook_url if technical else self.discord_webhook_url
            response = requests.post(url, json=payload)
            
            # Check if the message was sent successfully
            if response.status_code not in [200, 204]:
                logger.error(f"Failed to send Discord message. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")

    def on_modified(self, event):
        if event.src_path.lower() == self.log_file_path.lower():
            self.process_new_entries()

    def process_new_entries(self):
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as file:
                # Move to the last read position
                file.seek(self.last_position)
                
                # Read new entries
                new_entries = file.readlines()
                
                # Update last position
                self.last_position = file.tell()
                
                # Process each new entry
                for entry in new_entries:
                    self.parse_log_entry(entry)
        except PermissionError:
            logger.error("Unable to read log file. Make sure it's not locked by another process.")
        except Exception as e:
            logger.error(f"Error reading log file: {e}")

    def process_entire_log(self):
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as file:
                entries = file.readlines()
                for entry in entries:
                    self.parse_log_entry(entry, send_message=False)
                self.last_position = file.tell()
        except PermissionError:
            logger.error("Unable to read log file. Make sure it's not locked by another process.")
        except Exception as e:
            logger.error(f"Error reading log file: {e}")

    def parse_log_entry(self, entry, send_message=True):
        if self.detect_player_activity(entry, send_message):
            return
        if self.detect_actor_death(entry, send_message):
            return
        if self.detect_commodity_activity(entry, send_message):
            return

    def detect_player_activity(self, entry, send_message=True):
        player_match = re.search(self.regex_patterns['player'], entry)
        timestamp_match = re.search(self.regex_patterns['timestamp'], entry)
        
        if player_match and timestamp_match:
            player_name = player_match.group('player')
            timestamp = timestamp_match.group('timestamp')
            
            zone_match = re.search(self.regex_patterns['zone'], entry)
            
            if zone_match:
                action = zone_match.group('action')
                zone = zone_match.group('zone')
                
                discord_message = f"🚀 **Star Citizen Activity**\n" \
                                  f"**Player:** {player_name}\n" \
                                  f"**Action:** {action}\n" \
                                  f"**Zone:** {zone}\n" \
                                  f"**Timestamp:** {timestamp}"
                
                logger.info(f"Player {player_name} {action.lower()} zone {zone}")
                if send_message:
                    self.send_discord_message(discord_message)
                
                # Update actor state
                self.actor_state[player_name] = {
                    'action': action,
                    'zone': zone,
                    'timestamp': timestamp
                }
                
                # Send augmented notification for important players
                if player_name in self.important_players:
                    augmented_message = f"🔔 **Important Player Activity**\n" \
                                        f"**Player:** {player_name}\n" \
                                        f"**Action:** {action}\n" \
                                        f"**Zone:** {zone}\n" \
                                        f"**Timestamp:** {timestamp}\n" \
                                        f"🔊 **Sound Alert!**"
                    self.send_discord_message(augmented_message)
                
                # Send technical information for important players
                if player_name in self.important_players:
                    technical_message = f"activity,{timestamp},{player_name},{action},{zone}"
                    self.send_discord_message(technical_message, technical=True)
                
                return True
        return False

    def detect_actor_death(self, entry, send_message=True):
        actor_death_match = re.search(self.regex_patterns['actor_death'], entry)
        if actor_death_match:
            timestamp = actor_death_match.group('timestamp')
            victim = actor_death_match.group('victim')
            zone = actor_death_match.group('zone')
            killer = actor_death_match.group('killer')
            weapon = actor_death_match.group('weapon')
            damage_type = actor_death_match.group('damage_type')
            
            discord_message = f"💀 **Star Citizen Death Event**\n" \
                              f"**Victim:** {victim}\n" \
                              f"**Zone:** {zone}\n" \
                              f"**Killer:** {killer}\n" \
                              f"**Weapon:** {weapon}\n" \
                              f"**Damage Type:** {damage_type}\n" \
                              f"**Timestamp:** {timestamp}"
            
            logger.info(f"Player {victim} killed by {killer} in zone {zone} using {weapon} with damage type {damage_type}")
            if send_message:
                self.send_discord_message(discord_message)
            
            # Update actor state
            self.actor_state[victim] = {
                'status': 'dead',
                'zone': zone,
                'timestamp': timestamp,
                'killed_by': killer,
                'weapon': weapon,
                'damage_type': damage_type
            }
            
            # Send technical information for important players
            if victim in self.important_players or killer in self.important_players:
                technical_message = f"death,{timestamp},{victim},{zone},{killer},{weapon},{damage_type}"
                self.send_discord_message(technical_message, technical=True)
            
            return True
        return False

    def detect_commodity_activity(self, entry, send_message=True):
        commodity_match = re.search(self.regex_patterns['commodity'], entry)
        timestamp_match = re.search(self.regex_patterns['timestamp'], entry)
        
        if commodity_match and timestamp_match:
            owner = commodity_match.group('owner')
            commodity = commodity_match.group('commodity')
            zone = commodity_match.group('zone')
            timestamp = timestamp_match.group('timestamp')
            
            discord_message = f"📦 **Star Citizen Commodity Activity**\n" \
                              f"**Owner:** {owner}\n" \
                              f"**Commodity:** {commodity}\n" \
                              f"**Zone:** {zone}\n" \
                              f"**Timestamp:** {timestamp}"
            
            logger.info(f"Commodity {commodity} owned by {owner} in zone {zone}")
            if send_message:
                self.send_discord_message(discord_message)
            
            # Update actor state
            self.actor_state[owner] = {
                'commodity': commodity,
                'zone': zone,
                'timestamp': timestamp
            }
            
            # Send technical information for important players
            if owner in self.important_players:
                technical_message = f"commodity,{timestamp},{owner},{commodity},{zone}"
                self.send_discord_message(technical_message, technical=True)
            
            return True
        return False

DEFAULT_CONFIG = {
    "log_file_path": os.path.join(os.path.dirname(sys.executable), "Game.log"),
    "discord_webhook_url": "",
    "technical_webhook_url": "",
    "regex_patterns": {
        "player": r"Player (?P<player>\w+)",
        "timestamp": r"\[(?P<timestamp>.*?)\]",
        "zone": r"Zone (?P<zone>\w+): (?P<action>\w+)",
        "actor_death": r"(?P<timestamp>\d+-\d+-\d+ \d+:\d+:\d+) - (?P<victim>\w+) was killed by (?P<killer>\w+) in zone (?P<zone>\w+) with (?P<weapon>\w+) \((?P<damage_type>\w+)\)",
        "commodity": r"(?P<timestamp>\d+-\d+-\d+ \d+:\d+:\d+) - (?P<owner>\w+) acquired (?P<commodity>\w+) in zone (?P<zone>\w+)"
    },
    "important_players": []
}

def emit_default_config(config_path):
    with open(config_path, 'w', encoding='utf-8') as config_file:
        json.dump(DEFAULT_CONFIG, config_file, indent=4)
    logger.info(f"Default config emitted at {config_path}")

def main(process_all=False, use_discord=False):
    config_path = os.path.join(os.path.dirname(sys.executable), "config.json")
    
    if not os.path.exists(config_path):
        emit_default_config(config_path)
    
    with open(config_path, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    
    logger.info(f"Monitoring log file: {config['log_file_path']}")
    logger.info(f"Sending updates to {'Discord webhook' if use_discord else 'stdout'}")
    
    # Ensure the file exists
    if not os.path.exists(config['log_file_path']):
        logger.error(f"Log file not found at {config['log_file_path']}")
        return

    # Create a file handler
    event_handler = LogFileHandler(config, process_all=process_all, use_discord=use_discord)
    
    # Create an observer
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(config['log_file_path']), recursive=False)
    
    try:
        # Start the observer
        observer.start()
        
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Allow clean exit
        logger.info("Monitoring stopped by user.")
        observer.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        # Wait for the observer thread to finish
        observer.join()

if __name__ == "__main__":
    # Check for optional flags
    if '--help' in sys.argv or '-h' in sys.argv:
        print("Usage: log_analyzer.exe [--process-all | -p] [--discord | -d]")
        sys.exit(0)
    
    process_all = '--process-all' in sys.argv or '-p' in sys.argv
    use_discord = '--discord' in sys.argv or '-d' in sys.argv
    main(process_all, use_discord)