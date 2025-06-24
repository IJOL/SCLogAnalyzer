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
from datetime import datetime  # Fix: import datetime for timestamp handling
#from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler
from PIL import Image, ImageEnhance  # Import ImageEnhance for contrast adjustment
from pyzbar.pyzbar import decode  # For QR code detection
from bs4 import BeautifulSoup  # For profile scraping
# Using absolute imports instead of relative ones
from helpers.config_utils import get_application_path, get_config_manager
from helpers.supabase_manager import supabase_manager  # Import Supabase manager for cloud storage
from helpers.message_bus import message_bus, MessageLevel  # Import at module level
from helpers.data_provider import get_data_provider  # Import data provider
from helpers.rate_limiter import MessageRateLimiter
from helpers.async_profile import scrape_profile_async  # Import profile scraper helper

# Configure logging with application path and executable name
app_path = get_application_path()
executable_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]
error_log_path = os.path.join(app_path, f"{executable_name}.log")
logging.basicConfig(level=logging.ERROR, filename=error_log_path, filemode='a', 
                   format='%(asctime)s - %(levelname)s - %(message)s')

# Define constants
PRINT_SCREEN_KEY = "print_screen"  # Add constant for PrintScreen key
RETURN_KEY = "return"  # Add constant for Return key

# Import version information
try:
    # Using absolute import
    from version import get_version
except ImportError:
    def get_version():
        return "unknown"

# Instancia única de rate limiter para todos los contextos (stdout, discord, realtime)
rate_limiter = MessageRateLimiter(timeout=300, max_duplicates=1)

def output_message(timestamp, message, regex_pattern=None, level=None):
    """
    Output a message using the message bus.

    Args:
        timestamp: Timestamp string or None.
        message: Message to output.
        regex_pattern: The regex pattern name that matched the message (optional).
        level: Message priority level (optional).
    """
    # Check if rate limiter exists and if message should be sent
    rate_limiter = getattr(main, 'rate_limiter', None)
    if rate_limiter and not rate_limiter.should_send(message, 'stdout'):
        return  # Message is rate-limited, do not output

    # Map level string to MessageLevel enum if provided as string
    if level is None:
        msg_level = MessageLevel.INFO
    elif isinstance(level, str):
        level_map = {
            'debug': MessageLevel.DEBUG,
            'info': MessageLevel.INFO,
            'warning': MessageLevel.WARNING, 
            'error': MessageLevel.ERROR,
            'critical': MessageLevel.CRITICAL
        }
        msg_level = level_map.get(level.lower(), MessageLevel.INFO)
    else:
        msg_level = level
    
    # Create metadata
    metadata = {}
    if hasattr(main, 'in_gui'):
        metadata['in_gui'] = getattr(main, 'in_gui', False)
    
    # Publish the message to the bus
    message_bus.publish(
        content=message,
        timestamp=timestamp,
        level=msg_level,
        pattern_name=regex_pattern,
        metadata=metadata
    )

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, **kwargs):
        # Get the singleton config manager instead of having it passed
        self.config_manager = get_config_manager()
        
        # Initialize rate limiter
        self.rate_limiter = MessageRateLimiter(
            timeout=int(self.rate_limit_timeout or 300),
            max_duplicates=int(self.rate_limit_max_duplicates or 1)
        )
        
        # Initialize core attributes from config
        self.username = self.config_manager.get('username', 'Unknown')
        self.current_shard = None
        self.current_version = None
        self.script_version = get_version()
        self.log_file_path = self.config_manager.get('log_file_path')
        self.last_position = 0
        self.actor_state = {}
        
        # Flag to track if we're in a EA_ mode (to ignore exits)
        self.in_ea_mode = False
        
        # Initialize a single data queue instead of separate queues for Google Sheets and Supabase
        self.data_queue = queue.Queue()
        
        self.stop_event = threading.Event()
        self.screenshots_folder = os.path.join(os.path.dirname(self.log_file_path), "ScreenShots")
        self.current_mode = None
        self.version = get_version()
        
        # Initialize the data provider
        self.data_provider = get_data_provider(self.config_manager)
        
        # Create screenshots folder if it doesn't exist
        if not os.path.exists(self.screenshots_folder):
            os.makedirs(self.screenshots_folder)

        # Start data queue processor thread if not in process_once mode
        if not self.process_once:
            self.data_thread = threading.Thread(target=self.process_data_queue)
            self.data_thread.daemon = True
            self.data_thread.start()
        
        # Compile mode regex patterns
        self.mode_start_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <Context Establisher Done> establisher=\"(?P<establisher>.*?)\" runningTime=(?P<running_time>[\d\.]+) map=\"(?P<map>.*?)\" gamerules=\"(?P<gamerules>.*?)\" sessionId=\"(?P<session_id>[\w-]+)\" \[(?P<tags>.*?)\]")
        self.nickname_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <Channel Connection Complete> map=\"(?P<map>.*?)\" gamerules=\"(?P<gamerules>.*?)\" remoteAddr=(?P<remote_addr>.*?) localAddr=(?P<local_addr>.*?) connection=\{(?P<connection_major>\d+), (?P<connection_minor>\d+)\} session=(?P<session_id>[\w-]+) node_id=(?P<node_id>[\w-]+) nickname=\"(?P<nickname>.*?)\" playerGEID=(?P<player_geid>\d+) uptime_secs=(?P<uptime>[\d\.]+)")
        self.mode_end_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <Channel Disconnected> cause=(?P<cause>\d+) reason=\"(?P<reason>.*?)\" frame=(?P<frame>\d+) map=\"(?P<map>.*?)\" gamerules=\"(?P<gamerules>.*?)\" remoteAddr=(?P<remote_addr>[\d\.:\w]+) localAddr=(?P<local_addr>[\d\.:\w]+) connection=\{(?P<connection_major>\d+), (?P<connection_minor>\d+)\} session=(?P<session>[\w-]+) node_id=(?P<node_id>[\w-]+) nickname=\"(?P<nickname>.*?)\" playerGEID=(?P<player_geid>\d+) uptime_secs=(?P<uptime>[\d\.]+) \[(?P<tags>.*?)\]")
        # Add server endpoint regex to detect PU/PTU version
        self.server_endpoint_regex = re.compile(r"<(?P<timestamp>.*?)> \[Notice\] <ReuseChannel> Reusing channel for .* to endpoint dns:///(?P<server_version>[^\.]+)\..*? \(transport security: \d\)")

        # --- BLOQUEO DE GRABACIÓN POR LOBBY PRIVADO EN MODOS EA_* ---
        self.block_private_lobby_recording = False
        self.lobby_type_regex = re.compile(
            r"<(?P<timestamp>.*?)> \[Notice\] <\[EALobby\] NotifyServiceRequestResponse> "
            r"\[EALobby\]\[CEALobby::NotifyServiceRequestResponse\] Notifying Service Response\. "
            r"Response\[\d+\]\[.*?\] Network\[(?P<network>\w+)\]\[\d+\] "
            r"Mode\[GameMode\.(?P<mode>EA_\w+)\]\[\d+\] Map\[(?P<map>[\w_]+)\]\[\d+\]"
        )
        self.vip_patterns = self.compile_vip_patterns()  # Compile VIP patterns at initialization
        # Process entire log if requested
        if self.process_all:
            self.process_entire_log()
        else:
            # Move to the end of the file if we're not processing everything
            self.last_position = self._get_file_end_position()
            output_message(None, f"Skipping to the end of log file (position {self.last_position})")
        # Setup message bus listener for actor_profile events
        message_bus.on("actor_profile", self._on_actor_profile)
        message_bus.on("request_profile", self.async_profile_scraping)
        message_bus.on("force_broadcast_profile", self._on_force_broadcast_profile)

    def __getattr__(self, name):
        """
        Dynamically retrieve attributes from the config_manager when they're not found
        in the instance. This allows direct access to any configuration value without
        explicitly defining it in the class.
        
        Args:
            name (str): The attribute name to look for in the config_manager
            
        Returns:
            The value from the config_manager
            
        Raises:
            AttributeError: If the attribute doesn't exist in the config_manager either
        """
        try:
            # Try to get the property from the config_manager
            return self.config_manager.get(name)
        except Exception as e:
            # If that fails or if the property doesn't exist, raise AttributeError
            raise AttributeError(f"Neither LogFileHandler nor ConfigManager has an attribute named '{name}'") from e
    
    def _on_actor_profile(self, player_name, org, enlisted, metadata=None):
        """Handler for actor_profile events from message bus"""
        message_bus.publish(
            content=f"_on_actor_profile called for {player_name} with origin={metadata.get('origin') if metadata else 'None'}",
            level=MessageLevel.DEBUG,
            metadata={"source": "log_analyzer", "action": "actor_profile_handler"}
        )

        # Si es un perfil recibido por broadcast y es nuestro propio mensaje, ignorarlo
        if metadata and metadata.get('origin') == 'broadcast_received':
            event_username = metadata.get('username')
            if event_username == self.username:
                message_bus.publish(
                    content=f"Ignoring own broadcast for {player_name}",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "log_analyzer", "action": "ignore_own_broadcast"}
                )
                return

        from helpers.profile_cache import ProfileCache
        cache = ProfileCache.get_instance()

        # Si es un perfil recibido por broadcast y tiene raw_data, usarlo directamente
        if metadata and metadata.get('origin') == 'broadcast_received' and metadata.get('raw_data'):
            raw_data = metadata['raw_data'].copy()
            
            # Añadir metadatos mínimos necesarios
            profile_data = {
                'player_name': raw_data.get('player_name'),
                'org': raw_data.get('org'),
                'enlisted': raw_data.get('enlisted'),
                'source_type': 'automatic',
                'origin': 'broadcast_received',
                'requested_by': metadata.get('username'),
                'source_user': metadata.get('username'),
                'cache_time': datetime.now().isoformat(),
                **raw_data  # Incluir todos los campos del raw_data
            }
            
            # Almacenar en caché
            cache.store_profile(profile_data['player_name'], profile_data)
            
            # Mostrar en log solo (sin notificación para broadcast)
            message_bus.publish(
                content=f"Profile for {player_name} received from {metadata.get('username')}",
                level=MessageLevel.DEBUG,
                metadata={"source": "log_analyzer", "action": "profile_received"}
            )
            return

        # Determinar origen y tipo de la solicitud para perfiles normales
        action = metadata.get('action', '') if metadata else ''
        if action == 'get':
            origin = 'manual'
            source_type = 'manual'
        elif action in ['killer', 'victim']:
            origin = action
            source_type = 'automatic'
        else:
            origin = 'automatic'
            source_type = 'automatic'
        requested_by = self.username
        source_user = self.username
        
        # Create data dict to match pattern used by other event handlers
        data = {
            'player_name': player_name,
            'org': org,
            'enlisted': enlisted,            
        }
        
        # Add metadata if provided
        if metadata:
            data.update(metadata)
            data['all'] = ' '.join([f"{k}: {v}\n" for k, v in metadata.items() 
                                   if v is not None and 
                                        k not in ['source','timestamp','player_name', 'org', 'enlisted','action'] and 
                                        v not in ('None','Unknown','')])
        
        # Add state data to the data dict   
        data = self.add_state_data(data)
        
        # Almacenar en cache
        cache.add_profile(
            player_name=player_name,
            profile_data=data,
            source_type=source_type,
            origin=origin,
            requested_by=requested_by,
            source_user=source_user
        )
        
        # Emitir evento profile_cached para que el widget se actualice
        message_bus.emit("profile_cached", player_name, data)
        
        # Use standard pattern: check if format exists in messages and output
        output_message_format = self.messages.get("actor_profile")
        if output_message_format:
            output_message(None, output_message_format.format(**data), regex_pattern="actor_profile")
        
        # Si es broadcast recibido, solo mostrar en log_text y terminar
        if origin == 'broadcast_received':
            return
        
        # Para perfiles normales, continuar con Discord y lógica adicional
        self.send_discord_message(data, pattern_name="actor_profile")
        
        # Determinar si es solicitud manual vs automática
        action = metadata.get('action', '') if metadata else ''
        if action == 'get':
            # Profile request manual: notificar solo localmente
            if output_message_format:
                content = output_message_format.format(**data)
                message_bus.emit("show_windows_notification", content)
        else:
            # Profile automático (killer/victim): transmitir por realtime
            # Verificar si el perfil ya existía en cache antes de procesar
            existing_profile = cache.get_profile(player_name)
            
            if not existing_profile:
                # Es la primera vez que obtenemos este perfil -> broadcast
                self.send_realtime_event(data, pattern_name="actor_profile")
                message_bus.publish(
                    content=f"Broadcasting new profile for {player_name}",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "log_analyzer"}
                )
            else:
                # Ya teníamos el perfil en cache -> NO broadcast
                message_bus.publish(
                    content=f"Profile for {player_name} already in cache, skipping broadcast",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "log_analyzer"}
                )

    def add_state_data(self, data):
        """
        Add state data (current_mode, shard, username, version) as first-level keys to the given data.
        Only adds keys if they don't already exist in the data. Preserves the original order of the data dict.

        Args:
            data (dict): The data to which state information will be added.

        Returns:
            dict: The updated data with state information, maintaining original data order.
        """
        # Create a default state dict
        state_data = {
            "mode": self.current_mode or "None",
            "shard": self.current_shard or "Unknown",
            "username": self.username or "Unknown",
            "version": self.current_version or "Unknown",
            "script_version": self.script_version or "Unknown",
                        "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),            
        }
        
        # Create a new dict with state_data keys that don't exist in data
        result = data.copy()  # Start with a copy of the original data to preserve order
        
        # Only add state_data keys that don't already exist in the data
        for key, value in state_data.items():
            if key not in result:
                result[key] = value
        
        return result

    def stop(self):
        """Stop the handler and cleanup threads"""
        self.stop_event.set()
        output_message(None, "Stopping log analyzer...")
        self.cleanup_threads()
        output_message(None, "Log analyzer stopped successfully")

    def cleanup_threads(self):
        """Ensure all threads are stopped"""
        # Wait for data thread to finish processing remaining items
        if hasattr(self, 'data_thread') and self.data_thread.is_alive():
            output_message(None, "Waiting for data queue to complete...")
            self.data_queue.join()
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
            elif pattern_name and pattern_name in self.discord:
                # Get all possible player references from the data
                player_fields = ['player', 'owner', 'victim', 'killer', 'entity']
                players = [data.get(field) for field in player_fields if data.get(field)]
                
                # Add alert emoji if any player is in important_players
                if any(player in self.important_players for player in players):
                    data['alert'] = '🔊 Sound Alert!'
                else:
                    data['alert'] = ''  # Empty string for non-important players
                    
                content = self.discord[pattern_name].format(**data)
                
                # Determine the correct webhook URL based on the mode and message type
                if self.current_mode == "SC_Default" and self.live_discord_webhook:
                    url = self.live_discord_webhook
                elif self.current_mode != "SC_Default" and self.ac_discord_webhook:
                    url = self.ac_discord_webhook
                else:
                    url = self.discord_webhook_url  # Fallback to the default webhook
            else:
                return
            
            # Check if this message should be rate limited - using pattern_name as part of the key
            if not rate_limiter.should_send(f"{pattern_name}:{content}", 'discord'):
                output_message(None, f"Rate limited Discord message for pattern: {pattern_name}")
                return
                
            payload = {"content": content}
            response = requests.post(url, json=payload)
            if response.status_code not in [200, 204]:
                output_message(None, f"Failed to send Discord message. Status code: {response.status_code}")
        except Exception as e:
            output_message(None, f"Error sending Discord message: {e}")

    def process_data_queue(self):
        """Worker thread to process data queue"""
        # Define batch parameters
        max_batch_size = 20  # Maximum number of items to process in one batch
        max_wait_time = 0.5  # Maximum time to wait for a batch to fill (in seconds)
        
        while not self.stop_event.is_set():
            try:
                # Collect batch of items
                batch = []
                start_time = time.time()
                
                # Try to fill the batch up to max_batch_size or until max_wait_time is reached
                while len(batch) < max_batch_size and (time.time() - start_time) < max_wait_time:
                    try:
                        # Try to get an item with a short timeout
                        data,sheet_name = self.data_queue.get(timeout=0.1)
                        batch.append({'data': data, 'sheet': data.get('sheet',self.current_mode or 'None')})
                        
                        # If queue is empty, don't wait for more items
                        if self.data_queue.empty():
                            break
                    except queue.Empty:
                        # No items in queue, break if we have at least one item or wait longer
                        if len(batch) > 0:
                            break
                        # If batch is empty, wait longer
                        time.sleep(0.2)
                        
                # Process the collected batch if not empty
                if batch:
                    message_bus.publish(
                        content=f"Processing batch of {len(batch)} items", 
                        level=MessageLevel.DEBUG,
                        metadata={"source": "log_analyzer"}
                    )                  
                    # Process each event type batch
                    if self.data_provider.process_data(batch):
                        message_bus.publish(
                            content=f"Successfully processed batch of {len(batch)} items", 
                            level=MessageLevel.DEBUG,
                            metadata={"source": "log_analyzer"}
                        )
                    else:
                        message_bus.publish(
                            content=f"Failed to process batch of {len(batch)} items", 
                            level=MessageLevel.ERROR,
                            metadata={"source": "log_analyzer"}
                        )
                    
                    # Mark all items as done
                    for _ in range(len(batch)):
                        self.data_queue.task_done()
                
            except Exception as e:
                message_bus.publish(
                    content=f"Exception in data queue worker thread: {e}", 
                    level=MessageLevel.ERROR,
                    metadata={"source": "log_analyzer"}
                )
                logging.error(f"Exception in data queue worker thread: {str(e)}")
                logging.error(traceback.format_exc())
        
        message_bus.publish(
            content="Data queue worker thread stopped", 
            level=MessageLevel.INFO,
            metadata={"source": "log_analyzer"}
        )

    def update_data_queue(self, data, event_type):
        """
        Add data to the data queue, including state information.
        Skip sending data if version starts with 'ptu'.

        Args:
            data (dict): The data to send.
            event_type (str): The type of event triggering the update.
            
        Returns:
            bool: True if queued successfully, False if skipped due to PTU version or other error.
        """
        # Check if current version is PTU (case-insensitive check)
        if self.current_version and self.current_version.lower().startswith('ptu'):
            message_bus.publish(
                content=f"Skipping data processing for PTU version: {self.current_version}", 
                level=MessageLevel.DEBUG,
                metadata={"source": "log_analyzer"}
            )
            return False

        # Add state data to the payload and proceed as normal for non-PTU versions
        data_with_state = self.add_state_data(data)

        # --- BLOQUEO DE GRABACIÓN POR LOBBY PRIVADO EN MODOS EA_* ---
        if getattr(self, 'block_private_lobby_recording', False):
            return False

        self.data_queue.put((data_with_state, event_type))
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
            # Reset state when a new log file is detected
            output_message(None, f"New log file detected at {event.src_path}")
            self.reset_state()
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
                            message_bus.emit("shard_version_update", 
                                self.current_shard, 
                                self.current_version, 
                                self.username, 
                                self.current_mode
                            )
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
                self.reset_state()
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
                
                # Check if we're in GUI mode
                in_gui_mode = hasattr(main, 'in_gui') and main.in_gui
                
                # Process entries with periodic yielding if in GUI mode
                for i, entry in enumerate(entries):
                    self.parse_log_entry(entry, send_message=False)
                    
                    # Yield to the main thread every 10 entries if in GUI mode
                    if in_gui_mode and i % 4 == 0 and i > 0:
                        import wx
                        wx.YieldIfNeeded()
                        
                self.last_position = file.tell()
        except PermissionError:
            output_message(None, "Unable to read log file. Make sure it's not locked by another process.")
        except Exception as e:
            output_message(None, f"Error reading log file: {e}\n{traceback.format_exc()}")
            logging.error("An error occurred: %s", str(e))
            logging.error("Stack trace:\n%s", traceback.format_exc())

    def detect_vip(self, entry, send_message=True):
        """
        Detect if any VIP appears in the log line. Use the same pattern as detect_and_emit_generic.
        """
        for vip_regex in self.vip_patterns:
            match = vip_regex.search(entry)
            if match:
                data = match.groupdict()
                timestamp = data.get('timestamp',datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))           # Add state data to the detected data
                data = self.add_state_data(data)
                pattern_name = 'vip'
                output_message_format = self.messages.get(pattern_name, None)
                if output_message_format:
                    output_message(timestamp, output_message_format.format(**data), regex_pattern=pattern_name)
        
                if send_message:
                    self.send_discord_message(data, pattern_name=pattern_name)
                    self.send_realtime_event(data, pattern_name=pattern_name)

                return data['vip']
        return None

    def parse_log_entry(self, entry, send_message=True):
        # VIP detection FIRST, but do not block other detections
        self.detect_vip(entry, send_message=send_message)
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

    def compile_vip_patterns(self):
        """
        Compile regex patterns from important_players in config. Invalid patterns are ignored.
        """
        patterns = []
        vip_list = self.config_manager.get('important_players', [])
        for pattern in [ p.strip() for p in vip_list.split(",")]:
            try:
                patterns.append(re.compile(f"<(?P<timestamp>.*?)>.*?(?P<vip>{pattern}?).*?"))
            except Exception:
                pass  # Silently ignore invalid patterns
        return patterns  # Always assign a list, never None

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
                message_bus.emit("username_change", self.username, old_username)
                
                # Send startup Discord message after getting the username for the first time
                if old_username == 'Unknown' and not self.process_once:
                    self.send_discord_message(self.add_state_data({}),"startup")

                return True

        # --- BLOQUEO DE GRABACIÓN POR LOBBY PRIVADO EN MODOS EA_* ---
        lobby_match = self.lobby_type_regex.search(entry)
        if lobby_match:
            network = lobby_match.group('network')
            mode = lobby_match.group('mode')
            if mode.startswith('EA_'):
                if network == 'Custom':
                    self.block_private_lobby_recording = True
                elif network == 'Online':
                    self.block_private_lobby_recording = False

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
                # Si el nuevo modo es SC_Frontend, limpiar el shard
                if new_mode != "SC_Default":
                    self.current_shard = None
                
                # Check if we're entering an EA_ mode
                self.in_ea_mode = new_mode is not None and new_mode.startswith("EA_")
                
                # Log EA mode detection state
                if self.in_ea_mode:
                    output_message(timestamp, f"EA mode detected: '{new_mode}'. Exit events will be ignored until next mode change.", level="debug")

                # Si el nuevo modo es SC_*, desactivar siempre el bloqueo de grabación
                if new_mode and new_mode.startswith('SC_'):
                    self.block_private_lobby_recording = False
                
                # Emit the event to notify subscribers about mode change
                message_bus.emit("mode_change", new_mode, old_mode)

                # Format the mode data for output
                mode_data['status'] = 'entered'
                mode_data['old_mode'] = old_mode or 'None'
                mode_data=self.add_state_data(mode_data)  # Add state data to the mode data

                # Emit the event to notify subscribers
                message_bus.emit("shard_version_update", 
                    self.current_shard, 
                    self.current_version, 
                    self.username, 
                    self.current_mode,
                    self.block_private_lobby_recording
                )

                # Output message
                output_message(timestamp, f"Mode changed: '{old_mode or 'None'}' → '{new_mode}'",'mode_change')

                # Send to Discord if enabled
                if send_message and self.use_discord and 'mode_change' in self.discord:
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
                # Skip exit processing if we're in an EA_ mode that matches the current mode
                if self.in_ea_mode and self.current_mode and self.current_mode.startswith("EA_"):
                    output_message(timestamp, f"Ignoring exit event for EA mode: '{gamerules}'", level="debug")
                    return False
                
                # Emit the event to notify subscribers about mode exit
                message_bus.emit("mode_change", None, self.current_mode)

                # Format the mode data for output
                mode_data['status'] = 'exited'
                mode_data=self.add_state_data(mode_data)  # Add state data to the mode data
                # Emit the event to notify subscribers
                message_bus.emit("shard_version_update", 
                    self.current_shard, 
                    self.current_version, 
                    self.username, 
                    self.current_mode,
                    self.block_private_lobby_recording
                )

                # Output message
                output_message(timestamp, f"Exited mode: '{self.current_mode}'")

                # Reset current mode
                self.current_mode = None
                # Reset EA mode flag
                self.in_ea_mode = False

                # Send to Discord if enabled
                if send_message and self.use_discord and 'mode_change' in self.discord:
                    self.send_discord_message(mode_data, pattern_name='mode_change')

                return True
                
        # Check for server endpoint version (PU/PTU)
        endpoint_match = self.server_endpoint_regex.search(entry)
        if endpoint_match:
            endpoint_data = endpoint_match.groupdict()
            new_server_version = endpoint_data.get('server_version')
            timestamp = endpoint_data.get('timestamp')

            # If it's a different server version than the current one, update it
            if new_server_version != self.current_version:
                old_server_version = self.current_version
                self.current_version = new_server_version

                # Output message
                output_message(timestamp, f"Server version changed: '{old_server_version or 'None'}' → '{new_server_version}'", 'server_version_change')
                
                # Emit the event to notify subscribers about version update
                message_bus.emit("shard_version_update", 
                    self.current_shard, 
                    self.current_version, 
                    self.username, 
                    self.current_mode
                )

                # Format the server version data for output
                endpoint_data['old_server_version'] = old_server_version or 'None'
                endpoint_data = self.add_state_data(endpoint_data)  # Add state data to the server version data

                # Send to Discord if enabled
                if send_message and self.use_discord and 'server_version_change' in self.discord:
                    self.send_discord_message(endpoint_data, pattern_name='server_version_change')

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
            self.clean_trailing_ids(data)
            # Extract player and action information
            data['player'] = data.get('player') or data.get('owner') or data.get('entity') or 'Unknown'
            data['action'] = pattern_name.replace('_', ' ').title()
            timestamp = data.get('timestamp')
            data['username'] = self.username  # Use instance attribute
            
            # Clean IDs - remove trailing underscores followed by 4+ consecutive digits
            
            # Add state data to the detected data
            data = self.add_state_data(data)
    
            output_message_format = self.messages.get(pattern_name)
            if output_message_format:
                output_message(timestamp, output_message_format.format(**data), regex_pattern=pattern_name)
    
            if send_message:
                self.send_discord_message(data, pattern_name=pattern_name)            # Send to data queue
                if  pattern_name in self.google_sheets_mapping:
                    self.update_data_queue(data, pattern_name)
                self.send_realtime_event(data, pattern_name)            
                self.async_profile_scraping(data, pattern_name)
    
            return True, data
        return False, None

    def clean_trailing_ids(self, data):
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = re.sub(r'_\d{4,}$', '', value)

    def reset_state(self):
        """
        Reset all dynamic state variables to their initial values.
        This should be called when a log file change is detected.
        """
        output_message(None, "Resetting state variables to initial values")
        self.current_shard = None
        self.current_version = None
        self.current_mode = None
        last_username = self.username
        self.username = self.config_manager.get('username', 'Unknown')
        self.in_ea_mode = False
        self.last_position = 0
        self.actor_state = {}
        # Emit events to notify subscribers about the reset
        from helpers.message_bus import message_bus
        message_bus.emit("mode_change", None, self.current_mode)
        message_bus.emit("shard_version_update", self.current_shard, self.current_version, self.username, self.current_mode)
        message_bus.emit("username_change", self.username,  last_username)
        message_bus.emit("realtime_disconnect")
    

    def send_realtime_event(self, data, pattern_name):
        """
        Send a realtime event with rate limiting if the pattern is in the realtime list.
        
        Args:
            data (dict): The data to send in the event.
            pattern_name (str): The pattern name that triggered the event.
        
        Returns:
            bool: True if the event was sent, False if rate-limited or not a realtime pattern.
        """
        if not message_bus.is_debug_mode() and self.current_mode != "SC_Default":
            return False
        # Check if this pattern should be sent as realtime
        if pattern_name not in self.config_manager.get('realtime', []):
            return False
        # Get timestamp from data
        timestamp = data.get('timestamp')
        
        # Get output message format from configuration
        output_message_format = self.messages.get(pattern_name)
        
        # Create the content string
        content = output_message_format.format(**data) if output_message_format else f"{pattern_name}: {data.get('player', 'Unknown')}"

        # Check if this event should be rate limited
        if not rate_limiter.should_send(f"{pattern_name}:{content}", 'realtime'):
            message_bus.publish(
                content=f"Rate limited realtime event for pattern: {pattern_name}",
                level=MessageLevel.DEBUG,
                metadata={"source": "log_analyzer"}
            )
            return False
        
        # Create a message with all necessary information
        realtime_data = {
            'timestamp': timestamp,
            'type': pattern_name,
            'content': content,
            'raw_data': {k: str(v) if v is not None else '' for k, v in data.items()}
        }
        
        # Emit the event for RealtimeBridge to capture
        message_bus.emit(
            "realtime_event",
            realtime_data
        )
        
        message_bus.publish(
            content=f"Emitted realtime event for pattern: {pattern_name}",
            level=MessageLevel.DEBUG,
            metadata={"source": "log_analyzer"}
        )
        
        return True

    def async_profile_scraping(self, data, pattern_name):
        """
        Async profile scraping for actor_death events with cache support.
        
        Args:
            data (dict): The actor_death event data containing killer and victim.
                        Can include an 'action' field with "get", "killer", or "victim".
        """
        try:
            from helpers.profile_cache import ProfileCache
            
            # if self.current_mode != "SC_Default" and data.get('action') != 'get':
            if not message_bus.is_debug_mode() and (self.current_mode != "SC_Default" and data.get('action') != 'get'):
                return
            scraping_events = self.config_manager.get('scraping', ['player_death'])
            if not pattern_name in scraping_events and data.get('action') != 'get':
                return
            # Determinar si es patrón automático (en configuración scraping) o solicitud manual
            if pattern_name in scraping_events:
                # Extract killer and victim from the data
                killer = data.get('killer')
                victim = data.get('victim')
                
                if not killer or not victim:
                    message_bus.publish(
                        content="Actor death event missing killer or victim, skipping profile scraping",
                        level=MessageLevel.DEBUG,
                        metadata={"source": "log_analyzer"}
                    )
                    return
                
                # Determinar a quién hacer scraping (killer o victim, pero no username)
                username = self.username  # Use instance attribute
                target_player = None
                action = None
                
                if killer != username:
                    target_player = killer
                    action = "killer"
                elif victim != username:
                    target_player = victim
                    action = "victim"
                    
                # Añadir la acción determinada a los datos
                data['action'] = action
            else:
                # Solicitud manual (como "get"), usar player_name como target
                target_player = data.get('player_name')
                
            # Si hay target, hacer scraping asíncrono
            if target_player:
                cache = ProfileCache.get_instance()
                cached_profile = cache.get_profile(target_player)
                
                if cached_profile:
                    message_bus.publish(
                        content=f"Profile for {target_player} found in cache, serving from cache",
                        level=MessageLevel.DEBUG,
                        metadata={"source": "log_analyzer"}
                    )
                    
                    # Emitir evento con datos de cache
                    profile_data = cached_profile['profile_data']
                    message_bus.emit('actor_profile', 
                                    target_player, 
                                    profile_data.get('main_org_sid'), 
                                    profile_data.get('enlisted'), 
                                    profile_data)
                else:
                    scrape_profile_async(target_player, data)
                    message_bus.publish(
                        content=f"Started profile scraping for {target_player} with action={data.get('action')}",
                        level=MessageLevel.DEBUG,
                        metadata={"source": "log_analyzer"}
                    )
            
        except Exception as e:
            message_bus.publish(
                content=f"Error in async profile scraping: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "log_analyzer"}
            )

    def _on_force_broadcast_profile(self, player_name, profile_data):
        """Handler for force_broadcast_profile events from message bus"""
        # profile_data ya contiene todos los datos necesarios
        data = profile_data.copy()
        
        # Asegurar que tenemos los campos básicos
        data['player_name'] = player_name
        data['org'] = profile_data.get('main_org_sid', 'Unknown')
        data['enlisted'] = profile_data.get('enlisted', 'Unknown')
        
        # Marcar como broadcast forzado
        data['action'] = 'force_broadcast'
        
        # Add state data to the data dict   
        data = self.add_state_data(data)
        
        # SOLO HACER EL BROADCAST REAL - sin Discord ni log
        self.send_realtime_event(data, pattern_name="actor_profile")
        
        message_bus.publish(
            content=f"Force broadcast completed for profile {player_name}",
            level=MessageLevel.INFO,
            metadata={"source": "log_analyzer", "action": "force_broadcast"}
        )


def signal_handler(signum, frame):
    """Handle external signals to stop the application"""
    output_message(None, f"Received signal {signum}, shutting down...")
    if hasattr(signal_handler, 'event_handler') and signal_handler.event_handler:
        signal_handler.event_handler.stop()
    if hasattr(signal_handler, 'observer') and signal_handler.observer:
        signal_handler.observer.stop()

def stop_monitor(event_handler, observer):
    """
    Stop the observer and data thread cleanly.
    
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

def startup(process_all=False, use_discord=None, process_once=False, datasource=None, log_file_path=None, **kwargs):
    """
    Initialize the log analyzer infrastructure and allow the caller to pass event subscriptions via kwargs.

    Args:
        process_all: Whether to process the entire log file.
        use_discord: Whether to use Discord for notifications.
        process_once: Whether to process the log file once and exit.
        datasource: The data source to use ('googlesheets' or 'supabase').
        log_file_path: Path to the log file.
        kwargs: Additional arguments for event subscriptions or configurations.
    """
    try:
        app_path = get_application_path()
        
        # Log tool name and executable version
        tool_name = "SC Log Analyzer"
        version = get_version()
        output_message(None, f"Starting {tool_name} {version}")
        logging.info(f"{tool_name} {version} started")

        # Initialize the ConfigManager
        config_manager = get_config_manager()
        output_message(None, f"Loading config from: {config_manager.config_path}")
        
        # Override configuration with command-line parameters
        config_manager.override_with_parameters(
            process_all=process_all,
            use_discord=use_discord,
            process_once=process_once,
            datasource=datasource,
            log_file_path=log_file_path
        )
        
        # Log file path must exist
        if not os.path.exists(config_manager.get('log_file_path')):
            output_message(None, f"Log file not found at {config_manager.get('log_file_path')}")
            return

        # Create a global rate limiter for the application
        main.rate_limiter = MessageRateLimiter(
            timeout=int(config_manager.get('rate_limit_timeout', 300)),
            max_duplicates=int(config_manager.get('rate_limit_max_duplicates', 1))
        )

        # Create a file handler with kwargs for event subscriptions
        event_handler = LogFileHandler(**kwargs)

        if event_handler.process_once:
            output_message(None, "Processing log file once and exiting...")
            event_handler.process_entire_log()
            return event_handler

        # Log monitoring status just before starting the observer
        output_message(None, f"Monitoring log file: {config_manager.get('log_file_path')}")
        output_message(None, f"Sending updates to {'Discord webhook' if event_handler.use_discord else 'stdout'}")
        output_message(None, f"Data provider: {config_manager.get('datasource', 'googlesheets')}")

        # Create an observer
        observer = Observer()
        observer.schedule(event_handler, path=os.path.dirname(config_manager.get('log_file_path')), recursive=False)
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

def main(process_all=False, use_discord=None, process_once=False, datasource=None, log_file_path=None):
    try:
        event_handler, observer = startup(process_all, use_discord, process_once, datasource, log_file_path)

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
        print(f"Usage: {sys.argv[0]} [--process-all | -p] [--no-discord | -nd] [--process-once | -o] [--datasource <googlesheets|supabase>] [--debug | -d]")
        print("Options:")
        print("  --process-all, -p    Skip processing entire log file (overrides config)")
        print("  --no-discord, -nd    Do not send output to Discord webhook")
        print("  --process-once, -o   Process log file once and exit")
        print("  --datasource <googlesheets|supabase>    Specify the data source to use")
        print("  --debug, -d          Enable debug mode (e.g., save cropped images)")
        print(f"Version: {get_version()}")
        sys.exit(0)
    
    process_all = '--process-all' in sys.argv or '-p' in sys.argv
    use_discord = not ('--no-discord' in sys.argv or '-nd' in sys.argv)
    process_once = '--process-once' in sys.argv or '-o' in sys.argv
    datasource = None
    if '--datasource' in sys.argv:
        datasource_index = sys.argv.index('--datasource') + 1
        if datasource_index < len(sys.argv):
            datasource = sys.argv[datasource_index]
    debug_mode = '--debug' in sys.argv or '-d' in sys.argv
    # Set debug mode global en message_bus
    message_bus.set_debug_mode(debug_mode)
    # Show version info on startup
    print(f"SC Log Analyzer v{get_version()} starting...")
    main(process_all, use_discord, process_once, datasource)
