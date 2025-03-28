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
import win32gui
import win32con
from pynput.keyboard import Controller, Key  # Import Controller and Key for keyboard interactions
import win32process
import psutil
import win32ui
import mss  # Add mss for GPU-rendered window capturing
import random  # Import random for sampling lines

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
    
    # Redirect to GUI log handler if in GUI mode
    if getattr(main, 'in_gui', False) and hasattr(main, 'gui_log_handler'):
        main.gui_log_handler(formatted_msg)
    else:
        print(formatted_msg)

def find_window_by_title(title, class_name=None, process_name=None):
    """Find a window by its title, class name, and process name."""
    def enum_windows_callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
            if class_name and win32gui.GetClassName(hwnd) != class_name:
                return
            if process_name:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    process = psutil.Process(pid)
                    if process.name() != process_name:
                        return
                except psutil.NoSuchProcess:
                    return
            windows.append(hwnd)

    windows = []
    win32gui.EnumWindows(enum_windows_callback, windows)
    return windows[0] if windows else None

def capture_window_screenshot(hwnd, output_path):
    """
    Capture a screenshot of a specific window using its handle.

    Args:
        hwnd (int): The handle of the window to capture.
        output_path (str): The file path to save the screenshot.
    """
    try:
        # Get the window's rectangle
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)

        # Define the top-right 200x200 region
        width = 200
        height = 200
        left = right - width

        # Use mss to capture the screen region
        with mss.mss() as sct:
            monitor = {
                "top": top,
                "left": left,
                "width": width,
                "height": height
            }
            screenshot = sct.grab(monitor)

            # Save the screenshot as a JPG file
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            img.save(output_path, format="JPEG", quality=85)

        output_message(None, f"Screenshot saved to {output_path}")

    except Exception as e:
        output_message(None, f"Error capturing screenshot: {e}")
        output_message(None, "Stack trace:\n{}".format(traceback.format_exc()))
        logging.error("Error capturing screenshot: %s", str(e))
        logging.error("Stack trace:\n%s", traceback.format_exc())
        raise  # Re-raise the exception to propagate it for further debugging

def send_keystrokes_to_window(window_title, keystrokes, screenshots_folder, **kwargs):
    """Send keystrokes to a specific window and capture a screenshot if PRINT_SCREEN_KEY is triggered."""
    try:
        hwnd = find_window_by_title(window_title, kwargs.get('class_name'), kwargs.get('process_name'))
        if not hwnd:
            output_message(None, f"Window with title '{window_title}' not found.")
            return

        # Bring the window to the foreground
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.05)  # Give some time for the window to focus

        # Simulate keystrokes
        keyboard = Controller()
        for key in keystrokes:
            if key == PRINT_SCREEN_KEY:
                # Capture a screenshot
                timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
                screenshot_path = os.path.join(screenshots_folder, f"screenshot_{timestamp}.jpg")
                capture_window_screenshot(hwnd, screenshot_path)
            elif key == RETURN_KEY:
                keyboard.tap(Key.enter)
            elif isinstance(key, str):
                for char in key:  # Send each character in the string
                    keyboard.tap(char)
                    time.sleep(0.05)  # Small delay between characters
            else:
                keyboard.tap(key)
            time.sleep(0.05)  # Small delay between keystrokes

    except Exception as e:
        output_message(None, f"Error sending keystrokes to window: {e}")

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.current_shard = None  # Initialize shard information
        self.current_version = None  # Initialize version information
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
        self.google_sheets_mapping = config.get('google_sheets_mapping', {})
        self.username = config.get('username', 'Unknown')
        self.use_googlesheet = config.get('use_googlesheet', False) and bool(self.google_sheets_webhook)
        self.google_sheets_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.screenshots_folder = os.path.join(os.path.dirname(self.log_file_path), "ScreenShots")
        if not os.path.exists(self.screenshots_folder):
            os.makedirs(self.screenshots_folder)
        self.autoshard = config.get('autoshard', False)  # Add autoshard attribute

        if not self.process_once:
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

        if not self.process_once:
            self.send_startup_message()

    def send_keystrokes_to_sc(self):
        """Send predefined keystrokes to the Star Citizen window."""
        send_keystrokes_to_window(
            "Star Citizen",
            [
                "º", "r_DisplaySessionInfo 1", RETURN_KEY,
                "º", PRINT_SCREEN_KEY,
                "º", "r_DisplaySessionInfo 0", RETURN_KEY,
                "º"
            ],
            self.screenshots_folder,
            class_name="CryENGINE",
            process_name="StarCitizen.exe"
        )

    def send_startup_keystrokes(self):
        """Send predefined keystrokes to the Star Citizen window at startup."""
        if self.current_mode == "SC_Default" and not self.process_once and self.autoshard:  # Use self.autoshard
            output_message(None, "Startup detected with mode SC_Default. Sending keystrokes to Star Citizen window.")
            self.send_keystrokes_to_sc()



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
        while not self.stop_event.is_set():
            if not self.use_googlesheet:
                time.sleep(1)
                continue
            try:
                queue_data = []
                try:
                    # Get queue items with timeout to check stop_event regularly
                    data, event_type = self.google_sheets_queue.get(timeout=1)
                    queue_data.append({'data':data,'sheet': "{}-{}".format(self.google_sheets_mapping.get(event_type), self.current_mode or 'None')})
                    self.google_sheets_queue.task_done()
                    
                    # Get any additional items that might be in the queue
                    while not self.google_sheets_queue.empty():
                        data, event_type = self.google_sheets_queue.get_nowait()
                        queue_data.append({'data':data,'sheet': self.google_sheets_mapping.get(event_type)})
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
        """Add data to Google Sheets queue"""
        if not self.use_googlesheet:
            return
        self.google_sheets_queue.put((data, event_type))

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
                        self.current_shard = qr_parts[1]  # Second value as shard
                        self.current_version = qr_parts[3]  # Fourth value as version
                        output_message(None, f"Shard updated: {self.current_shard}, Version updated: {self.current_version}")
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

        # Process patterns in google_sheets_mapping first
        processed_patterns = set()
        for pattern_name in self.google_sheets_mapping.keys():
            success, _ = self.detect_and_emit_generic(entry, pattern_name, send_message)
            if success:
                processed_patterns.add(pattern_name)

        # Process remaining patterns not in google_sheets_mapping
        for pattern_name in self.regex_patterns.keys():
            if pattern_name not in processed_patterns:
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
                mode_data['shard'] = self.current_shard or 'Unknown'  # Add shard information
                mode_data['version'] = self.current_version or 'Unknown'  # Add version information
                
                # Output message
                output_message(timestamp, f"Mode changed: '{old_mode or 'None'}' → '{new_mode}'")
                
                # Send to Discord if enabled
                if send_message and self.use_discord and 'mode_change' in self.discord_messages:
                    self.send_discord_message(mode_data, pattern_name='mode_change')
                
                # Only send keystrokes if send_message is True
                if new_mode == "SC_Default" and send_message and self.autoshard:
                    output_message(timestamp, "Mode changed to SC_Default. Sending keystrokes to Star Citizen window.")
                    self.send_keystrokes_to_sc()
                
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
                mode_data['shard'] = self.current_shard or 'Unknown'  # Add shard information
                mode_data['version'] = self.current_version or 'Unknown'  # Add version information
                
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
                'reason': 'Channel Disconnected',
                'shard': self.current_shard or 'Unknown',  # Add shard information
                'version': self.current_version or 'Unknown'  # Add version information
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
                
            data['shard'] = self.current_shard or 'Unknown'  # Add shard information
            data['version'] = self.current_version or 'Unknown'  # Add version information
            
            output_message_format = self.messages.get(pattern_name)
            if not output_message_format is None:
                output_message(timestamp, output_message_format.format(**data))
            if send_message:
                self.send_discord_message(data, pattern_name=pattern_name)
            
            # Send to Google Sheets if pattern is configured
            if pattern_name in self.google_sheets_mapping and send_message:
                self.update_google_sheets(data, pattern_name)
            
            return True, data
        return False, None

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

def emit_default_config(config_path, in_gui=False):
    with open(get_template_path(), 'r', encoding='utf-8') as template_file:
        template_config = json.load(template_file)
    if not in_gui:
        config = prompt_for_config_values(template_config)
    else:
        config = template_config
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

def main(process_all=False, use_discord=None, process_once=False, use_googlesheet=None, log_file_path=None, autoshard=None):
    try:
        app_path = get_application_path()
        config_path = os.path.join(app_path, "config.json")
        
        output_message(None, f"Loading config from: {config_path}")
        
        if not os.path.exists(config_path):
            output_message(None, f"Config file not found, creating default at: {config_path}")
            emit_default_config(config_path)
        
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

        # Set autoshard default: True for CLI, False for GUI
        if autoshard is None:
            autoshard = not hasattr(main, 'in_gui') or not main.in_gui
        config['autoshard'] = autoshard  # Add autoshard to the config

        # Override config values with command-line parameters if provided
        if not process_all:
            # Reverse logic: -p flag forces process_all to False
            config['process_all'] = True
        else:
            # Use the config value if -p flag not present
            config['process_all'] = bool(config.get('process_all', True))
            
        config['process_once'] = process_once or bool(config.get('process_once', False))

        # Create a file handler
        event_handler = LogFileHandler(config)
        
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

            # Call the startup keystrokes method only if autoshard is True
            if event_handler and event_handler.autoshard:
                output_message(None, "Sending startup keystrokes to Star Citizen window...")
                event_handler.send_startup_keystrokes()

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
        print(f"Usage: {sys.argv[0]} [--process-all | -p] [--no-discord | -nd] [--process-once | -o] [--no-googlesheet | -ng] [--debug | -d] [--autoshard | -a]")
        print("Options:")
        print("  --process-all, -p    Skip processing entire log file (overrides config)")
        print("  --no-discord, -nd    Do not send output to Discord webhook")
        print("  --process-once, -o   Process log file once and exit")
        print("  --no-googlesheet, -ng    Do not send output to Google Sheets webhook")
        print("  --debug, -d          Enable debug mode (e.g., save cropped images)")
        print("  --autoshard, -a      Automatically send startup keystrokes to Star Citizen window")
        print(f"Version: {get_version()}")
        sys.exit(0)
    
    process_all = '--process-all' in sys.argv or '-p' in sys.argv
    use_discord = not ('--no-discord' in sys.argv or '-nd' in sys.argv)
    process_once = '--process-once' in sys.argv or '-o' in sys.argv
    use_googlesheet = not ('--no-googlesheet' in sys.argv or '-ng' in sys.argv)
    debug_mode = '--debug' in sys.argv or '-d' in sys.argv
    autoshard = '--autoshard' in sys.argv or '-a' in sys.argv

    # Set debug mode globally
    main.debug_mode = debug_mode

    # Show version info on startup
    print(f"SC Log Analyzer v{get_version()} starting...")
    main(process_all, use_discord, process_once, use_googlesheet, autoshard=autoshard)