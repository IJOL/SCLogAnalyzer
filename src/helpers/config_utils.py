import os
import sys
import json
import requests  # Added for fetch_dynamic_config
import threading
import re  # Added for URL validation
from .message_bus import message_bus, MessageLevel  # Import the message bus

DEFAULT_CONFIG_TEMPLATE = "config.json.template"

# Global singleton instance
_config_manager_instance = None
_config_manager_lock = threading.Lock()

def get_config_manager(in_gui=False):
    """
    Get or create the singleton ConfigManager instance.
    
    Args:
        in_gui (bool): Whether the application is running in GUI mode
    
    Returns:
        ConfigManager: The singleton instance of ConfigManager
    """
    global _config_manager_instance
    
    with _config_manager_lock:
        if _config_manager_instance is None:
            _config_manager_instance = ConfigManager(in_gui=in_gui)
        elif in_gui:
            # If we're in GUI mode but the instance wasn't created with in_gui=True,
            # update the flag on the existing instance
            _config_manager_instance.in_gui = True
        return _config_manager_instance

def prompt_for_config_values(template):
    """Prompt the user for configuration values based on a template."""
    config = template.copy()
    for key, value in template.items():
        if isinstance(value, str) and value.startswith("{?") and value.endswith("}"):
            label = value[2:-1]
            user_input = input(f"Please enter a value for {label}: ")
            config[key] = user_input
        elif isinstance(value, dict):
            config[key] = prompt_for_config_values(value)
    return config

def emit_default_config(config_path, in_gui=False, template_path=None):
    """Emit a default configuration file if it doesn't exist."""
    template_file_path = template_path or get_template_path()
    with open(template_file_path, 'r', encoding='utf-8') as template_file:
        template_config = json.load(template_file)
    if not in_gui:
        config = prompt_for_config_values(template_config)
    else:
        template_config["discord_webhook_url"] = ""
        template_config["google_sheets_webhook"] = ""
        config = template_config
    config.pop("username", None)  # Remove username from the default config
    if os.path.exists(os.path.join(get_application_path(), "Game.log")):
        config['log_file_path'] = os.path.join(get_application_path(), "Game.log")
    
    # Create the configuration file
    with open(config_path, 'w', encoding='utf-8') as config_file:
        json.dump(config, config_file, indent=4)
    
    # Use message bus instead of direct print
    message_bus.publish(
        content=f"Default config emitted at {config_path}",
        level=MessageLevel.INFO
    )

def get_template_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    elif '__compiled__' in globals():
        return os.path.dirname(__file__)
    else:
        return get_application_path()

def get_template_path():
    return os.path.join(get_template_base_dir(), DEFAULT_CONFIG_TEMPLATE)


def get_application_path():
    """Determine the correct application path whether running as .py or .exe."""
    # Fall back to other methods if not a Nuitka build
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle (exe) through PyInstaller
        return os.path.dirname(sys.executable)
    elif '__compiled__' in globals():
        # If the application is run as a compiled script (e.g. Nuitka)
        return os.path.dirname(__file__)
    else:
        # If the application is run as a Python script
        # Get the directory of the script that was used to invoke the Python interpreter
        return os.path.dirname(os.path.abspath(sys.argv[0]))

def fetch_dynamic_config(config_manager=None):
    """
    Fetch dynamic configuration from a data provider (Google Sheets or Supabase).
    
    Args:
        config_manager (ConfigManager, optional): The config manager instance for getting data provider.
        
    Returns:
        dict: A dictionary containing configuration values fetched from the data provider.
    """
    # If config_manager is provided, try to use the configured data provider
    if config_manager:
        try:
            from .data_provider import get_data_provider
            data_provider = get_data_provider(config_manager)
            if data_provider.is_connected():
                # Fetch configuration from the connected data provider
                return data_provider.fetch_config()
        except (ImportError, Exception) as e:
            message_bus.publish(
                content=f"Error using data provider for config: {e}",
                level=MessageLevel.ERROR
            )
            return {}
    
    # If no config_manager or data provider failed, return empty dict
    return {}

class ConfigManager:
    """
    A class to manage configuration settings with support for nested keys and dynamic updates.
    """
    def __init__(self, config_path=None, in_gui=False):
        """Initialize the ConfigManager with a configuration file path."""
        self.config_path = config_path or os.path.join(get_application_path(), "config.json")
        self.app_path = get_application_path()
        self._config = {}
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self.in_gui = in_gui  # Track whether we're running in GUI mode
        self.new_config = True  # Flag to indicate if a new config was created
        
        # No need to create an Event instance - using MessageBus event system instead
        
        self.load_config()
        # Setup data providers automatically after loading the config
        self.setup_data_providers()

    def load_config(self):
        """Load configuration from file. Creates default config if it doesn't exist."""
        with self._lock:
            # First try to load from the local file
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as config_file:
                        self._config = json.load(config_file)
                        self.new_config = False
                except Exception as e:
                    message_bus.publish(
                        content=f"Error loading configuration: {e}",
                        level=MessageLevel.ERROR
                    )
                    # Create default config if the file exists but couldn't be loaded
                    self._create_default_config()
            else:
                # Create default config if the file doesn't exist
                self._create_default_config()
    
    def _create_default_config(self):
        """Create a default configuration file and load it."""
        try:
            # Pass the GUI mode flag to emit_default_config
            emit_default_config(self.config_path, in_gui=self.in_gui)
            with open(self.config_path, 'r', encoding='utf-8') as config_file:
                self._config = json.load(config_file)
            message_bus.publish(
                content=f"Created default configuration at {self.config_path}",
                level=MessageLevel.INFO
            )
        except Exception as e:
            message_bus.publish(
                content=f"Error creating default configuration: {e}",
                level=MessageLevel.ERROR
            )
            self._config = {}  # Set empty config as fallback
        self.new_config = True
    
    def renew_config(self, preserve_keys=None):
        """
        Renew the configuration using the template while preserving specific values.
        
        Args:
            preserve_keys (list, optional): List of keys to preserve from the current config.
                                         If None, uses default keys to preserve.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.new_config:
            with self._lock:
                try:
                    # Import here to avoid circular import issues
                    from version import get_version
                    current_version = get_version()
                    
                    # Default keys to preserve if none specified
                    preserve_keys = preserve_keys or ["discord_webhook_url", "google_sheets_webhook", 
                                                     "log_file_path", "console_key", "version",
                                                     "supabase_key","datasource", "live_discord_webhook",
                                                     "ac_discord_webhook"]
                    
                    # Check if the config has already been renewed for this version
                    config_renew_version = self.get("version")
                    if config_renew_version == current_version:
                        return True
                    
                    template_path = get_template_path()
                    if not os.path.exists(template_path):
                        message_bus.publish(
                            content="Template file not found. Skipping config renewal.",
                            level=MessageLevel.WARNING
                        )
                        return False
                    
                    # Load the template
                    with open(template_path, 'r', encoding='utf-8') as template_file:
                        template_data = json.load(template_file)
                    
                    # Store values from the current config that need to be preserved
                    preserved_values = {}
                    for key in preserve_keys:
                        value = self.get(key)
                        if value is not None:  # Only preserve if the key exists in current config
                            preserved_values[key] = value
                    
                    # Update the configuration with the template
                    self._config = template_data
                    
                    # Restore preserved values using the set method
                    for key, value in preserved_values.items():
                        self.set(key, value)
                    
                    # Save the current version as the renewal version
                    self.set("version", current_version)
                    
                    # Save the renewed config
                    self.apply_dynamic_config()
                    self.save_config()
                    message_bus.publish(
                        content=f"Configuration renewed successfully for version {current_version}.",
                        level=MessageLevel.INFO
                    )
                    return True
                except Exception as e:
                    message_bus.publish(
                        content=f"Error renewing configuration: {e}",
                        level=MessageLevel.ERROR
                    )
                    return False
    
    def save_config(self):
        """Save the current configuration to file, handling lock contention by deferring to a background thread if needed."""
        # Use a short timeout to try to acquire the lock
        config_items_to_filter = ['use_discord', 'use_googlesheet', 
                                  'process_once', 'process_all',]
        acquired = self._lock.acquire(timeout=0.1)
        if acquired:
            try:
                
                filtered_config = self.filter(config_items_to_filter)
                with open(self.config_path, 'w', encoding='utf-8') as config_file:
                    json.dump(filtered_config, config_file, indent=4)
            except Exception as e:
                message_bus.publish(
                    content=f"Error saving configuration: {e}",
                    level=MessageLevel.ERROR
                )
            finally:
                self._lock.release()
            # Reset pending save flag if it was set
            if hasattr(self, '_pending_save_thread'):
                self._pending_save_thread = False
        else:
            # If already waiting, do not spawn another thread
            if getattr(self, '_pending_save_thread', False):
                return
            self._pending_save_thread = True
            def wait_and_save():
                with self._lock:
                    try:
                        filtered_config = self.filter(config_items_to_filter)
                        with open(self.config_path, 'w', encoding='utf-8') as config_file:
                            json.dump(filtered_config, config_file, indent=4)
                    except Exception as e:
                        message_bus.publish(
                            content=f"Error saving configuration (async): {e}",
                            level=MessageLevel.ERROR
                        )
                    finally:
                        self._pending_save_thread = False
            t = threading.Thread(target=wait_and_save, daemon=True)
            t.start()

    def filter(self, key_paths):
        """
        Filter the configuration dictionary based on provided key paths.
        
        Args:
            key_paths (list): List of key paths to filter from the config.
            
        Returns:
            dict: A new dictionary without the key_paths.
        """
        with self._lock:
            filtered_config = {}
            for key in self._config:
                if key not in key_paths:
                    filtered_config[key] = self._config[key]
            return filtered_config

    def get(self, key_path, default=None):
        """
        Get a configuration value using dot notation for nested keys.
        
        Args:
            key_path (str): The key path in dot notation (e.g., 'regex_patterns.player_death')
            default: The default value to return if the key doesn't exist
            
        Returns:
            The configuration value or the default value if not found
        """
        with self._lock:
            if '.' not in key_path:
                return self._config.get(key_path, default)
            
            keys = key_path.split('.')
            value = self._config
            for key in keys:
                if not isinstance(value, dict) or key not in value:
                    return default
                value = value[key]
            return value
    
    def set(self, key_path, value):
        """
        Set a configuration value using dot notation for nested keys.
        
        Args:
            key_path (str): The key path in dot notation (e.g., 'regex_patterns.player_death')
            value: The value to set
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                if '.' not in key_path:
                    self._config[key_path] = value
                else:
                    keys = key_path.split('.')
                    config = self._config
                    for key in keys[:-1]:
                        if key not in config:
                            config[key] = {}
                        elif not isinstance(config[key], dict):
                            config[key] = {}
                        config = config[key]
                    config[keys[-1]] = value
                return True
            except Exception as e:
                message_bus.publish(
                    content=f"Error setting configuration value: {e}",
                    level=MessageLevel.ERROR
                )
                return False
    
    def apply_dynamic_config(self):
        """
        Apply dynamic configuration from the configured data provider.
        
        This method loads dynamic configuration from whatever data provider is currently
        configured (Google Sheets, Supabase, etc.) and applies it directly to the current configuration.
        
        Returns:
            bool: True if successfully applied, False otherwise
        """
        with self._lock:
            try:
                # Store original datasource for change detection
                original_datasource = self.get('datasource', 'googlesheets')
                
                # Fetch dynamic config using the configured data provider
                dynamic_config = fetch_dynamic_config(self)
                
                if not dynamic_config:
                    message_bus.publish(
                        content="No dynamic configuration found or data provider not available",
                        level=MessageLevel.WARNING,
                        metadata={"source": "config_manager"}
                    )
                    return False
                
                # Apply each configuration value
                for key, value in dynamic_config.items():
                    self.set(key, value)
                
                message_bus.publish(
                    content=f"Successfully applied {len(dynamic_config)} dynamic configuration values",
                    level=MessageLevel.INFO,
                    metadata={"source": "config_manager"}
                )
                
                # Explicitly check if datasource changed and handle the change
                new_datasource = self.get('datasource', 'googlesheets')
                if original_datasource != new_datasource:
                    message_bus.publish(
                        content=f"Datasource changed from '{original_datasource}' to '{new_datasource}'",
                        level=MessageLevel.INFO,
                        metadata={"source": "config_manager"}
                    )
                    message_bus.emit("datasource_changed", original_datasource, new_datasource)
                
                return True
            except Exception as e:
                message_bus.publish(
                    content=f"Error applying dynamic configuration: {e}",
                    level=MessageLevel.ERROR,
                    metadata={"source": "config_manager"}
                )
                return False
                
    def setup_data_providers(self):
        """
        Configure data providers based on the datasource configuration.
        Connects to Supabase if that's the selected datasource and falls back to Google Sheets if connection fails.
        
        Returns:
            bool: True if at least one data provider is successfully set up
        """
        with self._lock:
            # Get the selected data source (default to "googlesheets")
            datasource = self.get('datasource', 'googlesheets')
            
            # Connect to Supabase if it's the selected datasource
            if datasource == 'supabase':
                from .supabase_manager import supabase_manager
                # Pass the config_manager instance to the connect method
                if supabase_manager.connect(config_manager=self):
                    message_bus.publish(
                        content="Successfully connected to Supabase",
                        level=MessageLevel.INFO,
                        metadata={"source": "config_manager"}
                    )
                else:
                    message_bus.publish(
                        content="Failed to connect to Supabase. Falling back to Google Sheets.",
                        level=MessageLevel.WARNING,
                        metadata={"source": "config_manager"}
                    )
                    # Fall back to Google Sheets if Supabase connection fails
                    self.set('datasource', 'googlesheets')
                    # Save the changed configuration to disk
                    
            if self.apply_dynamic_config():
                self.save_config()
                return True
            
            return datasource in ['googlesheets', 'supabase']

    def get_all(self):
        """Get a copy of the entire configuration dictionary."""
        with self._lock:
            filtered_config = self.filter(['use_discord', 'use_googlesheet', 
                                           'process_once', 'process_all',
                                           'version'])
            return filtered_config
    
    def update(self, new_config):
        """Update the configuration with a new dictionary."""
        with self._lock:
            self._config.update(new_config)
    
    def override_with_parameters(self, **kwargs):
        """
        Override config values with provided parameters, modifying the internal config directly.
        
        Args:
            **kwargs: Variable keyword arguments to override config values.
                     Common parameters include:
                     - process_all: Whether to process the entire log file
                     - use_discord: Whether to use Discord for notifications
                     - process_once: Whether to process the log file once and exit
                     - datasource: Data source to use ('googlesheets' or 'supabase')
                     - log_file_path: Path to the log file
            
        Returns:
            dict: Reference to the internal configuration dictionary after modifications
        """
        with self._lock:
            # Handle log file path
            if kwargs.get('log_file_path'):
                self._config['log_file_path'] = kwargs['log_file_path']
            elif 'log_file_path' in self._config and not os.path.isabs(self._config['log_file_path']):
                self._config['log_file_path'] = os.path.join(self.app_path, self._config['log_file_path'])
            
            # Handle special boolean flags with consistent logic
            special_params = {
                # key: (kwargs_key, config_default, special_handling_function)
                'use_discord': ('use_discord', True, 
                               lambda: self.is_valid_url(self._config.get('discord_webhook_url', ''))),
                'process_once': ('process_once', False,
                               lambda: bool(self._config.get('process_once', False)))
            }
            
            for config_key, (kwargs_key, default, validate_fn) in special_params.items():
                if kwargs_key in kwargs:
                    self._config[config_key] = kwargs[kwargs_key]
                elif not bool(self._config.get(config_key, default)):
                    self._config[config_key] = False
                else:
                    self._config[config_key] = validate_fn()
            
            # Handle datasource parameter
            if 'datasource' in kwargs:
                self._config['datasource'] = kwargs['datasource']
            elif not self._config.get('datasource'):
                # Default to googlesheets if not specified
                self._config['datasource'] = 'googlesheets'
                
            # Ensure datasource is valid
            if self._config['datasource'] not in ['googlesheets', 'supabase']:
                self._config['datasource'] = 'googlesheets'
                message_bus.publish(
                    content="Invalid datasource specified, using 'googlesheets'",
                    level=MessageLevel.WARNING
                )
            
            # Handle process_all with its special reversed logic
            if 'process_all' in kwargs:
                # -p flag (False) means don't process all (force incremental)
                self._config['process_all'] = not(not kwargs['process_all'])
            else:
                self._config['process_all'] = bool(self._config.get('process_all', True))
            
            # Apply all other parameters directly
            for key, value in kwargs.items():
                if key not in ['process_all', 'use_discord', 'process_once', 'datasource', 'log_file_path']:
                    self._config[key] = value
            
            return self._config

    def is_valid_url(self, url):
        """Validate if the given string is a correctly formatted URL"""
        if not url:
            return False
            
        regex = re.compile(
            r'^(?:http|ftp)s?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
            r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return re.match(regex, url) is not None

    def __getattr__(self, name):
        """
        Transparently retrieve configuration values as attributes.
        
        This allows accessing config values directly as properties, e.g.:
        config_manager.log_file_path instead of config_manager.get('log_file_path')
        
        Args:
            name (str): The name of the attribute/config key to retrieve
            
        Returns:
            The configuration value or raises AttributeError if not found
        """
        with self._lock:
            # Simply check if the attribute exists in the _config dictionary
            return self._config.get(name)
