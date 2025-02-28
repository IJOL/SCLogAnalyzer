import os
import time
import re
import sys
import json
import requests
import traceback
import threading
import queue
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
        self.messages = config.get('messages', {})
        self.important_players = config['important_players']
        self.last_position = 0
        self.actor_state = {}
        self.process_all = process_all
        self.use_discord = use_discord
        self.discord_messages = config.get('discord', {})
        self.google_sheets_webhook = config.get('google_sheets_webhook', '')
        self.google_sheets_mapping = config.get('google_sheets_mapping', {})
        self.username = config.get('username', 'Unknown')
        self.filter_username_pattern = config.get('filter_username_pattern', None)
        self.google_sheets_queue = queue.Queue()
        self.google_sheets_thread = threading.Thread(target=self.process_google_sheets_queue)
        self.google_sheets_thread.daemon = True
        self.google_sheets_thread.start()

        if self.process_all:
            self.process_entire_log()

    def send_discord_message(self, data, pattern_name=None, technical=False):
        """Send a message to Discord via webhook or stdout"""
        if not self.use_discord:
            return

        try:
            if technical:
                # Technical messages are sent as-is
                payload = {"content": data}
                url = self.technical_webhook_url
            elif pattern_name and pattern_name in self.discord_messages:
                # Get all possible player references from the data
                player_fields = ['player', 'owner', 'victim', 'killer', 'entity']
                players = [data.get(field) for field in player_fields if data.get(field)]
                
                # Determine if we should send the message based on important_players
                should_send = (
                    not self.important_players or  # Send if no important players configured
                    any(player in self.important_players for player in players)  # Or if any player is important
                )
                
                if should_send:
                    # Add alert emoji if any player is in important_players
                    if any(player in self.important_players for player in players):
                        data['alert'] = '🔊 Sound Alert!'
                    else:
                        data['alert'] = ''  # Empty string for non-important players
                        
                    payload = {"content": self.discord_messages[pattern_name].format(**data)}
                    url = self.discord_webhook_url
                else:
                    return
            else:
                return
                
            response = requests.post(url, json=payload)
            if response.status_code not in [200, 204]:
                output_message(None, f"Failed to send Discord message. Status code: {response.status_code}")
        except Exception as e:
            output_message(None, f"Error sending Discord message: {e}")

    def process_google_sheets_queue(self):
        """Worker thread to process Google Sheets queue"""
        while True:
            try:
                queue_data = []
                while not self.google_sheets_queue.empty():
                    data, event_type = self.google_sheets_queue.get()
                    queue_data.append({'data':data,'sheet': self.google_sheets_mapping.get(event_type)})
                    self.google_sheets_queue.task_done()
                
                if queue_data:
                    self._send_to_google_sheets(queue_data)
            except Exception as e:
                output_message(None, f"Exception in Google Sheets worker thread: {e}")

    def _send_to_google_sheets(self, queue_data):
        """Send data to Google Sheets via webhook"""
        if not self.google_sheets_webhook:
            return

        try:
            payload =  queue_data
            response = requests.post(self.google_sheets_webhook, json=payload)
            if response.status_code == 200:
                output_message(None, "Data sent to Google Sheets successfully")
            else:
                output_message(None, f"Error sending data to Google Sheets: {response.status_code} - {response.text}")
        except Exception as e:
            output_message(None, f"Exception sending data to Google Sheets: {e}")

    def update_google_sheets(self, data, event_type):
        """Add data to Google Sheets queue"""
        self.google_sheets_queue.put((data, event_type))

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
            output_message(None, f"Error reading log file: {e}\n{traceback.format_exc()}")  # Replace self.output_message

    def parse_log_entry(self, entry, send_message=True):
        # Try filter_username_pattern first if defined
        if self.filter_username_pattern and self.filter_username_pattern in self.regex_patterns:
            success, _ = self.detect_and_emit_generic(entry, self.filter_username_pattern, send_message)
            if success:
                return
            
        # Try commodity activity next
        if self.detect_commodity_activity(entry, send_message):
            return
            
        # Try generic detection for any other configured patterns
        for pattern_name in self.regex_patterns.keys():
            if pattern_name not in ['timestamp', 'zone', 'commodity'] and pattern_name != self.filter_username_pattern:
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
            output_message(None, f"Pattern {pattern_name} not found in configuration")
            return False, None

        data = self.detect_generic(entry, self.regex_patterns[pattern_name])
        if data:
            # Apply username filter if this is the pattern we want to filter
            if pattern_name == self.filter_username_pattern:
                # Extract victim and killer names for exact matching
                victim = data.get('victim', '')
                killer = data.get('killer', '')
                
                # Check if either victim or killer matches the username
                if not (victim == self.username or killer == self.username):
                    return False, None

            # Extract player and action information
            data['player'] = data.get('player') or data.get('owner') or data.get('entity') or 'Unknown'
            data['action'] = pattern_name.replace('_', ' ').title()
            timestamp = data.get('timestamp')
            data['username'] = self.username
            output_message_format = self.messages.get(pattern_name)
            if not output_message_format is None:
                output_message(timestamp, output_message_format.format(**data))
            if send_message:
                self.send_discord_message(data, pattern_name=pattern_name)
            
            # Send to Google Sheets if pattern is configured
            if pattern_name in self.google_sheets_mapping:
                self.update_google_sheets(data, pattern_name)
            
            return True, data
        return False, None

    def detect_commodity_activity(self, entry, send_message=True):
        # Check if required pattern exists
        if 'commodity' not in self.regex_patterns:
            output_message(None, "Missing 'commodity' pattern in configuration")
            return False
            
        commodity_data = self.detect_generic(entry, self.regex_patterns['commodity'])
        if not commodity_data:
            return False
            
        # Validate required fields
        required_fields = ['owner', 'commodity', 'zone', 'timestamp']
        missing_fields = [field for field in required_fields if not commodity_data.get(field)]
        
        if missing_fields:
            output_message(None, f"Missing required fields in commodity data: {', '.join(missing_fields)}")
            return False

        # All validation passed, proceed with processing
        data = {field: commodity_data[field] for field in required_fields}
        
        message = self.messages.get("commodity_activity")
        if not message:
            output_message(None, "Missing 'commodity_activity' message template")
            return False
            
        output_message(data['timestamp'], message.format(**data))
        if send_message:
            self.send_discord_message(data, pattern_name='commodity_activity')
        
        # Update actor state
        self.actor_state[data['owner']] = {
            'commodity': data['commodity'],
            'zone': data['zone'],
            'timestamp': data['timestamp']
        }
        
        # Send technical information for important players
        if data['owner'] in self.important_players:
            technical_message = f"commodity,{data['timestamp']},{data['owner']},{data['commodity']},{data['zone']}"
            self.send_discord_message(technical_message, technical=True)
        
        return True

DEFAULT_CONFIG = {
    "log_file_path": os.path.join(os.path.dirname(__file__), "Game.log"),
    "discord_webhook_url": "",
    "technical_webhook_url": "",
    "regex_patterns": {
        "timestamp": r"\[(?P<timestamp>.*?)\]",
        "zone": r"Zone (?P<zone>\w+): (?P<action>\w+)",
        "actor_death": r"<(?P<timestamp>.*?)> \\[Notice\\] <Actor Death> CActor::Kill: '(?P<victim>.*?)' \\[(?P<victim_id>\\d+)\\] in zone '(?P<zone>.*?)' killed by '(?P<killer>.*?)' \\[(?P<killer_id>\\d+)\\] using '(?P<weapon>.*?)' \\[Class (?P<weapon_class>.*?)\\] with damage type '(?P<damage_type>.*?)' from direction x: (?P<direction_x>[\\d\\.-]+), y: (?P<direction_y>[\\d\\.-]+), z: (?P<direction_z>[\\d\\.-]+) \\[Team_ActorTech\\]\\[Actor\\]",
        "commodity": r"(?P<timestamp>\d+-\d+-\d+ \d+:\d+:\d+) - (?P<owner>\w+) acquired (?P<commodity>\w+) in zone (?P<zone>\w+)",
        "leave_zone": r"<(?P<timestamp>.*?)> \\[Notice\\] <CEntityComponentInstancedInterior::OnEntityLeaveZone> \\[InstancedInterior\\] OnEntityLeaveZone - InstancedInterior \\[(?P<zone>.*?)\\] \\[(?P<zone_id>\\d+)\\] -> Entity \\[(?P<entity>.*?)\\] \\[(?P<entity_id>\\d+)\\] -- m_openDoors\\[(?P<open_doors>\\d+)\\], m_managerGEID\\[(?P<manager_geid>\\d+)\\], m_ownerGEID\\[(?P<owner>.*?)\\]\\[(?P<entity_id>\\d+)\\], m_isPersistent\\[(?P<persistent>\\d+)\\] \\[Team_(?P<team>.*?)\\]\\[Cargo\\]",
    },
    "important_players": [],
    "messages": {
        "actor_death": "Player {victim} killed by {killer} in zone {zone} using {weapon} with damage type {damage_type} at {timestamp}",
        "leave_zone": "Entity {entity} left zone {zone} at {timestamp}",
        "commodity_activity": "Commodity {commodity} owned by {owner} in zone {zone}"
    },
    "discord": {
        "actor_death": "💀 **Death Alert**\n**Victim:** {victim}\n**Killer:** {killer}\n**Zone:** {zone}\n**Weapon:** {weapon}\n**Type:** {damage_type}\n{alert}",
        "leave_zone": "🚪 **Zone Change**\n**Entity:** {entity}\n**Zone:** {zone}\n{alert}",
        "commodity_activity": "📦 **Commodity**\n**Owner:** {owner}\n**Item:** {commodity}\n**Zone:** {zone}\n{alert}"
    },
    "google_sheets_webhook": "",  # Add this line
    "google_sheets_mapping": {
        "actor_death": "deaths",
        "enter_ship": "ships",
        "commodity": "trading",
        "quantum_jump": "navigation"
    },
    "filter_username_pattern": "",  # Specify which pattern name should filter by username
}

def emit_default_config(config_path):
    with open(config_path, 'w', encoding='utf-8') as config_file:
        json.dump(DEFAULT_CONFIG, config_file, indent=4)
    output_message(None, f"Default config emitted at {config_path}")  # Replace self.output_message

def get_application_path():
    """Determine the correct application path whether running as .py or .exe"""
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle (exe)
        return os.path.dirname(sys.executable)
    else:
        # If the application is run as a python script
        return os.path.dirname(os.path.abspath(__file__))

def main(process_all=False, use_discord=False, process_once=False):
    app_path = get_application_path()
    config_path = os.path.join(app_path, "config.json")
    
    output_message(None, f"Loading config from: {config_path}")
    
    if not os.path.exists(config_path):
        output_message(None, f"Config file not found, creating default at: {config_path}")
        emit_default_config(config_path)
    
    with open(config_path, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
        output_message(None, f"Config loaded successfully from: {config_path}")
    
    # If log_file_path is relative, make it relative to the application path
    if not os.path.isabs(config['log_file_path']):
        config['log_file_path'] = os.path.join(app_path, config['log_file_path'])

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
        print(f"Usage: {sys.argv[0]} [--process-all | -p] [--discord | -d] [--process-once | -o]")  # Use print
        print("Options:")  # Use print
        print("  --process-all, -p    Process entire log file before monitoring")  # Use print
        print("  --discord, -d        Send output to Discord webhook")  # Use print
        print("  --process-once, -o   Process log file once and exit")  # Use print
        sys.exit(0)
    
    process_all = '--process-all' in sys.argv or '-p' in sys.argv
    use_discord = '--discord' in sys.argv or '-d' in sys.argv
    process_once = '--process-once' in sys.argv or '-o' in sys.argv
    main(process_all, use_discord, process_once)