import os
import time
import re
import sys
import json
import requests
#from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler

def output_message(timestamp, message):
    if timestamp:
        print(f"{timestamp} - {message}")
    else:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"*{current_time} - {message}")

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

    def send_discord_message(self, message, technical=False, timestamp=None):
        """Send a message to Discord via webhook or stdout"""
        if not self.use_discord:
            return

        try:
            payload = {
                "content": message
            }
            url = self.technical_webhook_url if technical else self.discord_webhook_url
            response = requests.post(url, json=payload)
            
            # Check if the message was sent successfully
            if response.status_code not in [200, 204]:
                output_message(timestamp, f"Failed to send Discord message. Status code: {response.status_code}")  # Replace self.output_message
        except Exception as e:
            output_message(timestamp, f"Error sending Discord message: {e}")  # Replace self.output_message

    def on_modified(self, event):
        if event.src_path.lower() == self.log_file_path.lower():
            self.process_new_entries()

    def process_new_entries(self):
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
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
            output_message(None, "Unable to read log file. Make sure it's not locked by another process.")  # Replace self.output_message
        except Exception as e:
            output_message(None, f"Error reading log file: {e}")  # Replace self.output_message

    def process_entire_log(self):
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                entries = file.readlines()
                for entry in entries:
                    self.parse_log_entry(entry, send_message=False)
                self.last_position = file.tell()
        except PermissionError:
            output_message(None, "Unable to read log file. Make sure it's not locked by another process.")  # Replace self.output_message
        except Exception as e:
            output_message(None, f"Error reading log file: {e}")  # Replace self.output_message

    def parse_log_entry(self, entry, send_message=True):
        # Try standard detectors first
        if self.detect_player_activity(entry, send_message):
            return
        if self.detect_actor_death(entry, send_message):
            return
        if self.detect_commodity_activity(entry, send_message):
            return
            
        # Try generic detection for any other configured patterns
        for pattern_name in self.regex_patterns.keys():
            if pattern_name not in ['player', 'timestamp', 'zone', 'actor_death', 'commodity']:
                success, _ = self.detect_and_emit_generic(entry, pattern_name, send_message)
                if success:
                    return

    def detect_generic(self, entry, pattern):
        """
        Generic detection method that returns a dictionary of matched groups
        Args:
            entry: The log entry to analyze
            pattern: The regex pattern to match against
        Returns:
            Dictionary with matched groups or None if no match
        """
        match = re.search(pattern, entry)
        if match:
            return match.groupdict()
        return None

    def detect_and_emit_generic(self, entry, pattern_name, send_message=True):
        """
        Generic detection and message emission for any configured pattern
        Args:
            entry: Log entry to analyze
            pattern_name: Name of the pattern in regex_patterns config
            send_message: Whether to send the message or not
        Returns:
            Tuple of (bool, dict) - Success flag and matched data
        """
        if pattern_name not in self.regex_patterns:
            output_message(None, f"Pattern {pattern_name} not found in configuration")  # Replace self.output_message
            return False, None

        data = self.detect_generic(entry, self.regex_patterns[pattern_name])
        if data:
            # Extract player and action information
            player = data.get('player') or data.get('owner') or data.get('entity') or 'Unknown'
            action = pattern_name.replace('_', ' ').title()
            timestamp = data.get('timestamp')
            
            discord_message = f"⚡ **{action}**\n" \
                            f"**Player:** {player}"
            
            output_message(timestamp, f"{pattern_name} event for player {player}")  # Replace self.output_message
            if send_message:
                self.send_discord_message(discord_message, timestamp=timestamp)
            
            return True, data
        return False, None

    def detect_player_activity(self, entry, send_message=True):
        player_data = self.detect_generic(entry, self.regex_patterns['player'])
        timestamp_data = self.detect_generic(entry, self.regex_patterns['timestamp'])
        zone_data = self.detect_generic(entry, self.regex_patterns['zone'])
        
        if player_data and timestamp_data and zone_data:
            player_name = player_data['player']
            timestamp = timestamp_data['timestamp']
            action = zone_data['action']
            zone = zone_data['zone']
            
            discord_message = f"🚀 **Star Citizen Activity**\n" \
                            f"**Player:** {player_name}\n" \
                            f"**Action:** {action}\n" \
                            f"**Zone:** {zone}\n" \
                            f"**Timestamp:** {timestamp}"
            
            output_message(timestamp, f"Player {player_name} {action.lower()} zone {zone}")  # Replace self.output_message
            if send_message:
                self.send_discord_message(discord_message, timestamp=timestamp)
            
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
                self.send_discord_message(augmented_message, timestamp=timestamp)
            
            # Send technical information for important players
            if player_name in self.important_players:
                technical_message = f"activity,{timestamp},{player_name},{action},{zone}"
                self.send_discord_message(technical_message, technical=True, timestamp=timestamp)
            
            return True
        return False

    def detect_actor_death(self, entry, send_message=True):
        death_data = self.detect_generic(entry, self.regex_patterns['actor_death'])
        if death_data:
            victim = death_data['victim']
            zone = death_data['zone']
            killer = death_data['killer']
            weapon = death_data['weapon']
            damage_type = death_data['damage_type']
            timestamp = death_data['timestamp']
            
            if victim.startswith('PU_') or victim.startswith('Kopion_'):
                return False

            discord_message = f"💀 **Star Citizen Death Event**\n" \
                            f"**Victim:** {victim}\n" \
                            f"**Zone:** {zone}\n" \
                            f"**Killer:** {killer}\n" \
                            f"**Weapon:** {weapon}\n" \
                            f"**Damage Type:** {damage_type}\n" \
                            f"**Timestamp:** {timestamp}"
            
            output_message(timestamp, f"Player {victim} killed by {killer} in zone {zone} using {weapon} with damage type {damage_type}")  # Replace self.output_message
            if send_message:
                self.send_discord_message(discord_message, timestamp=timestamp)
            
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
                self.send_discord_message(technical_message, technical=True, timestamp=timestamp)
            
            return True
        return False

    def detect_commodity_activity(self, entry, send_message=True):
        commodity_data = self.detect_generic(entry, self.regex_patterns['commodity'])
        if commodity_data:
            owner = commodity_data['owner']
            commodity = commodity_data['commodity']
            zone = commodity_data['zone']
            timestamp = commodity_data['timestamp']
            
            discord_message = f"📦 **Star Citizen Commodity Activity**\n" \
                            f"**Owner:** {owner}\n" \
                            f"**Commodity:** {commodity}\n" \
                            f"**Zone:** {zone}\n" \
                            f"**Timestamp:** {timestamp}"
            
            output_message(timestamp, f"Commodity {commodity} owned by {owner} in zone {zone}")  # Replace self.output_message
            if send_message:
                self.send_discord_message(discord_message, timestamp=timestamp)
            
            # Update actor state
            self.actor_state[owner] = {
                'commodity': commodity,
                'zone': zone,
                'timestamp': timestamp
            }
            
            # Send technical information for important players
            if owner in self.important_players:
                technical_message = f"commodity,{timestamp},{owner},{commodity},{zone}"
                self.send_discord_message(technical_message, technical=True, timestamp=timestamp)
            
            return True
        return False

DEFAULT_CONFIG = {
    "log_file_path": os.path.join(os.path.dirname(__file__), "Game.log"),
    "discord_webhook_url": "",
    "technical_webhook_url": "",
    "regex_patterns": {
        "player": r"Player (?P<player>\w+)",
        "timestamp": r"\[(?P<timestamp>.*?)\]",
        "zone": r"Zone (?P<zone>\w+): (?P<action>\w+)",
        "actor_death": r"<(?P<timestamp>.*?)> \\[Notice\\] <Actor Death> CActor::Kill: '(?P<victim>.*?)' \\[(?P<victim_id>\\d+)\\] in zone '(?P<zone>.*?)' killed by '(?P<killer>.*?)' \\[(?P<killer_id>\\d+)\\] using '(?P<weapon>.*?)' \\[Class (?P<weapon_class>.*?)\\] with damage type '(?P<damage_type>.*?)' from direction x: (?P<direction_x>[\\d\\.-]+), y: (?P<direction_y>[\\d\\.-]+), z: (?P<direction_z>[\\d\\.-]+) \\[Team_ActorTech\\]\\[Actor\\]",
        "commodity": r"(?P<timestamp>\d+-\d+-\d+ \d+:\d+:\d+) - (?P<owner>\w+) acquired (?P<commodity>\w+) in zone (?P<zone>\w+)",
        "leave_zone": r"<(?P<timestamp>.*?)> \\[Notice\\] <CEntityComponentInstancedInterior::OnEntityLeaveZone> \\[InstancedInterior\\] OnEntityLeaveZone - InstancedInterior \\[(?P<zone>.*?)\\] \\[(?P<zone_id>\\d+)\\] -> Entity \\[(?P<entity>.*?)\\] \\[(?P<entity_id>\\d+)\\] -- m_openDoors\\[(?P<open_doors>\\d+)\\], m_managerGEID\\[(?P<manager_geid>\\d+)\\], m_ownerGEID\\[(?P<owner>.*?)\\]\\[(?P<entity_id>\\d+)\\], m_isPersistent\\[(?P<persistent>\\d+)\\] \\[Team_(?P<team>.*?)\\]\\[Cargo\\]"
    },
    "important_players": []
}

def emit_default_config(config_path):
    with open(config_path, 'w', encoding='utf-8') as config_file:
        json.dump(DEFAULT_CONFIG, config_file, indent=4)
    output_message(None, f"Default config emitted at {config_path}")  # Replace self.output_message

def main(process_all=False, use_discord=False, process_once=False):
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    
    if not os.path.exists(config_path):
        emit_default_config(config_path)
    
    with open(config_path, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    
    # Ensure the file exists
    if not os.path.exists(config['log_file_path']):
        output_message(None, f"Log file not found at {config['log_file_path']}")  # Replace self.output_message
        return

    # Create a file handler
    event_handler = LogFileHandler(config, process_all=process_all, use_discord=use_discord)
    
    if process_once:
        output_message(None, "Processing log file once and exiting...")  # Replace self.output_message
        event_handler.process_entire_log()
        return

    # Log monitoring status just before starting the observer
    output_message(None, f"Monitoring log file: {config['log_file_path']}")  # Replace self.output_message
    output_message(None, f"Sending updates to {'Discord webhook' if use_discord else 'stdout'}")  # Replace self.output_message

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
        output_message(None, "Monitoring stopped by user.")  # Replace self.output_message
        observer.stop()
    except Exception as e:
        output_message(None, f"Unexpected error: {e}")  # Replace self.output_message
    finally:
        # Wait for the observer thread to finish
        observer.join()

if __name__ == "__main__":
    # Check for optional flags
    if '--help' in sys.argv or '-h' in sys.argv:
        print("Usage: log_analyzer.exe [--process-all | -p] [--discord | -d] [--process-once | -o]")  # Use print
        print("Options:")  # Use print
        print("  --process-all, -p    Process entire log file before monitoring")  # Use print
        print("  --discord, -d        Send output to Discord webhook")  # Use print
        print("  --process-once, -o   Process log file once and exit")  # Use print
        sys.exit(0)
    
    process_all = '--process-all' in sys.argv or '-p' in sys.argv
    use_discord = '--discord' in sys.argv or '-d' in sys.argv
    process_once = '--process-once' in sys.argv or '-o' in sys.argv
    main(process_all, use_discord, process_once)