import os
import time
import re
import sys
import json
import requests
import traceback
import threading
import queue
import signal
import logging  # Add logging for error handling
#from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler
from PIL import Image, ImageEnhance  # Import ImageEnhance for contrast adjustment
from pyzbar.pyzbar import decode  # For QR code detection
from config_utils import emit_default_config, get_application_path, get_template_path
from gui_module import WindowsHelper  # Import the new helper class for Windows-related functionality

# Configure logging
logging.basicConfig(level=logging.ERROR, filename='error.log', filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')

# Define constants
CROP_WIDTH = 650
CROP_HEIGHT = 380
PRINT_SCREEN_KEY = "print_screen"  # Add constant for PrintScreen key
RETURN_KEY = "return"  # Add constant for Return key

# Import version information
try:
    from version import get_version
except ImportError:
    def get_version():
        return "unknown"

class MessageRateLimiter:
    """Class to handle rate limiting of repeated messages."""
    def __init__(self, timeout=20, max_duplicates=4, cleanup_interval=60):
        """
        Initialize the rate limiter.
        
        Args:
            timeout: Time in seconds before allowing the same message again
            max_duplicates: Maximum number of duplicate messages allowed within timeout period
            cleanup_interval: Time in seconds to keep stale messages before cleanup
        """
        self.messages = {}  # {message_hash: (timestamp, count)}
        self.timeout = timeout
        self.max_duplicates = max_duplicates
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()  # Track the last cleanup time

    def should_send(self, message, message_type=None):
        """
        Check if a message should be sent based on rate limiting rules.
        
        Args:
            message: The message content
            message_type: Optional type identifier for the message (e.g., 'discord', 'stdout')
            
        Returns:
            bool: True if message should be sent, False otherwise
        """
        current_time = time.time()
        # Perform cleanup periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self.cleanup_messages(current_time)
        
        # Create a unique key based on message content and type
        key = f"{message_type}:{message}" if message_type else message
        
        # Check if this message has been seen before
        if key in self.messages:
            last_time, count = self.messages[key]
            
            # If message has been sent too many times within timeout, block it
            if count >= self.max_duplicates and current_time - last_time < self.timeout:
                # Update count but don't reset the timer
                self.messages[key] = (last_time, count + 1)
                return False
                
            # If timeout has passed, reset counter
            if current_time - last_time >= self.timeout:
                self.messages[key] = (current_time, 1)
                return True
                
            # Update count and timestamp
            self.messages[key] = (last_time, count + 1)
        else:
            # First time seeing this message
            self.messages[key] = (current_time, 1)
            
        return True
    
    def cleanup_messages(self, current_time):
        """
        Remove stale messages from the store.
        
        Args:
            current_time: The current time to compare against message timestamps.
        """
        stale_keys = [
            key for key, (last_time, _) in self.messages.items()
            if current_time - last_time > self.cleanup_interval
        ]
        for key in stale_keys:
            del self.messages[key]
        self.last_cleanup = current_time

    def get_stats(self, message, message_type=None):
        """Get statistics about a message."""
        key = f"{message_type}:{message}" if message_type else message
        if key in self.messages:
            last_time, count = self.messages[key]
            return {
                "last_sent": last_time,
                "count": count,
                "blocked": count > self.max_duplicates and (time.time() - last_time < self.timeout)
            }
        return None

def output_message(timestamp, message):
    """
    Output a message to stdout or a custom handler in GUI mode.
    
    Args:
        timestamp: Timestamp string or None
        message: Message to output
    """
    formatted_msg = ""
    if timestamp:
        formatted_msg = f"{timestamp} - {message}"
    else:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        formatted_msg = f"*{current_time} - {message}"
    
    # Check if rate limiter exists and if message should be sent
    rate_limiter = getattr(main, 'rate_limiter', None)
    if rate_limiter and not rate_limiter.should_send(formatted_msg, 'stdout'):
        # Message is rate limited - don't output
        return
    
    # Redirect to GUI log handler if in GUI mode
    if getattr(main, 'in_gui', False) and hasattr(main, 'gui_log_handler') and callable(main.gui_log_handler):
        # Call the GUI log handler with the formatted message
        main.gui_log_handler(formatted_msg)
    else:
        print(formatted_msg)

class Event:
    """A simple event system to allow subscribers to listen for updates."""
    def __init__(self):
        self._subscribers = []

    def subscribe(self, callback):
        """Subscribe to the event."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback):
        """Unsubscribe from the event."""
        self._subscribers.remove(callback)

    def emit(self, *args, **kwargs):
        """Emit the event to all subscribers."""
        for callback in self._subscribers:
            callback(*args, **kwargs)

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, config, **kwargs):
        # Restore instance attributes
        self.on_shard_version_update = Event()  # Event for shard and version updates
        self.on_mode_change = Event()  # Event for mode changes
        # Handle subscriptions passed via kwargs
        if 'on_shard_version_update' in kwargs and callable(kwargs['on_shard_version_update']):
            self.on_shard_version_update.subscribe(kwargs['on_shard_version_update'])
        if 'on_mode_change' in kwargs and callable(kwargs['on_mode_change']):
            self.on_mode_change.subscribe(kwargs['on_mode_change'])
        self.rate_limiter = MessageRateLimiter(
            timeout=config.get('rate_limit_timeout', 60),
            max_duplicates=config.get('rate_limit_max_duplicates', 3)
        )
        self.username = config.get('username', 'Unknown')  # Username as an instance attribute
        self.current_shard = None  # Initialize shard information
        self.current_version = None  # Initialize Star Citizen version information
        self.script_version = get_version()  # Initialize script version
        self.log_file_path = config['log_file_path']
        self.discord_webhook_url = config['discord_webhook_url']
        self.technical_webhook_url = config.get('technical_webhook_url', False)
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
        self.use_googlesheet = config.get('use_googlesheet', False) and bool(self.google_sheets_webhook)
        self.google_sheets_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.screenshots_folder = os.path.join(os.path.dirname(self.log_file_path), "ScreenShots")
        self.google_sheets_mapping = config.get('google_sheets_mapping', [])
        if not os.path.exists(self.screenshots_folder):
            os.makedirs(self.screenshots_folder)

        if not self.process_once:
            self.google_sheets_thread = threading.Thread(target=self.process_google_sheets_queue)
            self.google_sheets_thread.daemon = True
            self.google_sheets_thread.start()
        self.version = get_version()
        
        # Mode tracking (new approach)
        self.current_mode = None
        
        # Compile mode regex patterns
        self.mode_start_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <Context Establisher Done> establisher=\"(?P<establisher>.*?)\" runningTime=(?P<running_time>[\d\.]+) map=\"(?P<map>.*?)\" gamerules=\"(?P<gamerules>.*?)\" sessionId=\"(?P<session_id>[\w-]+)\" \[(?P<tags>.*?)\]")
        self.nickname_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <Channel Connection Complete> map=\"(?P<map>.*?)\" gamerules=\"(?P<gamerules>.*?)\" remoteAddr=(?P<remote_addr>.*?) localAddr=(?P<local_addr>.*?) connection=\{(?P<connection_major>\d+), (?P<connection_minor>\d+)\} session=(?P<session_id>[\w-]+) node_id=(?P<node_id>[\w-]+) nickname=\"(?P<nickname>.*?)\" playerGEID=(?P<player_geid>\d+) uptime_secs=(?P<uptime>[\d\.]+)")
        self.mode_end_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <Channel Disconnected> cause=(?P<cause>\d+) reason=\"(?P<reason>.*?)\" frame=(?P<frame>\d+) map=\"(?P<map>.*?)\" gamerules=\"(?P<gamerules>.*?)\" remoteAddr=(?P<remote_addr>[\d\.:\w]+) localAddr=(?P<local_addr>[\d\.:\w]+) connection=\{(?P<connection_major>\d+), (?P<connection_minor>\d+)\} session=(?P<session>[\w-]+) node_id=(?P<node_id>[\w-]+) nickname=\"(?P<nickname>.*?)\" playerGEID=(?P<player_geid>\d+) uptime_secs=(?P<uptime>[\d\.]+) \[(?P<tags>.*?)\]")

        # Simpler Channel Disconnected pattern for other types of disconnects
        self.simple_disconnect_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <Channel Disconnected>")

        if self.process_all:
            self.process_entire_log()
        else:
            # Move to the end of the file if we're not processing everything
            self.last_position = self._get_file_end_position()
            output_message(None, f"Skipping to the end of log file (position {self.last_position})")

    def add_state_data(self, data):
        """
        Add state data (current_mode, shard, username, version) as first-level keys to the given data.

        Args:
            data (dict): The data to which state information will be added.

        Returns:
            dict: The updated data with state information.
        """
        return {
            **data,
            "mode": self.current_mode or "None",
            "shard": self.current_shard or "Unknown",
            "username": self.username or "Unknown",
            "version": self.current_version or "Unknown",
            "script_version": self.script_version or "Unknown",
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),            
        }

    def stop(self):
        """Stop the handler and cleanup threads"""
        self.stop_event.set()
        output_message(None, "Stopping log analyzer...")
        self.cleanup_threads()
        output_message(None, "Log analyzer stopped successfully")

    def cleanup_threads(self):
        """Ensure all threads are stopped"""
        # Wait for Google Sheets thread to finish processing remaining items
        if self.google_sheets_thread.is_alive():
            output_message(None, "Waiting for Google Sheets queue to complete...")
            self.google_sheets_queue.join()
            # Give it a moment to exit gracefully
            time.sleep(0.5)

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
        """Send a startup message to Discord webhook if Discord is active."""
        if self.use_discord:
            startup_message = f"🚀 **Startup Alert**\n**Username:** {self.username}\n**Script Version:** {self.script_version}\n**Status:** Monitoring started with Discord active"
            self.send_discord_message(startup_message, technical=True)

    def send_discord_message(self, data, pattern_name=None, technical=False):
        """Send a message to Discord via webhook or stdout"""
        if not self.use_discord:
            return

        try:
            content = None
            url = None
            
            if technical:
                # Technical messages are sent as-is
                content = data
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
                        
                    content = self.discord_messages[pattern_name].format(**data)
                    url = self.discord_webhook_url
                else:
                    return
                
            else:
                return
            
            # Check if this message should be rate limited
            if not self.rate_limiter.should_send(content, f'discord_{pattern_name}'):
                output_message(None, f"Rate limited Discord message for pattern: {pattern_name}")
                return
                
            payload = {"content": content}
            response = requests.post(url, json=payload)
            if response.status_code not in [200, 204]:
                output_message(None, f"Failed to send Discord message. Status code: {response.status_code}")
        except Exception as e:
            output_message(None, f"Error sending Discord message: {e}")

    def process_google_sheets_queue(self):
        """Worker thread to process Google Sheets queue"""
        while not self.stop_event.is_set():
            if not self.use_googlesheet:
                time.sleep(1)
                continue
            try:
                queue_data = []
                try:
                    # Get queue items with timeout to check stop_event regularly
                    data, event_type = self.google_sheets_queue.get(timeout=1)
                    queue_data.append({'data': data, 'sheet': data.get('sheet',self.current_mode or 'None')})  # Use current_mode as sheet
                    self.google_sheets_queue.task_done()
                    
                    # Get any additional items that might be in the queue
                    while not self.google_sheets_queue.empty():
                        data, event_type = self.google_sheets_queue.get_nowait()
                        queue_data.append({'data': data, 'sheet': data.get('sheet',self.current_mode or 'None')})  # Use current_mode as sheet
                        self.google_sheets_queue.task_done()
                except queue.Empty:
                    # No items in queue, just continue loop
                    pass
                
                if queue_data:
                    self._send_to_google_sheets(queue_data)
            except Exception as e:
                output_message(None, f"Exception in Google Sheets worker thread: {e}")
        
        output_message(None, "Google Sheets worker thread stopped")

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
        """
        Add data to Google Sheets queue, including state information.

        Args:
            data (dict): The data to send.
            event_type (str): The type of event triggering the update.
        """
        if not self.use_googlesheet:
            return False

        # Add state data to the payload
        data_with_state = self.add_state_data(data)
        self.google_sheets_queue.put((data_with_state, event_type))
        return True

    def on_modified(self, event):
        if event.src_path.lower() == self.log_file_path.lower():
            self.process_new_entries()

    def on_created(self, event):
        """Handle new files in monitored folders."""
        # Skip files with the 'cropped_' prefix
        if os.path.basename(event.src_path).startswith("cropped_"):
            return

        if event.src_path.lower().startswith(self.screenshots_folder.lower()):
            self.process_new_screenshot(event.src_path)
        elif event.src_path.lower() == self.log_file_path.lower():
            self.process_new_entries()

    def process_new_screenshot(self, file_path):
        """Process a new screenshot to extract shard and version information."""
        max_retries = 3
        retry_delay = 0.5  # 500 milliseconds

        for attempt in range(max_retries):
            try:
                # Open the image
                image = Image.open(file_path)

                # Ensure the image is fully loaded
                image.load()

                # Check the image size
                width, height = image.size
                if width == 200 and height == 200:
                    # If the image already has the correct size, skip cropping
                    top_right = image
                else:
                    # Otherwise, crop a fixed 200x200 pixel area from the top-right corner
                    top_right = image.crop((width - 200, 0, width, 200))

                # Convert to grayscale for QR code detection
                top_right = top_right.convert("L")  # Convert to grayscale

                # Use the central 50x50 pixels for threshold calculation
                central_x_start = (top_right.width - 50) // 2
                central_y_start = (top_right.height - 50) // 2
                central_region = top_right.crop((
                    central_x_start,
                    central_y_start,
                    central_x_start + 50,
                    central_y_start + 50
                ))

                # Calculate the simple mean of the central region
                pixels = central_region.load()
                pixel_values = [pixels[x, y] for x in range(central_region.width) for y in range(central_region.height)]
                dark_threshold = sum(pixel_values) // len(pixel_values)

                # Output the threshold value
                output_message(None, f"Darkness threshold: {dark_threshold}")

                # Darken only the pixels that are already dark
                pixels = top_right.load()
                for x in range(top_right.width):
                    for y in range(top_right.height):
                        current_pixel = pixels[x, y]
                        if current_pixel < dark_threshold:  # Only darken pixels below the threshold
                            pixels[x, y] = max(0, current_pixel - 150)  # Darken by reducing brightness


                # Try to decode QR code
                qr_codes = decode(top_right)
                if qr_codes:
                    # Extract shard and version information from QR code
                    qr_data = qr_codes[0].data.decode('utf-8')
                    qr_parts = qr_data.split()
                    if len(qr_parts) >= 4:
                        new_shard = qr_parts[1]
                        new_version = qr_parts[3]

                        # Check if shard or version has changed
                        if new_shard != self.current_shard or new_version != self.current_version:
                            self.current_shard = new_shard
                            self.current_version = new_version
                            output_message(None, f"Shard updated: {self.current_shard}, Version updated: {self.current_version}")

                            # Emit the event to notify subscribers
                            self.on_shard_version_update.emit(self.current_shard, self.current_version, self.username)
                    else:
                        output_message(None, "QR code does not contain sufficient information.")
                else:
                    output_message(None, "No QR code detected.")
                    
                # Save the cropped image only if debug mode is enabled
                if getattr(main, 'debug_mode', False) or not qr_codes:
                    cropped_path = os.path.join(
                        os.path.dirname(file_path),
                        f"cropped_{os.path.basename(file_path)}"
                    )
                    top_right.save(cropped_path, format="JPEG", quality=85)
                    output_message(None, f"Debug mode: Cropped image saved to {cropped_path}")

                # Optionally send shard info to Discord or Google Sheets
                if self.current_shard:
                    self.send_discord_message({"shard_info": self.current_shard, "version_info": self.current_version}, pattern_name="shard_info")

                return  # Exit the retry loop if successful

            except IOError as e:
                if attempt < max_retries - 1:
                    output_message(None, f"Retrying screenshot processing ({attempt + 1}/{max_retries}) due to error: {e}")
                    time.sleep(retry_delay)  # Wait before retrying
                else:
                    output_message(None, f"Error processing screenshot {file_path}: {e}")

    def process_latest_screenshot(self):
        """
        Find and process the latest image in the screenshots folder.
        """
        try:
            if not os.path.exists(self.screenshots_folder):
                return

            # Get all files in the screenshots folder
            files = [
                os.path.join(self.screenshots_folder, f)
                for f in os.listdir(self.screenshots_folder)
                if os.path.isfile(os.path.join(self.screenshots_folder, f)) and not f.startswith("cropped_")
            ]

            if not files:
                return

            # Find the latest file by modification time
            latest_file = max(files, key=os.path.getmtime)
            output_message(None, f"Processing latest screenshot: {latest_file}")
            self.process_new_screenshot(latest_file)

        except Exception as e:
            output_message(None, f"Error processing latest screenshot: {e}")

    def process_new_entries(self):
        try:
            current_file_size = os.path.getsize(self.log_file_path)
            
            # Detect log truncation
            if self.last_position > current_file_size:
                output_message(None, "Log file truncated. Resetting position to the beginning.")
                self.last_position = 0

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
        except FileNotFoundError:
            output_message(None, "Log file not found. Waiting for it to be created...")
            time.sleep(1)  # Wait briefly for the file to reappear
        except PermissionError:
            output_message(None, "Unable to read log file. Make sure it's not locked by another process.")
        except Exception as e:
            output_message(None, f"Error reading log file: {e}")
            logging.error("An error occurred: %s", str(e))
            logging.error("Stack trace:\n%s", traceback.format_exc())

    def process_entire_log(self):
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                entries = file.readlines()
                for entry in entries:
                    self.parse_log_entry(entry, send_message=False)
                self.last_position = file.tell()
        except PermissionError:
            output_message(None, "Unable to read log file. Make sure it's not locked by another process.")
        except Exception as e:
            output_message(None, f"Error reading log file: {e}\n{traceback.format_exc()}")
            logging.error("An error occurred: %s", str(e))
            logging.error("Stack trace:\n%s", traceback.format_exc())

    def parse_log_entry(self, entry, send_message=True):
        # First check for mode changes
        if self.detect_mode_change(entry, send_message):
            return

        # First process patterns in google_sheets_mapping
        for pattern_name in self.google_sheets_mapping:
            success, _ = self.detect_and_emit_generic(entry, pattern_name, send_message)
            if success:
                return

        # Then process patterns in regex_patterns, skipping those in google_sheets_mapping
        for pattern_name in self.regex_patterns.keys():
            if pattern_name not in self.google_sheets_mapping:
                success, _ = self.detect_and_emit_generic(entry, pattern_name, send_message)
                if success:
                    return

    def detect_mode_change(self, entry, send_message=True):
        """
        Detect if the log entry represents a change in game mode using the new regex patterns.
        """
        nickname_match = self.nickname_regex.search(entry)
        if nickname_match:
            nickname_data = nickname_match.groupdict()
            new_nickname = nickname_data.get('nickname')
            
            # Update username if nickname is available
            if new_nickname and new_nickname != self.username:
                old_username = self.username
                self.username = new_nickname
                output_message(nickname_data.get('timestamp'), f"Username updated: '{old_username}' → '{new_nickname}'")
                
                # Emit the event to notify subscribers about nickname/username change
                self.on_shard_version_update.emit(self.current_shard, self.current_version, self.username)
                
                # Send startup Discord message after getting the username for the first time
                if old_username == 'Unknown' and not self.process_once:
                    self.send_startup_message()

                return True

        # Check for mode start (Context Establisher Done)
        start_match = self.mode_start_regex.search(entry)
        if start_match:
            mode_data = start_match.groupdict()
            new_mode = mode_data.get('gamerules')
            timestamp = mode_data.get('timestamp')

            # Update username with the nickname from the regex match
            self.username = mode_data.get('nickname', self.username)

            # If it's a different mode than the current one, update it
            if new_mode != self.current_mode:
                old_mode = self.current_mode
                self.current_mode = new_mode

                # Emit the event to notify subscribers about mode change
                self.on_mode_change.emit(new_mode, old_mode)

                # Format the mode data for output
                mode_data['status'] = 'entered'
                mode_data['old_mode'] = old_mode or 'None'
                mode_data=self.add_state_data(mode_data)  # Add state data to the mode data

                # Emit the event to notify subscribers
                self.on_shard_version_update.emit(self.current_shard, self.current_version, self.username)

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
                # Emit the event to notify subscribers about mode exit
                self.on_mode_change.emit(None, self.current_mode)

                # Format the mode data for output
                mode_data['status'] = 'exited'
                mode_data=self.add_state_data(mode_data)  # Add state data to the mode data

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

            # Emit the event to notify subscribers about mode exit
            self.on_mode_change.emit(None, self.current_mode)

            # Create mode data for the message
            mode_data = {
                'timestamp': timestamp,
                'status': 'exited',
                'reason': 'Channel Disconnected',
            }
            mode_data = self.add_state_data(mode_data)  # Add state data to the mode data
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
        Generic detection and message emission for any configured pattern.

        Args:
            entry: Log entry to analyze.
            pattern_name: Name of the pattern in regex_patterns config.
            send_message: Whether to send the message or not.

        Returns:
            Tuple of (bool, dict) - Success flag and matched data.
        """
        if pattern_name not in self.regex_patterns:
            output_message(None, f"Pattern {pattern_name} not found in configuration")
            return False, None

        data = self.detect_generic(entry, self.regex_patterns[pattern_name])
        if data:
            # Extract player and action information
            data['player'] = data.get('player') or data.get('owner') or data.get('entity') or 'Unknown'
            data['action'] = pattern_name.replace('_', ' ').title()
            timestamp = data.get('timestamp')
            data['username'] = self.username  # Use instance attribute

            # Add state data to the detected data
            data = self.add_state_data(data)

            output_message_format = self.messages.get(pattern_name)
            if not output_message_format is None:
                output_message(timestamp, output_message_format.format(**data))
            if send_message:
                self.send_discord_message(data, pattern_name=pattern_name)

            # Send to Google Sheets if enabled and pattern is in the mapping
            if send_message and pattern_name in self.google_sheets_mapping:
                self.update_google_sheets(data, pattern_name)

            return True, data
        return False, None

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

def signal_handler(signum, frame):
    """Handle external signals to stop the application"""
    output_message(None, f"Received signal {signum}, shutting down...")
    if hasattr(signal_handler, 'event_handler') and signal_handler.event_handler:
        signal_handler.event_handler.stop()
    if hasattr(signal_handler, 'observer') and signal_handler.observer:
        signal_handler.observer.stop()

def stop_monitor(event_handler, observer):
    """
    Stop the observer and Google Sheets thread cleanly.
    
    Args:
        event_handler: The LogFileHandler instance.
        observer: The Observer instance.
    """
    output_message(None, "Stopping monitor...")
    if observer.is_alive():
        observer.stop()
        observer.join()
    event_handler.stop()
    output_message(None, "Monitor stopped successfully")

def startup(process_all=False, use_discord=None, process_once=False, use_googlesheet=None, log_file_path=None, **kwargs):
    """
    Initialize the log analyzer infrastructure and allow the caller to pass event subscriptions via kwargs.

    Args:
        process_all: Whether to process the entire log file.
        use_discord: Whether to use Discord for notifications.
        process_once: Whether to process the log file once and exit.
        use_googlesheet: Whether to use Google Sheets for data storage.
        log_file_path: Path to the log file.
        kwargs: Additional arguments for event subscriptions or configurations.
    """
    try:
        app_path = get_application_path()
        config_path = os.path.join(app_path, "config.json")
        
        # Log tool name and executable version
        tool_name = "SC Log Analyzer"
        version = get_version()
        output_message(None, f"Starting {tool_name} {version}")
        logging.info(f"{tool_name} {version} started")

        output_message(None, f"Loading config from: {config_path}")
        
        if not os.path.exists(config_path):
            output_message(None, f"Config file not found, creating default at: {config_path}")
            emit_default_config(config_path)  # Pass template_path if needed
        
        with open(config_path, 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
            output_message(None, f"Config loaded successfully from: {config_path}")
        
        # If a custom log file path is provided, use it (for GUI)
        if log_file_path:
            config['log_file_path'] = log_file_path
        # If log_file_path is relative, make it relative to the application path
        elif not os.path.isabs(config['log_file_path']):
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
        if not process_all:
            # Reverse logic: -p flag forces process_all to False
            config['process_all'] = True
        else:
            # Use the config value if -p flag not present
            config['process_all'] = bool(config.get('process_all', True))
            
        config['process_once'] = process_once or bool(config.get('process_once', False))

        # Create a global rate limiter for the application
        main.rate_limiter = MessageRateLimiter(
            timeout=config.get('rate_limit_timeout', 10),
            max_duplicates=config.get('rate_limit_max_duplicates', 3)
        )

        # Create a file handler with kwargs for event subscriptions
        event_handler = LogFileHandler(config, **kwargs)

        if event_handler.process_once:
            output_message(None, "Processing log file once and exiting...")
            event_handler.process_entire_log()
            return event_handler

        # Log monitoring status just before starting the observer
        output_message(None, f"Monitoring log file: {config['log_file_path']}")
        output_message(None, f"Sending updates to {'Discord webhook' if event_handler.use_discord else 'stdout'}")

        # Create an observer
        observer = Observer()
        observer.schedule(event_handler, path=os.path.dirname(config['log_file_path']), recursive=False)
        observer.schedule(event_handler, path=event_handler.screenshots_folder, recursive=False)  # Monitor screenshots folder
            # Store references for signal handler
        signal_handler.event_handler = event_handler
        signal_handler.observer = observer    
        # Return the initialized handler and observer without starting processing
        return event_handler, observer
    except Exception as e:
        logging.error("An error occurred: %s", str(e))
        logging.error("Stack trace:\n%s", traceback.format_exc())
        raise

def main(process_all=False, use_discord=None, process_once=False, use_googlesheet=None, log_file_path=None):
    try:
        event_handler, observer = startup(process_all, use_discord, process_once, use_googlesheet, log_file_path)

        # If in GUI mode, start the observer in a separate thread and return immediately
        if hasattr(main, 'in_gui') and main.in_gui:
            observer_thread = threading.Thread(target=observer.start)
            observer_thread.daemon = True
            observer_thread.start()
            return event_handler, observer
        
        # Register signal handlers if not in a GUI environment
        if not hasattr(main, 'in_gui') or not main.in_gui:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Start the observer
            observer.start()

            # Ensure monitoring is started before generating screenshots
            output_message(None, "Monitoring started successfully.")

            # Keep the script running until stop event is set
            while not event_handler.stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            output_message(None, "Monitoring stopped by user.")
            stop_monitor(event_handler, observer)
        except Exception as e:
            output_message(None, f"Unexpected error: {e}")
            stop_monitor(event_handler, observer)
        finally:
            # Wait for the observer thread to finish
            observer.join()
            return event_handler
    except Exception as e:
        logging.error("An error occurred: %s", str(e))
        logging.error("Stack trace:\n%s", traceback.format_exc())
        raise

if __name__ == "__main__":
    # Check for optional flags
    if '--help' in sys.argv or '-h' in sys.argv:
        print(f"SC Log Analyzer v{get_version()}")
        print(f"Usage: {sys.argv[0]} [--process-all | -p] [--no-discord | -nd] [--process-once | -o] [--no-googlesheet | -ng] [--debug | -d]")
        print("Options:")
        print("  --process-all, -p    Skip processing entire log file (overrides config)")
        print("  --no-discord, -nd    Do not send output to Discord webhook")
        print("  --process-once, -o   Process log file once and exit")
        print("  --no-googlesheet, -ng    Do not send output to Google Sheets webhook")
        print("  --debug, -d          Enable debug mode (e.g., save cropped images)")
        print(f"Version: {get_version()}")
        sys.exit(0)
    
    process_all = '--process-all' in sys.argv or '-p' in sys.argv
    use_discord = not ('--no-discord' in sys.argv or '-nd' in sys.argv)
    process_once = '--process-once' in sys.argv or '-o' in sys.argv
    use_googlesheet = not ('--no-googlesheet' in sys.argv or '-ng' in sys.argv)
    debug_mode = '--debug' in sys.argv or '-d' in sys.argv

    # Set debug mode globally
    main.debug_mode = debug_mode

    # Show version info on startup
    print(f"SC Log Analyzer v{get_version()} starting...")
    main(process_all, use_discord, process_once, use_googlesheet)