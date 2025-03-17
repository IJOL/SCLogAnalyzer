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

# Import version information
try:
    from version import get_version
except ImportError:
    def get_version():
        return "unknown"

def output_message(timestamp, message):
    if timestamp:
        print(f"{timestamp} - {message}")
    else:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"*{current_time} - {message}")

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.log_file_path = config['log_file_path']
        self.discord_webhook_url = config['discord_webhook_url']
        self.technical_webhook_url = config.get('technical_webhook_url',False)
        self.regex_patterns = config['regex_patterns']
        self.messages = config.get('messages', {})
        self.important_players = config['important_players']
        self.last_position = 0
        self.actor_state = {}
        self.process_all = config.get('process_all', False)
        self.use_discord = config.get('use_discord', False) and bool(self.discord_webhook_url)
        self.process_once = config.get('process_once', False)
        self.discord_messages = config.get('discord', {})
        self.google_sheets_webhook = config.get('google_sheets_webhook', '')
        self.google_sheets_mapping = config.get('google_sheets_mapping', {})
        self.username = config.get('username', 'Unknown')
        self.filter_username_pattern = config.get('filter_username_pattern', None)
        self.use_googlesheet = config.get('use_googlesheet', False) and bool(self.google_sheets_webhook)
        self.google_sheets_queue = queue.Queue()
        self.google_sheets_thread = threading.Thread(target=self.process_google_sheets_queue)
        self.google_sheets_thread.daemon = True
        self.google_sheets_thread.start()
        self.version = get_version()
        
        # Mode tracking (new approach)
        self.current_mode = None
        
        # Compile mode regex patterns
        self.mode_start_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <Context Establisher Done> establisher=\"(?P<establisher>.*?)\" runningTime=(?P<running_time>[\d\.]+) map=\"(?P<map>.*?)\" gamerules=\"(?P<gamerules>.*?)\" sessionId=\"(?P<session_id>[\w-]+)\" \[(?P<tags>.*?)\]")
        self.mode_end_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <Channel Disconnected> cause=(?P<cause>\d+) reason=\"(?P<reason>.*?)\" frame=(?P<frame>\d+) map=\"(?P<map>.*?)\" gamerules=\"(?P<gamerules>.*?)\" remoteAddr=(?P<remote_addr>[\d\.:\w]+) localAddr=(?P<local_addr>[\d\.:\w]+) connection=\{(?P<connection_major>\d+), (?P<connection_minor>\d+)\} session=(?P<session>[\w-]+) node_id=(?P<node_id>[\w-]+) nickname=\"(?P<nickname>.*?)\" playerGEID=(?P<player_geid>\d+) uptime_secs=(?P<uptime>[\d\.]+) \[(?P<tags>.*?)\]")

        # Simpler Channel Disconnected pattern for other types of disconnects
        self.simple_disconnect_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <Channel Disconnected>")

        if self.process_all:
            self.process_entire_log()
        else:
            # Move to the end of the file if we're not processing everything
            self.last_position = self._get_file_end_position()
            output_message(None, f"Skipping to the end of log file (position {self.last_position})")

        self.send_startup_message()
        
    def _get_file_end_position(self):
        """Get the current end position of the log file"""
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                # Go to the end of the file
                file.seek(0, 2)  # 0 is the offset, 2 means from the end of the file
                return file.tell()
        except Exception as e:
            output_message(None, f"Error getting file end position: {e}")
            return 0

    def send_startup_message(self):
        """Send a startup message to Discord webhook if Discord is active"""
        if self.use_discord:
            startup_message = f"🚀 **Startup Alert**\n**Username:** {self.username}\n**Version:** {self.version}\n**Status:** Monitoring started with Discord active"
            self.send_discord_message(startup_message, technical=True)

    def send_discord_message(self, data, pattern_name=None, technical=False):
        """Send a message to Discord via webhook or stdout"""
        if not self.use_discord:
            return

        try:
            if technical:
                # Technical messages are sent as-is
                payload = {"content": data}
                url = self.technical_webhook_url or self.discord_webhook_url
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
            if not self.use_googlesheet:
                time.sleep(1)
                continue
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
        if not self.use_googlesheet:
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
        if not self.use_googlesheet:
            return
        self.google_sheets_queue.put((data, f"{event_type}-{self.current_mode or 'None'}"))

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
        # First check for mode changes
        if self.detect_mode_change(entry, send_message):
            return
            
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

    def detect_mode_change(self, entry, send_message=True):
        """
        Detect if the log entry represents a change in game mode using the new regex patterns
        Args:
            entry: The log entry to analyze
            send_message: Whether to send a message on mode change
        Returns:
            Boolean indicating if a mode change was detected
        """
        # Check for mode start (Context Establisher Done)
        start_match = self.mode_start_regex.search(entry)
        if start_match:
            mode_data = start_match.groupdict()
            new_mode = mode_data.get('gamerules')
            timestamp = mode_data.get('timestamp')
            
            # If it's a different mode than the current one, update it
            if new_mode != self.current_mode:
                old_mode = self.current_mode
                self.current_mode = new_mode
                
                # Format the mode data for output
                mode_data['mode'] = new_mode
                mode_data['username'] = self.username
                mode_data['status'] = 'entered'
                mode_data['old_mode'] = old_mode or 'None'
                
                # Output message
                output_message(timestamp, f"Mode changed: '{old_mode or 'None'}' → '{new_mode}'")
                
                # Send to Discord if enabled
                if send_message and self.use_discord and 'mode_change' in self.discord_messages:
                    self.send_discord_message(mode_data, pattern_name='mode_change')
                
                return True
        
        # Check for mode end (Channel Disconnected with gamerules)
        end_match = self.mode_end_regex.search(entry)
        if end_match:
            mode_data = end_match.groupdict()
            gamerules = mode_data.get('gamerules')
            timestamp = mode_data.get('timestamp')
            
            # Only consider it an end if it matches the current mode
            if gamerules == self.current_mode:
                # Format the mode data for output
                mode_data['mode'] = self.current_mode
                mode_data['username'] = self.username
                mode_data['status'] = 'exited'
                
                # Output message
                output_message(timestamp, f"Exited mode: '{self.current_mode}'")
                
                # Reset current mode
                self.current_mode = None
                
                # Send to Discord if enabled
                if send_message and self.use_discord and 'mode_change' in self.discord_messages:
                    self.send_discord_message(mode_data, pattern_name='mode_change')
                
                return True
        
        # Check for simple disconnects (for modes that don't have the full disconnect message)
        if self.current_mode and self.simple_disconnect_regex.search(entry):
            timestamp = self.simple_disconnect_regex.search(entry).group('timestamp')
            
            # Create mode data for the message
            mode_data = {
                'timestamp': timestamp,
                'mode': self.current_mode,
                'username': self.username,
                'status': 'exited',
                'reason': 'Channel Disconnected'
            }
            
            # Output message
            output_message(timestamp, f"Exited mode: '{self.current_mode}'")
            
            # Reset current mode
            self.current_mode = None
            
            # Send to Discord if enabled
            if send_message and self.use_discord and 'mode_change' in self.discord_messages:
                self.send_discord_message(mode_data, pattern_name='mode_change')
            
            return True
            
        return False

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
                # Extract victim and killer names for case-insensitive matching
                victim = data.get('victim', '').lower()
                killer = data.get('killer', '').lower()
                username_lower = self.username.lower()
                
                # Check if either victim or killer matches the username (case-insensitive)
                if not (victim == username_lower or killer == username_lower):
                    return False, None

            # Extract player and action information
            data['player'] = data.get('player') or data.get('owner') or data.get('entity') or 'Unknown'
            data['action'] = pattern_name.replace('_', ' ').title()
            timestamp = data.get('timestamp')
            data['username'] = self.username
            
            # Add current mode to data if active
            if self.current_mode:
                data['current_mode'] = self.current_mode
            else:
                data['current_mode'] = 'None'
                
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
        
        # Add current mode to data if active
        if self.current_mode:
            data['current_mode'] = self.current_mode
        else:
            data['current_mode'] = 'None'
            
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
    config['log_file_path'] = os.path.join(get_application_path(), "Game.log")
    
 
    with open(config_path, 'w', encoding='utf-8') as config_file:
        json.dump(config, config_file, indent=4)
    output_message(None, f"Default config emitted at {config_path}")

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

def is_valid_url(url):
    """Validate if the given string is a correctly formatted URL"""
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def main(process_all=False, use_discord=None, process_once=False, use_googlesheet=None):
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
        output_message(None, f"Log file not found at {config['log_file_path']}")
        return

    # Determine if Discord should be used based on the webhook URL and command-line parameter
    discord_webhook_url = config.get('discord_webhook_url')
    if use_discord is None:
        if not bool(config.get('use_discord', True)):
            config['use_discord'] = False
        else:
            config['use_discord'] = is_valid_url(discord_webhook_url)
    else:
        config['use_discord'] = use_discord

    # Determine if Google Sheets should be used based on the webhook URL and command-line parameter
    google_sheets_webhook = config.get('google_sheets_webhook')
    if use_googlesheet is None:
        if not bool(config.get('use_googlesheet', True)):
            config['use_googlesheet'] = False
        else:
            config['use_googlesheet'] = is_valid_url(google_sheets_webhook)
    else:
        config['use_googlesheet'] = use_googlesheet


    # Override config values with command-line parameters if provided
    config['process_all'] = process_all or bool(config.get('process_all', False))
    config['process_once'] = process_once or bool(config.get('process_once', False))

    # Create a file handler
    event_handler = LogFileHandler(config)
    
    if event_handler.process_once:
        output_message(None, "Processing log file once and exiting...")
        event_handler.process_entire_log()
        return

    # Log monitoring status just before starting the observer
    output_message(None, f"Monitoring log file: {config['log_file_path']}")
    output_message(None, f"Sending updates to {'Discord webhook' if event_handler.use_discord else 'stdout'}")

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
        output_message(None, "Monitoring stopped by user.")
        observer.stop()
    except Exception as e:
        output_message(None, f"Unexpected error: {e}")
    finally:
        # Wait for the observer thread to finish
        observer.join()

if __name__ == "__main__":
    # Check for optional flags
    if '--help' in sys.argv or '-h' in sys.argv:
        print(f"SC Log Analyzer v{get_version()}")
        print(f"Usage: {sys.argv[0]} [--process-all | -p] [--no-discord | -nd] [--process-once | -o] [--no-googlesheet | -ng]")
        print("Options:")
        print("  --process-all, -p    Process entire log file before monitoring")
        print("  --no-discord, -nd    Do not send output to Discord webhook")
        print("  --process-once, -o   Process log file once and exit")
        print("  --no-googlesheet, -ng    Do not send output to Google Sheets webhook")
        print(f"Version: {get_version()}")
        sys.exit(0)
    
    process_all = '--process-all' in sys.argv or '-p' in sys.argv
    use_discord = not ('--no-discord' in sys.argv or '-nd' in sys.argv)
    process_once = '--process-once' in sys.argv or '-o' in sys.argv
    use_googlesheet = not ('--no-googlesheet' in sys.argv or '-ng' in sys.argv)
    
    # Show version info on startup
    print(f"SC Log Analyzer v{get_version()} starting...")
    main(process_all, use_discord, process_once, use_googlesheet)