#!/usr/bin/env python
import wx
import os
import sys
import threading
import time
import webcolors
from watchdog.observers.polling import PollingObserver as Observer
import json
import winreg
import wx.grid
import requests
import log_analyzer

from .ui_components import TabCreator, DynamicLabels, safe_call_after
from .monitoring_service import MonitoringService
from .data_display_manager import DataDisplayManager
from .window_state_manager import WindowStateManager, is_app_in_startup
from .gui_module import ConfigDialog, ProcessDialog, TaskBarIcon, AboutDialog
from .message_bus import message_bus, MessageLevel
from .config_utils import get_config_manager
from .supabase_manager import supabase_manager
from helpers import updater
from version import get_version

# Define constants for repeated strings and values
CONFIG_FILE_NAME = "config.json"
REGISTRY_KEY_PATH = r"Software\SCLogAnalyzer\WindowInfo"
STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_APP_NAME = "SCLogAnalyzer"
STARTUP_COMMAND_FLAG = "--start-hidden"
DEFAULT_WINDOW_POSITION = (50, 50)
DEFAULT_WINDOW_SIZE = (800, 600)
LOG_FILE_WILDCARD = "Log files (*.log)|*.log|All files (*.*)|*.*"
TASKBAR_ICON_TOOLTIP = "SC Log Analyzer"

# Use constants from the updater module
from helpers.updater import UPDATER_EXECUTABLE, LEGACY_UPDATER


class LogAnalyzerFrame(wx.Frame):
    """Main application frame for SC Log Analyzer."""
    
    def __init__(self):
        """Initialize the main application frame."""
        super().__init__(None, title="SC Log Analyzer", size=(800, 600))
        
        # Set the application icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "SCLogAnalyzer.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
            
        # Initialize state properties
        self.username = "Unknown"
        self.shard = "Unknown"
        self.version = "Unknown"
        self.mode = "None"
        self.debug_mode = False  # Flag to track if debug mode is active
        
        # Define a consistent name for log message subscription
        self.log_subscription_name = "gui_main"
        
        # Initialize manager and service objects
        self.config_manager = get_config_manager(in_gui=True)
        self.tab_creator = TabCreator(self)
        self.monitoring_service = MonitoringService(self)
        self.data_manager = DataDisplayManager(self)
        self.window_manager = WindowStateManager(self)
        self.dynamic_labels = DynamicLabels(self)
        
        # Create main panel and UI components
        self._create_ui_components()
        
        # Set flag for GUI mode in log_analyzer
        log_analyzer.main.in_gui = True
        
        # Set up a custom log handler for GUI
        log_analyzer.main.gui_log_handler = self.append_log_message
        
        # Initialize message bus subscription
        message_bus.subscribe(self.log_subscription_name, self._append_log_message_from_bus)
        
        # Initialize variables for monitoring
        self.observer = None
        self.event_handler = None
        
        # Initialize configuration and settings
        self.initialize_config()
        self.config_manager.renew_config()
        
        # Set up stdout redirection

        # Create taskbar icon
        self.taskbar_icon = TaskBarIcon(self, TASKBAR_ICON_TOOLTIP)

        # Check if the app is started with the --start-hidden flag
        if STARTUP_COMMAND_FLAG in sys.argv:
            self.Hide()  # Hide the main window at startup
            
        # Check for updates at app initialization
        wx.CallAfter(self.check_for_updates)

        # Start monitoring by default when GUI is launched
        if self.log_file_path:
            wx.CallAfter(self.monitoring_service.start_monitoring, 1500)
        wx.CallAfter(self.monitoring_service.update_monitoring_buttons, True)

        # Restore window position, size, and state
        self.window_manager.restore_window_info()

        # Bind close event to handle cleanup
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        # Bind keyboard events for secret debug mode activation
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)  # Frame-level binding
        if hasattr(self, 'log_text'):
            self.log_text.Bind(wx.EVT_KEY_DOWN, self.on_key_down)  # Bind to log text control
        
        # Initialize dynamic labels
        wx.CallAfter(self.update_dynamic_labels)
        
        # Initially hide debug elements
        self.update_debug_ui_visibility()
    
    def _create_ui_components(self):
        """Create all UI components for the main application window."""
        # Create main panel
        panel = wx.Panel(self)
        
        # Bind keyboard events to panel as well
        panel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        # Create main vertical sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add dynamic labels for username, shard, version, and mode
        self.dynamic_labels.create_labels(panel, main_sizer)

        # Create notebook for log output and Google Sheets data
        self.notebook = wx.Notebook(panel)
        self.log_page = wx.Panel(self.notebook)
        self.notebook.AddPage(self.log_page, "Main Log")

        # Create a vertical sizer for the log page
        log_page_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add a horizontal sizer for buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Style buttons with icons and custom fonts
        # IMPORTANT: wx font style constants use UNDERSCORE, not DOT notation (wx.FONTSTYLE_NORMAL, not wx.FONTSTYLE_NORMAL)
        self.process_log_button = wx.Button(self.log_page, label=" Process Log")
        self.process_log_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN, wx.ART_BUTTON, (16, 16)))
        self.process_log_button.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        self.autoshard_button = wx.Button(self.log_page, label=" Auto Shard")
        self.autoshard_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_TIP, wx.ART_BUTTON, (16, 16)))
        self.autoshard_button.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.autoshard_button.Enable(False)  # Start in disabled state
        
        self.monitor_button = wx.Button(self.log_page, label=" Start Monitoring")
        self.monitor_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_EXECUTABLE_FILE, wx.ART_BUTTON, (16, 16)))
        self.monitor_button.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        # Add the data transfer button
        self.data_transfer_button = wx.Button(self.log_page, label=" Data Transfer")
        self.data_transfer_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_COPY, wx.ART_BUTTON, (16, 16)))
        self.data_transfer_button.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.data_transfer_button.Hide()  # Hidden by default (debug mode only)

        # Add the test button for data provider (hidden by default)
        self.test_data_provider_button = wx.Button(self.log_page, label=" Test Data Provider")
        self.test_data_provider_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_LIST_VIEW, wx.ART_BUTTON, (16, 16)))
        self.test_data_provider_button.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.test_data_provider_button.Hide()  # Hidden by default (debug mode only)

        # Add buttons to the horizontal button sizer
        button_sizer.Add(self.process_log_button, 0, wx.ALL, 2)
        button_sizer.Add(self.autoshard_button, 0, wx.ALL, 2)
        button_sizer.Add(self.monitor_button, 0, wx.ALL, 2)
        button_sizer.Add(self.data_transfer_button, 0, wx.ALL, 2)
        button_sizer.Add(self.test_data_provider_button, 0, wx.ALL, 2)

        # Add the button sizer to the log page sizer
        log_page_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 2)

        # Add the log text area with fixed-width font and rich text support
        self.log_text = wx.TextCtrl(
            self.log_page,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.TE_RICH2
        )
        fixed_font = wx.Font(
            10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
        )
        self.log_text.SetFont(fixed_font)
        self.log_text.SetForegroundColour(wx.Colour(0, 255, 0))  # Green text
        self.log_text.SetBackgroundColour(wx.Colour(0, 0, 0))  # Black background
        log_page_sizer.Add(self.log_text, 1, wx.EXPAND | wx.ALL, 2)

        # Set the sizer for the log page
        self.log_page.SetSizer(log_page_sizer)

        # Add notebook to the main sizer
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 2)

        # Set the sizer for the main panel
        panel.SetSizer(main_sizer)

        # Bind buttons
        self.process_log_button.Bind(wx.EVT_BUTTON, self.on_process_log)
        self.autoshard_button.Bind(wx.EVT_BUTTON, self.on_autoshard)
        self.monitor_button.Bind(wx.EVT_BUTTON, self.on_monitor)
        self.data_transfer_button.Bind(wx.EVT_BUTTON, self.on_data_transfer)
        self.test_data_provider_button.Bind(wx.EVT_BUTTON, self.on_test_data_provider)

        # Add menu items
        menu_bar = wx.MenuBar()
        config_menu = wx.Menu()
        self.discord_check = config_menu.AppendCheckItem(wx.ID_ANY, "Use Discord")
        self.googlesheet_check = config_menu.AppendCheckItem(wx.ID_ANY, "Use Google Sheets")
        self.supabase_check = config_menu.AppendCheckItem(wx.ID_ANY, "Use Supabase")
        config_menu.AppendSeparator()
        edit_config_item = config_menu.Append(wx.ID_ANY, "Edit Configuration")
        menu_bar.Append(config_menu, "Config")

        # Add Help menu with About item
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "About")
        menu_bar.Append(help_menu, "Help")
        self.SetMenuBar(menu_bar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_toggle_check, self.discord_check)
        self.Bind(wx.EVT_MENU, self.on_toggle_check, self.googlesheet_check)
        self.Bind(wx.EVT_MENU, self.on_toggle_check, self.supabase_check)
        self.Bind(wx.EVT_MENU, self.on_edit_config, edit_config_item)
        self.Bind(wx.EVT_MENU, self.on_about, about_item)

        # Status bar
        self.CreateStatusBar()
        self.SetStatusText("Ready")
    
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
            return self.config_manager.get(name)
        except Exception as e:
            # If that fails or if the property doesn't exist, raise AttributeError
            raise AttributeError(f"Neither {self.__class__.__name__} nor ConfigManager has an attribute named '{name}'") from e
    
    def check_for_updates(self):
        """Check for updates by querying the GitHub API."""
        current_version = get_version()
        updater.check_for_updates(self, current_version)
    
    def update_dynamic_labels(self):
        """Update the username, shard, version, and mode labels dynamically."""
        try:
            # Use instance properties if they're set, fall back to event_handler if needed
            username = self.username if self.username != "Unknown" and self.monitoring_service.event_handler else getattr(self.monitoring_service.event_handler, "username", "Unknown")
            shard = self.shard if self.shard != "Unknown" and self.monitoring_service.event_handler else getattr(self.monitoring_service.event_handler, "current_shard", "Unknown")
            version = self.version if self.version != "Unknown" and self.monitoring_service.event_handler else getattr(self.monitoring_service.event_handler, "current_version", "Unknown")
            mode = self.mode if self.mode != "None" and self.monitoring_service.event_handler else getattr(self.monitoring_service.event_handler, "current_mode", "None")

            self.dynamic_labels.update_labels(username, shard, version, mode)
        except Exception as e:
            message_bus.publish(
                content=f"Error updating labels: {e}",
                level=MessageLevel.ERROR
            )
    
    def on_shard_version_update(self, shard, version, username, mode=None):
        """
        Handle updates to the shard, version, username, and mode.

        Args:
            shard (str): The updated shard name.
            version (str): The updated version.
            username (str): The updated username.
            mode (str): The current game mode.
        """
        try:
            # Update instance properties
            self.shard = shard
            self.version = version
            self.username = username
            if mode is not None:
                self.mode = mode
                
            self.update_dynamic_labels()  # Call update_dynamic_labels to refresh UI
        except Exception as e:
            message_bus.publish(
                content=f"Error updating shard/version/username/mode: {e}",
                level=MessageLevel.ERROR
            )
    
    def on_mode_change(self, new_mode, old_mode):
        """
        Handle mode change events.

        Args:
            new_mode (str): The new mode entered.
            old_mode (str): The previous mode exited.
        """
        if new_mode == "SC_Default":
            self.autoshard_button.Enable(True)
        else:
            self.autoshard_button.Enable(False)
            
        # Update mode label when mode changes
        self.update_dynamic_labels()
    
    def on_username_change(self, username, old_username):
        """
        Handle username change events.

        Args:
            username (str): The new username.
            old_username (str): The previous username.
        """
        # Update the stored username
        self.username = username
        self.update_dynamic_labels()
        for tab_title, (grid, refresh_button) in self.tab_creator.tab_references.items():
            if refresh_button and refresh_button.grid == grid:
                # Update the grid's username if it matches the current tab
                safe_call_after(wx.CallLater, 500, self.data_manager.execute_refresh_event, refresh_button)
    
    def on_about(self, event):
        """Show the About dialog."""
        dialog = AboutDialog(self, update_callback=self.check_for_updates)
        dialog.ShowModal()
    
    def initialize_config(self):
        """Initialize configuration: load settings, ensure config exists with latest template, and validate."""
        try:
            # 1. Load configuration values from ConfigManager
            self.default_log_file_path = self.log_file_path
            self.discord_check.Check(self.use_discord or True)
            
            # Get the datasource and set UI accordingly
            datasource = self.datasource or 'googlesheets'
            self.googlesheet_check.Check(datasource == 'googlesheets')
            self.supabase_check.Check(datasource == 'supabase')
            
            # 3. Validate critical settings and prompt for missing ones
            missing_settings = []
            if not self.default_log_file_path:
                missing_settings.append("Log file path")
            elif not os.path.exists(self.default_log_file_path):
                missing_settings.append("Log file path does not exist")
                
            if datasource == 'googlesheets' and not self.google_sheets_webhook:
                missing_settings.append("Google Sheets webhook URL")
                
            if datasource == 'supabase' and (
                not self.supabase_url or 
                not self.supabase_key
            ):
                missing_settings.append("Supabase credentials")
                
            if not self.discord_webhook_url:
                self.discord_check.Check(False)  # Uncheck Discord usage
                
            if missing_settings:
                warning = ", ".join(missing_settings)
                message_bus.publish(
                    content=f"Missing or invalid settings: {warning}",
                    level=MessageLevel.WARNING
                )
                
                # Give the user time to see the message in the log
                wx.CallLater(1000, lambda: wx.MessageBox(
                    f"Please check your configuration. The following settings need attention:\n\n{warning}",
                    "Configuration Warning",
                    wx.OK | wx.ICON_WARNING
                ))
        except Exception as e:
            message_bus.publish(
                content=f"Error in initialize_config: {e}",
                level=MessageLevel.ERROR
            )
    
    def on_process_log(self, event):
        """Open the process log dialog."""
        dialog = ProcessDialog(self)
        dialog.ShowModal()
    
    def run_process_log(self, log_file):
        """Run log processing."""
        self.monitoring_service.run_process_log(log_file)
    
    def on_monitor(self, event):
        """Handle start/stop monitoring button click event."""
        if not self or not self.IsShown():
            return  # Prevent actions if the frame is destroyed
            
        if self.monitoring_service.is_monitoring():
            self.monitoring_service.stop_monitoring()
            self.monitoring_service.update_monitoring_buttons(started=False)
        else:
            self.monitoring_service.start_monitoring()
            self.monitoring_service.update_monitoring_buttons(started=True)
    
    def on_autoshard(self, event):
        """Handle Auto Shard button click."""
        try:
            self.send_keystrokes_to_sc()  # Call the method to send keystrokes
            message_bus.publish(
                content="Auto Shard keystrokes sent.",
                level=MessageLevel.INFO
            )
        except Exception as e:
            message_bus.publish(
                content=f"Error sending Auto Shard keystrokes: {e}",
                level=MessageLevel.ERROR
            )
    
    def send_keystrokes_to_sc(self):
        """Send predefined keystrokes to the Star Citizen window."""
        from .gui_module import WindowsHelper
        
        # Derive the ScreenShots folder from the log file path
        screenshots_folder = os.path.join(os.path.dirname(self.default_log_file_path), "ScreenShots")
        ck = self.console_key if self.console_key!='' else WindowsHelper.CONSOLE_KEY
        WindowsHelper.send_keystrokes_to_window(
            "Star Citizen",
            [
                ck , "r_DisplaySessionInfo 1", WindowsHelper.RETURN_KEY,
                ck, WindowsHelper.PRINT_SCREEN_KEY,
                ck, "r_DisplaySessionInfo 0", WindowsHelper.RETURN_KEY,
                ck
            ],
            screenshots_folder=screenshots_folder,
            class_name="CryENGINE",
            process_name="StarCitizen.exe"
        )
    
    def on_toggle_check(self, event):
        """Handle checkbox menu item toggle."""
        # Get the menu item directly from the event source
        menu_item = event.GetEventObject().FindItemById(event.GetId())
        
        if menu_item:
            # Toggle the check state
            new_state = not menu_item.IsChecked()
            menu_item.Check(new_state)
            
            # Update configuration based on which checkbox changed
            if menu_item == self.discord_check:
                self.config_manager.set('use_discord', new_state)
            elif menu_item == self.googlesheet_check:
                # Update datasource to googlesheets
                self.config_manager.set('datasource', 'googlesheets')
                # Ensure mutual exclusivity with supabase
                self.supabase_check.Check(False)
                message_bus.publish(
                    content="Switched to Google Sheets mode",
                    level=MessageLevel.INFO
                )
            elif menu_item == self.supabase_check:
                # Update datasource to supabase
                self.config_manager.set('datasource', 'supabase')
                # Ensure mutual exclusivity with Google Sheets
                self.googlesheet_check.Check(False)
                message_bus.publish(
                    content="Switched to Supabase mode",
                    level=MessageLevel.INFO
                )
                
            # Save configuration
            self.config_manager.save_config()
            
            # Update UI if monitoring is active
            if self.monitoring_service.is_monitoring():
                self.monitoring_service.stop_monitoring()
                self.monitoring_service.start_monitoring()
                
            # Update tabs based on data source change
            wx.CallAfter(self.data_manager.update_data_source_tabs)
    
    def on_edit_config(self, event):
        """Open the configuration dialog."""
        if not hasattr(self, 'config_dialog') or not self.config_dialog:
            self.config_dialog = ConfigDialog(self, self.config_manager)
            # Bind the close event to reload configuration
            self.config_dialog.Bind(wx.EVT_WINDOW_DESTROY, self.on_config_dialog_close)
        
        # Ensure the config dialog is within the main window's screen boundaries
        main_window_position = self.GetScreenPosition()
        main_window_size = self.GetSize()
        config_dialog_size = self.config_dialog.GetSize()

        # Get the display geometry for the screen containing the main window
        display_index = wx.Display.GetFromWindow(self)
        display_geometry = wx.Display(display_index).GetGeometry()

        # Calculate the new position within the display bounds
        new_x = max(display_geometry.GetLeft(), 
                    min(main_window_position.x + (main_window_size.x - config_dialog_size.x) // 2, 
                        display_geometry.GetRight() - config_dialog_size.x))
        new_y = max(display_geometry.GetTop(), 
                    min(main_window_position.y + (main_window_size.y - config_dialog_size.y) // 2, 
                        display_geometry.GetBottom() - config_dialog_size.y))
        
        self.config_dialog.SetPosition(wx.Point(new_x, new_y))
        
        # Show the dialog non-modally
        self.config_dialog.Show()
    
    def on_config_dialog_close(self, event):
        """Handle the configuration dialog's close event."""
        # Process the event first
        event.Skip()
        # Only reload configuration if changes were saved
        if self.config_dialog.config_saved:
            self.initialize_config()
            # If Supabase was enabled, try to connect and verify connection
            datasource = self.config_manager.get('datasource', 'googlesheets')
            if datasource == 'supabase':
                if not supabase_manager.is_connected():
                    connection_result = supabase_manager.connect()
                    if connection_result:
                        wx.MessageBox(
                            "Successfully connected to Supabase.",
                            "Connection Success",
                            wx.OK | wx.ICON_INFORMATION
                        )
                        message_bus.publish(
                            content="Connected to Supabase successfully after config change.",
                            level=MessageLevel.INFO
                        )
                    else:
                        wx.MessageBox(
                            "Failed to connect to Supabase. Check your credentials in config.\n"
                            "Falling back to Google Sheets mode.",
                            "Connection Failed",
                            wx.OK | wx.ICON_ERROR
                        )
                        # Fall back to Google Sheets
                        self.supabase_check.Check(False)
                        self.googlesheet_check.Check(True)
                        self.config_manager.set('datasource', 'googlesheets')
                        self.config_manager.save_config()
            
            # Restart monitoring if it was active
            if self.monitoring_service.is_monitoring():
                self.monitoring_service.stop_monitoring()
                self.monitoring_service.start_monitoring()
            
            # Update tabs based on the data source
            self.data_manager.update_data_source_tabs()
    
    def on_test_data_provider(self, event):
        """Handle the Test Data Provider button click."""
        self.data_manager.test_data_provider()
    
    def on_data_transfer(self, event):
        """Handle the Data Transfer button click."""
        message_bus.publish(
            content="Opening Data Transfer dialog...",
            level=MessageLevel.INFO
        )
        
        # Check if both Google Sheets and Supabase are configured
        google_sheets_webhook = self.config_manager.get('google_sheets_webhook', '')
        supabase_url = self.config_manager.get('supabase_url', '')
        supabase_key = self.config_manager.get('supabase_key', '')
        
        # Validate configurations
        missing_config = []
        
        if not google_sheets_webhook:
            missing_config.append("Google Sheets webhook URL")
            
        if not supabase_url or not supabase_key:
            missing_config.append("Supabase credentials")
        
        if missing_config:
            error_message = f"Missing configuration: {', '.join(missing_config)}.\nPlease update your configuration before transferring data."
            wx.MessageBox(error_message, "Configuration Error", wx.OK | wx.ICON_ERROR)
            message_bus.publish(
                content=error_message,
                level=MessageLevel.ERROR
            )
            return
        
        # Import here to avoid circular imports
        from .gui_module import DataTransferDialog
        
        # Create and show the dialog
        dialog = DataTransferDialog(self)
        dialog.ShowModal()
    
    def on_close(self, event):
        """Handle window close event."""
        # Use the window manager to clean up and save state
        self.window_manager.cleanup()
        
        # Stop monitoring if active
        if self.monitoring_service.is_monitoring():
            self.monitoring_service.stop_monitoring()
        
        # Restore original stdout
        sys.stdout = sys.__stdout__

        # Remove the custom log handler
        log_analyzer.main.gui_log_handler = None

        # Destroy the taskbar icon
        if hasattr(self, "taskbar_icon") and self.taskbar_icon:
            self.taskbar_icon.RemoveIcon()
            self.taskbar_icon.Destroy()
            self.taskbar_icon = None

        # Destroy the window
        self.Destroy()
    
    def append_log_message(self, message, regex_pattern=None):
        """
        Bridge method to maintain compatibility with older code.
        Redirects to the new message handling system.
        """
        if isinstance(message, str):
            # Publish the message to the bus
            message_bus.publish(
                content=message,
                level=MessageLevel.INFO,
                pattern_name=regex_pattern,
                metadata={'from_legacy': True}
            )
        else:
            # For the new Message objects from the message bus
            wx.CallAfter(self._append_log_message_from_bus, message)
    
    def _append_log_message_from_bus(self, message):
        """
        Process a message from the message bus and display it in the log text control.
        
        Args:
            message: The message object from the message bus
        """
        if self.log_text:
            # Default colors
            foreground_color = wx.Colour(255, 255, 255)  # White text
            background_color = wx.Colour(0, 0, 0)  # Black background

            # Load colors and patterns from the configuration
            colors = getattr(self, "colors", {})
            pattern_name = message.pattern_name
            
            if pattern_name:
                for color_spec, pattern_names in colors.items():
                    if pattern_name in pattern_names:
                        # Parse the color specification
                        color_parts = color_spec.split(",")
                        if len(color_parts) > 0:
                            try:
                                rgb = webcolors.name_to_rgb(color_parts[0].strip())
                                foreground_color = wx.Colour(rgb.red, rgb.green, rgb.blue)
                            except ValueError:
                                try:
                                    rgb = webcolors.hex_to_rgb(color_parts[0].strip())
                                    foreground_color = wx.Colour(rgb.red, rgb.green, rgb.blue)
                                except ValueError:
                                    pass  # Ignore invalid foreground color
                        if len(color_parts) > 1:
                            try:
                                rgb = webcolors.name_to_rgb(color_parts[1].strip())
                                background_color = wx.Colour(rgb.red, rgb.green, rgb.blue)
                            except ValueError:
                                try:
                                    rgb = webcolors.hex_to_rgb(color_parts[1].strip())
                                    background_color = wx.Colour(rgb.red, rgb.green, rgb.blue)
                                except ValueError:
                                    pass  # Ignore invalid background color
                        break

            # Apply the colors and append the message
            self.log_text.SetDefaultStyle(wx.TextAttr(foreground_color, background_color))
            self.log_text.AppendText(message.get_formatted_message() + "\n")
    
    def on_key_down(self, event):
        """Handle keyboard events for debug mode activation"""
        # Get the key code and modifier states
        key_code = event.GetKeyCode()
        ctrl_down = event.ControlDown()
        shift_down = event.ShiftDown()
        alt_down = event.AltDown()
        
        # Secret key combination: CTRL+SHIFT+ALT+D
        if ctrl_down and shift_down and alt_down and key_code == ord('D'):
            # Toggle debug mode
            self.debug_mode = not self.debug_mode
            self.update_debug_ui_visibility()
            
            # Show a subtle indication in the status bar
            if self.debug_mode:
                self.SetStatusText("Developer mode activated")
                message_bus.publish(
                    content="Developer tools activated",
                    level=MessageLevel.INFO
                )
            else:
                self.SetStatusText("Ready")
                message_bus.publish(
                    content="Developer tools deactivated",
                    level=MessageLevel.INFO
                )
        
        # Process the event normally
        event.Skip()
        
    def update_debug_ui_visibility(self):
        """Update UI elements based on debug mode state"""
        if hasattr(self, 'test_data_provider_button'):
            self.test_data_provider_button.Show(self.debug_mode)
        if hasattr(self, 'data_transfer_button'):
            self.data_transfer_button.Show(self.debug_mode)
            
        # Update log level filtering based on debug mode
        if hasattr(self, 'data_manager'):
            self.data_manager.set_debug_mode(self.debug_mode)
            
        # Force layout update
        if hasattr(self, 'log_page') and self.log_page:
            self.log_page.Layout()
            
        # Update GUI refresh
        if hasattr(self, 'GetMenuBar') and self.GetMenuBar():
            self.GetMenuBar().Refresh()
        self.Refresh()
    
    def async_init_tabs(self):
        """Initialize tabs asynchronously after the main window is loaded."""
        self.data_manager.async_init_tabs()


def main():
    """Main entry point for the application."""
    # Check if running as script or executable
    is_script = getattr(sys, 'frozen', False) == False
    
    if os.path.basename(sys.argv[0]) in (UPDATER_EXECUTABLE,LEGACY_UPDATER):
        updater.update_application()    
    else:
        updater.cleanup_updater_script()
    
    # Initialize debug mode based on script detection
    if is_script:
        # If running as script, log startup information with debug enabled
        print("Running as script - debug mode enabled")
        # Configure message bus with debug as default minimum level
        message_bus.publish(
            content="Application started in script mode with DEBUG level enabled",
            level=MessageLevel.DEBUG
        )
    
    app = wx.App()
    frame = LogAnalyzerFrame()
    
    # Set debug mode if running as script but don't update visibility yet
    # The frame initialization will handle the update_debug_ui_visibility call
    if is_script:
        frame.debug_mode = True
        frame.update_debug_ui_visibility()
    
    frame.Show()
    frame.async_init_tabs()  # Initialize tabs asynchronously
    app.MainLoop()

if __name__ == "__main__":
    main()