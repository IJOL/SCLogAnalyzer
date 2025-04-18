#!/usr/bin/env python
import wx
import os
import sys
import threading
import log_analyzer
import time
from watchdog.observers.polling import PollingObserver as Observer
import wx.adv  # Import wx.adv for taskbar icon support
import json  # For handling JSON files
import winreg  # Import for Windows registry manipulation
import wx.grid  # Import wx.grid for displaying tabular data
import requests  # For HTTP requests
from config_utils import get_config_manager, get_application_path  # Import the singleton getter
from gui_module import RedirectText, KeyValueGrid, ConfigDialog, ProcessDialog, WindowsHelper, NumericValidator, TaskBarIcon  # Import TaskBarIcon
from PIL import Image
import mss
from pyzbar.pyzbar import decode
import shutil  # For file operations
import tempfile  # For temporary directories
import subprocess
import webcolors  # Import the webcolors library

# Import the updater module for update functionality
import updater

from version import get_version  # For restarting the app

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
from updater import GITHUB_API_URL, APP_EXECUTABLE, UPDATER_EXECUTABLE,LEGACY_UPDATER

def safe_call_after(func, *args, **kwargs):
    """Safely call wx.CallAfter, ensuring wx.App is initialized."""
    if wx.GetApp() is not None:
        wx.CallAfter(func, *args, **kwargs)
    else:
        print(f"wx.App is not initialized. Cannot call {func.__name__}.")

class LogAnalyzerFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="SC Log Analyzer", size=(800, 600))
        # Set the application icon
        icon_path = os.path.join(os.path.dirname(__file__), "SCLogAnalyzer.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
            
        # Initialize state properties
        self.username = "Unknown"
        self.shard = "Unknown"
        self.version = "Unknown"
        self.mode = "None"
        self.debug_mode = False  # Flag to track if debug mode is active
            
# Initialize tab dictionary to store references to created tabs and grids
        self.tab_references = {}
            
        # Create main panel and UI components first
        self._create_ui_components()
        
        # Now set up configuration
        # Store config manager reference for dynamic attribute access
        self.config_manager = get_config_manager(in_gui=True)
        if self.google_sheets_webhook:
            self.config_manager.apply_dynamic_config(self.google_sheets_webhook)
       
        # Set flag for GUI mode
        log_analyzer.main.in_gui = True  # Ensure GUI mode is enabled
        
        # Set up a custom log handler for GUI (do this after log_text is created)
        log_analyzer.main.gui_log_handler = self.append_log_message
        
        # Initialize variables
        self.observer = None
        self.event_handler = None
        self.monitoring = False
        self.console_key = ""  # Default console key
        
        # Initialize configuration and create sheets tabs (only once)
        self.initialize_config()
        self.config_manager.renew_config()
        # Tab creation is now handled asynchronously in main() via async_init_tabs()

        # Set up stdout redirection
        sys.stdout = RedirectText(self.log_text)

        # Create taskbar icon
        self.taskbar_icon = TaskBarIcon(self, TASKBAR_ICON_TOOLTIP)

        # Check if the app is started with the --start-hidden flag
        if STARTUP_COMMAND_FLAG in sys.argv:
            self.Hide()  # Hide the main window at startup
        # Check for updates at app initialization
        wx.CallAfter(self.check_for_updates)

        # Start monitoring by default when GUI is launched
        wx.CallAfter(self.start_monitoring, 1500 )
        wx.CallAfter(self.update_monitoring_buttons, True)


        self.save_timer = wx.Timer(self)  # Timer to delay saving window info
        self.Bind(wx.EVT_TIMER, self.on_save_timer, self.save_timer)
        self.Bind(wx.EVT_MOVE, self.on_window_move_or_resize)
        self.Bind(wx.EVT_SIZE, self.on_window_move_or_resize)

        self.restore_window_info()  # Restore window position, size, and state from the registry

        # Bind close event to save window position
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        # Bind keyboard events for secret debug mode activation
        # Bind to components that can receive focus
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)  # Frame-level binding
        if hasattr(self, 'log_text'):
            self.log_text.Bind(wx.EVT_KEY_DOWN, self.on_key_down)  # Bind to log text control
        
        wx.CallAfter(self.update_dynamic_labels)
        
        # Initially hide debug elements
        self.update_debug_ui_visibility()
        
    def _create_ui_components(self):
        """Create all UI components first to ensure they exist before configuration is handled."""
        # Create main panel
        panel = wx.Panel(self)
        
        # Bind keyboard events to panel as well
        panel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        # Create main vertical sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add dynamic labels for username, shard, version, and mode
        bold_font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.username_label = wx.StaticText(panel, label="Username: Loading...")
        self.username_label.SetFont(bold_font)
        self.shard_label = wx.StaticText(panel, label="Shard: Loading...")
        self.shard_label.SetFont(bold_font)
        self.version_label = wx.StaticText(panel, label="Version: Loading...")
        self.version_label.SetFont(bold_font)
        self.mode_label = wx.StaticText(panel, label="Mode: Loading...")
        self.mode_label.SetFont(bold_font)
        label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        label_sizer.Add(self.username_label, 1, wx.ALL | wx.EXPAND, 5)
        label_sizer.Add(self.shard_label, 1, wx.ALL | wx.EXPAND, 5)
        label_sizer.Add(self.version_label, 1, wx.ALL | wx.EXPAND, 5)
        label_sizer.Add(self.mode_label, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(label_sizer, 0, wx.EXPAND)

        # Create notebook for log output and Google Sheets data
        self.notebook = wx.Notebook(panel)
        self.log_page = wx.Panel(self.notebook)
        self.notebook.AddPage(self.log_page, "Main Log")

        # Create a vertical sizer for the log page
        log_page_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add a horizontal sizer for buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # NOTE: It's wx.FONTSTYLE_NORMAL with underscore, not wx.FONTSTYLE.NORMAL with dot
        # Style buttons with icons and custom fonts
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

        # Add the new Test Google Sheets button with a better icon
        self.test_google_sheets_button = wx.Button(self.log_page, label=" Test Google Sheets")
        self.test_google_sheets_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_LIST_VIEW, wx.ART_BUTTON, (16, 16)))
        self.test_google_sheets_button.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        # Add buttons to the horizontal button sizer
        button_sizer.Add(self.process_log_button, 0, wx.ALL, 2)
        button_sizer.Add(self.autoshard_button, 0, wx.ALL, 2)
        button_sizer.Add(self.monitor_button, 0, wx.ALL, 2)
        button_sizer.Add(self.test_google_sheets_button, 0, wx.ALL, 2)  # Add the test button

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
        self.test_google_sheets_button.Bind(wx.EVT_BUTTON, self.on_test_google_sheets)

        # Add menu items
        menu_bar = wx.MenuBar()
        config_menu = wx.Menu()
        self.discord_check = config_menu.AppendCheckItem(wx.ID_ANY, "Use Discord")
        self.googlesheet_check = config_menu.AppendCheckItem(wx.ID_ANY, "Use Google Sheets")
        config_menu.AppendSeparator()
        edit_config_item = config_menu.Append(wx.ID_ANY, "Edit Configuration")  # Add menu item for config dialog
        menu_bar.Append(config_menu, "Config")

        # Add Help menu with About item
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "About")
        menu_bar.Append(help_menu, "Help")
        self.SetMenuBar(menu_bar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_toggle_check, self.discord_check)
        self.Bind(wx.EVT_MENU, self.on_toggle_check, self.googlesheet_check)
        self.Bind(wx.EVT_MENU, self.on_edit_config, edit_config_item)  # Bind the new menu item
        self.Bind(wx.EVT_MENU, self.on_about, about_item)  # Bind About menu item

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
            The value from the config_manager with appropriate defaults
            
        Raises:
            AttributeError: If the attribute doesn't exist in the config_manager either
        """
        try:
            # Define default values for common config attributes
            defaults = {
                'log_file_path': '',
                'google_sheets_webhook': '',
                'discord_webhook_url': '',
                'console_key': '',
                'colors': {},
                'use_discord': True,
                'use_googlesheet': True
            }
            
            # Try to get the property from the config_manager with appropriate default
            default_value = defaults.get(name, None)
            return self.config_manager.get(name, default_value)
        except Exception as e:
            # If that fails or if the property doesn't exist, raise AttributeError
            raise AttributeError(f"Neither LogAnalyzerFrame nor ConfigManager has an attribute named '{name}'") from e

    def check_for_updates(self):
        """Check for updates by querying the GitHub API."""
        current_version = get_version()
        updater.check_for_updates(self, current_version)

    def _add_tab(self, notebook, tab_title, url, params=None):
        """
        Create a new tab with a grid and a refresh button.

        Args:
            notebook (wx.Notebook): The notebook to add the tab to.
            tab_title (str): The title of the new tab.
            url (str): The URL to fetch JSON data from.
            params (dict, optional): Parameters to pass to the request.
        """
        # Check if a tab with the same title already exists
        if tab_title in self.tab_references:
            return self.tab_references[tab_title]  # Return None if the tab already exists

        # Create a new panel for the tab
        new_tab = wx.Panel(notebook)

        # Create a vertical sizer for the tab
        tab_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add a refresh button
        refresh_button = wx.Button(new_tab, label="Refresh")
        tab_sizer.Add(refresh_button, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        # Add a grid to display the JSON data
        grid = wx.grid.Grid(new_tab)
        grid.CreateGrid(0, 0)  # Start with an empty grid
        tab_sizer.Add(grid, 1, wx.EXPAND | wx.ALL, 2)

        # Set the sizer for the tab
        new_tab.SetSizer(tab_sizer)

        # Add the new tab to the notebook
        notebook.AddPage(new_tab, tab_title)

        # Store the URL and params directly on objects
        refresh_button.url = url
        refresh_button.params = params
        refresh_button.grid = grid

        # Bind the refresh button to fetch and update the grid
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_tab)

        # Store the tab reference in the dictionary
        self.tab_references[tab_title] = (grid,refresh_button)

        return grid,refresh_button  # Return the grid for further updates

    def add_tab(self, url, tab_title, params=None, top_panel=None):
        """
        Add a new tab to the notebook with a grid and optional top panel.

        Args:
            url (str): The URL to fetch JSON data from.
            tab_title (str): The title of the new tab.
            params (dict, optional): A dictionary of parameters to pass to the request.
            top_panel (wx.Panel, optional): A panel to place above the grid (e.g., a form).
        """
        # Check if tab already exists
        if tab_title in self.tab_references:
            # Tab exists, just return the existing grid
            grid,refresh_button = self.tab_references[tab_title]            
            return grid,refresh_button
        
        # If tab doesn't exist, use _add_tab to create it
        grid,refresh_button = self._add_tab(self.notebook, tab_title, url, params)

        if grid and top_panel:
            # Add the top panel to the tab's sizer
            parent_panel = grid.GetParent()
            parent_sizer = parent_panel.GetSizer()
            parent_sizer.Insert(0, top_panel, 0, wx.EXPAND | wx.ALL, 5)
            parent_panel.Layout()

        # Trigger initial refresh if the grid was created

        return grid,refresh_button

    def execute_refresh_event(self, refresh_button):
        event = wx.CommandEvent(wx.wxEVT_BUTTON)
        event.SetEventObject(refresh_button)
        self.on_refresh_tab(event)

    def add_form_tab(self, url, tab_title, form_fields={}, params=None):
        """
        Add a new tab with a form at the top and a grid at the bottom.

        Args:
            url (str): The URL to fetch data for the grid.
            tab_title (str): The title of the new tab.
            form_fields (dict): A dictionary where keys are field names and values are input types.
            params (dict, optional): Parameters to pass to the request.
        """
        # Check if tab already exists
        if tab_title in self.tab_references:
            # Tab exists, just return the existing grid
            grid,refresh_button = self.tab_references[tab_title]            
            return grid,refresh_button
                
        # Create the base tab if it doesn't exist
        grid,refresh_button = self._add_tab(self.notebook, tab_title, url, params)

        if grid:
            # Use the grid's parent as the correct parent for the form panel
            parent_panel = grid.GetParent()
            form_panel = wx.Panel(parent_panel)  # Correct parent assignment

            form_sizer = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
            form_sizer.AddGrowableCol(1, 1)

            form_controls = {}

            for field_name, field_type in form_fields.items():
                label = wx.StaticText(form_panel, label=field_name)
                if field_type == 'text':
                    control = wx.TextCtrl(form_panel)
                elif field_type == 'dropdown':
                    control = wx.Choice(form_panel, choices=form_fields.get('choices', []))
                elif field_type == 'check':
                    control = wx.CheckBox(form_panel)
                elif field_type == 'number':
                    control = wx.TextCtrl(form_panel)
                    control.SetValidator(NumericValidator(allow_float=True))
                    control.field_type = 'number'  # Store field type for validation
                else:
                    raise ValueError(f"Unsupported field type: {field_type}")
                form_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
                form_sizer.Add(control, 1, wx.EXPAND)
                form_controls[field_name] = control

            # Add the submit button aligned to the right
            submit_button = wx.Button(form_panel, label="Submit")
            button_sizer = wx.BoxSizer(wx.HORIZONTAL)
            button_sizer.AddStretchSpacer()
            button_sizer.Add(submit_button, 0, wx.ALL, 5)

            # Wrap the form and button sizer in a vertical sizer
            vertical_sizer = wx.BoxSizer(wx.VERTICAL)
            vertical_sizer.Add(form_sizer, 0, wx.EXPAND | wx.ALL, 5)
            vertical_sizer.Add(button_sizer, 0, wx.EXPAND)

            # Set the maximum width of the form to half of the parent
            max_width = parent_panel.GetSize().GetWidth() // 2
            form_panel.SetMaxSize(wx.Size(max_width, -1))

            form_panel.SetSizer(vertical_sizer)

            # Add the form panel to the tab's sizer
            parent_sizer = parent_panel.GetSizer()
            parent_sizer.Insert(0, form_panel, 0, wx.EXPAND | wx.ALL, 5)
            parent_panel.Layout()

            # Bind the submit button
            submit_button.Bind(wx.EVT_BUTTON, lambda event: self.on_form_submit(event, url, refresh_button, form_controls, params.get("sheet", "")))
            self.tab_references[tab_title] = (grid,refresh_button)  # Store the grid reference
        return grid,refresh_button

    def on_refresh_tab(self, event):
        """
        Handle refresh button click.
        Extracts URL and grid from the button and refreshes data.
        """
        button = event.GetEventObject()
        params = button.params
        
        # Resolve callable parameters if necessary
        if params:
            resolved_params = {}
            for key, value in params.items():
                if callable(value):
                    try:
                        resolved_params[key] = value(self)
                    except Exception as e:
                        wx.MessageBox(f"Error resolving parameter '{key}': {e}", 
                                    "Error", wx.OK | wx.ICON_ERROR)
                        return
                else:
                    resolved_params[key] = value
            params = resolved_params
        
        # Set loading state in the grid
        self.set_grid_loading(button.grid, True)
        
        # Start the fetch in a separate thread
        threading.Thread(
            target=self.fetch_and_update, 
            args=(button.url, params, button.grid), 
            daemon=True
        ).start()

    def set_grid_loading(self, grid, is_loading):
        """
        Set the visual state of a grid to indicate loading.
        
        Args:
            grid (wx.grid.Grid): The grid to update
            is_loading (bool): Whether the grid is loading data
        """
        if is_loading:
            # Clear existing data and show "Loading..." in the first cell
            if grid.GetNumberRows() > 0:
                grid.DeleteRows(0, grid.GetNumberRows())
            grid.AppendRows(1)
            if grid.GetNumberCols() == 0:
                grid.AppendCols(1)
            grid.SetCellValue(0, 0, "Loading data...")
            grid.SetCellAlignment(0, 0, wx.ALIGN_CENTER, wx.ALIGN_CENTER)
            grid.Enable(False)
        else:
            grid.Enable(True)
            # Make all cells read-only without disabling the grid
            grid.EnableEditing(False)

    def fetch_and_update(self, url, params, target_grid):
        """
        Fetch data from URL and update the target grid.
        
        Args:
            url (str): URL to fetch data from
            params (dict): Parameters for the request
            target_grid (wx.grid.Grid): Grid to update with the data
        """
        try:
            if not url:
                safe_call_after(wx.MessageBox, "No URL configured for this tab.", 
                                "Error", wx.OK | wx.ICON_ERROR)
                return
                
            response = requests.get(url, params=params)
            if response.status_code != 200:
                safe_call_after(wx.MessageBox, 
                                f"Failed to fetch data. HTTP Status: {response.status_code}", 
                                "Error", wx.OK | wx.ICON_ERROR)
                return

            data = response.json()
            if not isinstance(data, list) or not data:
                return

            # Update the grid with data
            safe_call_after(self.update_sheets_grid, data, target_grid)
        except requests.RequestException as e:
            safe_call_after(self.log_text.AppendText, f"Network error while fetching data: {e}\n")
        except json.JSONDecodeError:
            safe_call_after(self.log_text.AppendText, "Failed to decode JSON response from server.\n")
        except Exception as e:
            safe_call_after(self.log_text.AppendText, f"Unexpected error during data fetch: {e}\n")
        finally:
            # Clear loading state
            safe_call_after(self.set_grid_loading, target_grid, False)

    def update_dynamic_labels(self):
        """Update the username, shard, version, and mode labels dynamically."""
        try:
            # Use instance properties if they're set, fall back to event_handler if needed
            username = self.username if self.username != "Unknown" and self.event_handler else getattr(self.event_handler, "username", "Unknown")
            shard = self.shard if self.shard != "Unknown" and self.event_handler else getattr(self.event_handler, "current_shard", "Unknown")
            version = self.version if self.version != "Unknown" and self.event_handler else getattr(self.event_handler, "current_version", "Unknown")
            mode = self.mode if self.mode != "None" and self.event_handler else getattr(self.event_handler, "current_mode", "None")

            self.username_label.SetLabel(f"Username: {username}")
            self.shard_label.SetLabel(f"Shard: {shard}")
            self.version_label.SetLabel(f"Version: {version}")
            self.mode_label.SetLabel(f"Mode: {mode or 'None'}")
        except Exception as e:
            self.log_text.AppendText(f"Error updating labels: {e}\n")

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
            self.log_text.AppendText(f"Error updating shard/version/username/mode: {e}\n")

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

    def on_about(self, event):
        """Show the About dialog."""
        from gui_module import AboutDialog  # Import AboutDialog from gui_module
        dialog = AboutDialog(self, update_callback=self.check_for_updates)
        dialog.ShowModal()

    def update_monitoring_buttons(self, started):
        """
        Update the state of the monitoring and process buttons.

        Args:
            started (bool): True if monitoring has started, False otherwise.
        """
        if self.monitoring:  # Check the actual monitoring state
            self.monitor_button.SetLabel("Stop Monitoring")
            self.process_log_button.Enable(False)
            self.SetStatusText("Monitoring active")
        else:
            self.monitor_button.SetLabel("Start Monitoring")
            self.process_log_button.Enable(True)
            self.SetStatusText("Monitoring stopped")

    def initialize_config(self):
        """Initialize configuration: load settings, ensure config exists with latest template, and validate."""
        try:
            # 1. Load configuration values from ConfigManager
            self.default_log_file_path = self.log_file_path
            self.discord_check.Check(self.use_discord)
            self.googlesheet_check.Check(self.use_googlesheet)
            
            
            # 3. Validate critical settings and prompt for missing ones
            missing_settings = []
            if not self.default_log_file_path:
                missing_settings.append("Log file path")
            elif not os.path.exists(self.default_log_file_path):
                missing_settings.append("Log file path does not exist")
                
            if not self.google_sheets_webhook:
                missing_settings.append("Google Sheets webhook URL")
                self.googlesheet_check.Check(False)  # Uncheck Google Sheets usage
                
            if not self.discord_webhook_url:
                missing_settings.append("Discord webhook URL")
                self.discord_check.Check(False)  # Uncheck Discord usage

            if missing_settings:
                wx.MessageBox(
                    f"The following settings are missing or invalid: {', '.join(missing_settings)}.\n"
                    "Please configure them to start safely.",
                    "Configuration Required",
                    wx.OK | wx.ICON_WARNING
                )
                self.on_edit_config(None)  # Show the configuration dialog modal
            
        except Exception as e:
            if hasattr(self, 'log_text') and self.log_text is not None:
                self.log_text.AppendText(f"Error initializing configuration: {e}\n")
            else:
                print(f"Error initializing configuration: {e}")

    def on_process_log(self, event):
        """Open the process log dialog."""
        dialog = ProcessDialog(self)
        dialog.ShowModal()

    def run_process_log(self, log_file):
        """Run log processing."""
        if not self or not self.IsShown():
            return  # Prevent actions if the frame is destroyed
        if self.monitoring:
            wx.MessageBox("Stop monitoring first before processing log", "Cannot Process", wx.OK | wx.ICON_INFORMATION)
            return
        
        self.log_text.Clear()
        self.SetStatusText("Processing log file...")
        
        # Disable buttons during processing
        self.process_log_button.Enable(False)
        self.monitor_button.Enable(False)
        
        
        thread = threading.Thread(target=self.run_process_log_thread, args=(log_file, True, False, False))
        thread.daemon = True
        thread.start()

    def run_process_log_thread(self, log_file, process_all, use_discord, use_googlesheet):
        """Run log analysis in thread"""
        try:
            # Call main with process_once=True
            log_analyzer.main(
                process_all=process_all,
                use_discord=use_discord,
                process_once=True,
                use_googlesheet=use_googlesheet,
                log_file_path=log_file
            )
            wx.CallAfter(self.SetStatusText, "Processing completed")
        except Exception as e:
            wx.CallAfter(self.log_text.AppendText, f"Error processing log: {e}\n")
            wx.CallAfter(self.SetStatusText, "Error during processing")
        finally:
            wx.CallAfter(self.process_log_button.Enable, True)
            wx.CallAfter(self.monitor_button.Enable, True)
    
    def on_monitor(self, event):
        """Handle start/stop monitoring button click event."""
        if not self or not self.IsShown():
            return  # Prevent actions if the frame is destroyed
        if self.monitoring:
            self.stop_monitoring()
            self.update_monitoring_buttons(started=False)
        else:
            self.start_monitoring()
            self.update_monitoring_buttons(started=True)
    
    def start_monitoring(self, delay_ms=0):
        """Start log file monitoring.
        
        Args:
            delay_ms (int): Delay in milliseconds before starting the monitoring
        """
        if self.monitoring:  # Prevent starting monitoring if already active
            return
        self.log_text.Clear()
        self.monitoring = True  # Update monitoring state here
        self.SetStatusText("Preparing to monitor log file...")
        
        # Use the default log file path from the configuration
        log_file = self.default_log_file_path
        if not log_file:
            wx.MessageBox("Log file path is not set in the configuration.", "Error", wx.OK | wx.ICON_ERROR)
            self.monitoring = False
            return

        process_all = True  # Always process the entire log
        use_discord = self.discord_check.IsChecked()
        use_googlesheet = self.googlesheet_check.IsChecked()
        
        # Delay the start of monitoring to ensure UI is fully loaded
        if delay_ms > 0:
            wx.CallLater(delay_ms, self._start_monitoring_thread, log_file, process_all, use_discord, use_googlesheet)
            self.log_text.AppendText(f"Monitoring will start in {delay_ms/1000:.1f} seconds...\n")
        else:
            self._start_monitoring_thread(log_file, process_all, use_discord, use_googlesheet)
            
    def _start_monitoring_thread(self, log_file, process_all, use_discord, use_googlesheet):
        """Start the actual monitoring thread after any delay."""
        if not self.monitoring:  # Check if monitoring was canceled during delay
            return
            
        self.log_text.AppendText("Starting log monitoring...\n")
        # Run in a separate thread to keep UI responsive
        thread = threading.Thread(target=self.run_monitoring, args=(log_file, process_all, use_discord, use_googlesheet))
        thread.daemon = True
        thread.start()

    def on_username_change(self, username, old_username):
        """
        Handle username change events.

        Args:
            username (str): The new username.
            old_username (str): The previous username.
        """
        self.username = username
        self.update_dynamic_labels()
        for tab_title, (grid, refresh_button) in self.tab_references.items():
            if refresh_button and refresh_button.grid == grid:
                # Update the grid's username if it matches the current tab
                safe_call_after(wx.CallLater, 500, self.execute_refresh_event, refresh_button)

    def run_monitoring(self, log_file, process_all, use_discord, use_googlesheet):
        """Run monitoring in thread."""
        try:
            # Call startup with event subscriptions passed as kwargs
            result = log_analyzer.startup(
                process_all=process_all,
                use_discord=use_discord,
                process_once=False,
                use_googlesheet=use_googlesheet,
                log_file_path=log_file,
                on_shard_version_update=self.on_shard_version_update,
                on_mode_change=self.on_mode_change,
                on_username_change=self.on_username_change,
            )

            if result:
                self.event_handler, self.observer = result
                self.update_dynamic_labels()  # Update labels after starting monitoring

                # Start the observer thread explicitly
                if self.observer:
                    self.observer.start()

        except Exception as e:
            wx.CallAfter(self.log_text.AppendText, f"Error starting monitoring: {e}\n")
            wx.CallAfter(self.update_monitoring_buttons, False)
            self.monitoring = False
    
    def stop_monitoring(self):
        """Stop log file monitoring."""
        if not self.monitoring:  # Prevent stopping monitoring if not active
            return
        if self.event_handler and self.observer:
            log_analyzer.stop_monitor(self.event_handler, self.observer)
            self.event_handler = None
            self.observer = None
        self.monitoring = False  # Ensure monitoring state is updated
    def append_log_message(self, message, regex_pattern=None):
        wx.CallAfter(self._append_log_message, message, regex_pattern)
    def _append_log_message(self, message, regex_pattern=None):
        """
        Append a log message to the GUI log output area.

        Args:
            message: The log message to append.
            regex_pattern: The regex pattern name that matched the message (optional).
        """
        if self.log_text:
            # Default colors
            foreground_color = wx.Colour(255, 255, 255)  # White text
            background_color = wx.Colour(0, 0, 0)  # Black background

            # Load colors and patterns from the configuration
            colors = getattr(self, "colors", {})
            if regex_pattern:
                for color_spec, pattern_names in colors.items():
                    if regex_pattern in pattern_names:
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
            self.log_text.AppendText(message + "\n")

    def save_window_info(self):
        """Save the window's current position, size, and state to the Windows registry."""
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY_PATH)
            position = list(self.GetPosition())
            size = list(self.GetSize())
            is_maximized = self.IsMaximized()
            is_iconized = self.IsIconized()
            winreg.SetValueEx(key, "Position", 0, winreg.REG_SZ, f"{position[0]},{position[1]}")
            winreg.SetValueEx(key, "Size", 0, winreg.REG_SZ, f"{size[0]},{size[1]}")
            winreg.SetValueEx(key, "Maximized", 0, winreg.REG_SZ, str(is_maximized))
            winreg.SetValueEx(key, "Iconized", 0, winreg.REG_SZ, str(is_iconized))
            winreg.CloseKey(key)
        except Exception as e:
            self.log_text.AppendText(f"Error saving window info: {e}\n")

    def restore_window_info(self):
        """Restore the window's position, size, and state from the Windows registry."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY_PATH, 0, winreg.KEY_READ)
            position = winreg.QueryValueEx(key, "Position")[0].split(",")
            size = winreg.QueryValueEx(key, "Size")[0].split(",")
            is_maximized = winreg.QueryValueEx(key, "Maximized")[0] == "True"
            is_iconized = winreg.QueryValueEx(key, "Iconized")[0] == "True"
            winreg.CloseKey(key)

            # Convert position and size to integers
            position = [int(position[0]), int(position[1])]
            size = [int(size[0]), int(size[1])]

            # Check if the window fits in any display
            fits_in_display = False
            for i in range(wx.Display.GetCount()):
                display_bounds = wx.Display(i).GetGeometry()
                if display_bounds.Contains(wx.Rect(position[0], position[1], size[0], size[1])):
                    fits_in_display = True
                    break

            # If the window does not fit in any display, default to the primary display
            if not fits_in_display:
                primary_display_bounds = wx.Display(0).GetGeometry()
                position[0] = max(primary_display_bounds.GetLeft(), min(position[0], primary_display_bounds.GetRight() - size[0]))
                position[1] = max(primary_display_bounds.GetTop(), min(position[1], primary_display_bounds.GetBottom() - size[1]))

            # Set the position and size
            self.SetPosition(wx.Point(*position))
            self.SetSize(wx.Size(*size))

            # Restore maximized or iconized state
            if is_maximized:
                self.Maximize()
            elif is_iconized:
                self.Iconize()
        except FileNotFoundError:
            # Use default position and size if registry key is not found
            self.SetPosition(wx.Point(*DEFAULT_WINDOW_POSITION))
            self.SetSize(wx.Size(*DEFAULT_WINDOW_SIZE))
        except Exception as e:
            self.log_text.AppendText(f"Error restoring window info: {e}\n")

    def on_window_move_or_resize(self, event):
        """Handle window move or resize events."""
        if not self.save_timer.IsRunning():
            self.save_timer.Start(500)  # Start the timer only if it's not already running
        event.Skip()

    def on_save_timer(self, event):
        """Save window info when the timer fires."""
        if self.save_timer:
            self.save_window_info()
            self.save_timer.Stop()

    def on_autoshard(self, event):
        """Handle Auto Shard button click."""
        try:
            self.send_keystrokes_to_sc()  # Call the method to send keystrokes
            self.log_text.AppendText("Auto Shard keystrokes sent.\n")
        except Exception as e:
            self.log_text.AppendText(f"Error sending Auto Shard keystrokes: {e}\n")

    def send_keystrokes_to_sc(self):
        """Send predefined keystrokes to the Star Citizen window."""
        if not self.default_log_file_path:
            wx.MessageBox("Log file path is not set in the configuration.", "Error", wx.OK | wx.ICON_ERROR)
            return

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
        menu_item = self.FindItemById(event.GetId())
        if menu_item:
            menu_item.Check(not menu_item.IsChecked())

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
        
        # Check if config was saved (i.e., Accept was clicked, not Cancel)
        config_saved = False
        if hasattr(self, 'config_dialog') and self.config_dialog:
            config_saved = getattr(self.config_dialog, 'config_saved', False)
        
        # Only reload configuration if changes were saved
        if config_saved:
            self.initialize_config()
            if self.monitoring:
                self.stop_monitoring()
                self.start_monitoring()
            self.update_google_sheets_tabs()  # Update tabs after reloading config


    def update_google_sheets_tabs(self, refresh_tabs=[]):
        """Update Google Sheets tabs based on current configuration."""
        # Only add/update Google Sheets tabs if the webhook URL is valid
        if self.google_sheets_webhook and self.googlesheet_check.IsChecked():
            # Define the tabs we want to ensure exist
            if not len(self.tab_references):            
                required_tabs = [
                    {"title": "Stats", "params": None},
                    {"title": "SC Default", "params": {"sheet": "SC_Default", "username": lambda self: self.username}},
                    {"title": "SC Squadrons Battle", "params": {"sheet": "EA_SquadronBattle", "username": lambda self: self.username}},
                    {"title": "Materials", "params": {"sheet": "Materials", "username": lambda self: self.username}, 
                    "form_fields": {"Material": "text", "Qty": "number", "committed": "check"}}
                ]
                # First, create any missing tabs
                for tab_info in required_tabs:
                    title = tab_info["title"]
                    # Create the tab if it doesn't exist
                    if "form_fields" in tab_info:
                        self.add_form_tab(self.google_sheets_webhook, title, 
                                        params=tab_info["params"], 
                                        form_fields=tab_info["form_fields"])
                    else:
                        self.add_tab(self.google_sheets_webhook, title, params=tab_info["params"])
            else:            
                # Now refresh all tabs
                for title,t in self.tab_references.items():
                    if title in refresh_tabs or len(refresh_tabs) == 0:
                        self.execute_refresh_event(t[1])
            
            # No need to remove tabs - once created they stay in the UI
            # This simplifies the UI experience and matches your requirement

    def update_sheets_grid(self, json_data, grid):
        """
        Update the given grid with the provided JSON data.

        Args:
            json_data (list): The JSON data to display.
            grid (wx.grid.Grid): The grid to update.
        """
        if not json_data:
            grid.ClearGrid()
            return

        # Get the keys from the first dictionary as column headers
        headers = list(json_data[0].keys())

        # Resize the grid to fit the data
        grid.ClearGrid()
        if grid.GetNumberRows() > 0:
            grid.DeleteRows(0, grid.GetNumberRows())
        if grid.GetNumberCols() > 0:
            grid.DeleteCols(0, grid.GetNumberCols())
        grid.AppendCols(len(headers))
        grid.AppendRows(len(json_data))

        # Set column headers
        for col, header in enumerate(headers):
            grid.SetColLabelValue(col, header)

        # Populate the grid with data
        for row, entry in enumerate(json_data):
            for col, header in enumerate(headers):
                grid.SetCellValue(row, col, str(entry[header]))

        # Auto-size columns only if there are valid rows and columns
        if grid.GetNumberCols() > 0 and grid.GetNumberRows() > 0:
            grid.AutoSizeColumns()

    def on_form_submit(self, event, url, refresh_button, form_controls, sheet):
        """
        Handle form submission.

        Args:
            event (wx.Event): The event object.
            url (str): The URL to send the form data to.
            grid (wx.grid.Grid): The grid to update after submission.
        """
        try:
            # Collect form data
            form_data = {}
            for field, control in form_controls.items():
                # Check numeric fields specifically
                if hasattr(control, 'field_type') and control.field_type == 'number':
                    try:
                        # Convert to appropriate numeric type before adding to form_data
                        value = control.GetValue()
                        if '.' in value:
                            form_data[field] = float(value)
                        else:
                            form_data[field] = int(value) if value else 0
                    except ValueError:
                        wx.MessageBox(f"'{field}' must be a valid number.", "Validation Error", wx.OK | wx.ICON_ERROR)
                        return
                else:
                    form_data[field] = control.GetValue()
            form_data["sheet"] = sheet  # Add the sheet name to the form data
            # Use log_analyzer's update_google_sheets method to send data
            success = self.event_handler.update_google_sheets(form_data, sheet)
            if success:
                wx.MessageBox("Form submitted successfully.", "Success", wx.OK | wx.ICON_INFORMATION)
                # Clear all form fields after successful submission
                for field, control in form_controls.items():
                    if hasattr(control, 'field_type') and control.field_type == 'number':
                        control.SetValue("")
                    elif isinstance(control, wx.CheckBox):
                        control.SetValue(False)
                    elif isinstance(control, wx.Choice):
                        if control.GetCount() > 0:
                            control.SetSelection(0)
                    else:
                        control.SetValue("")
                # Optionally refresh the grid
                self.execute_refresh_event(refresh_button)
            else:
                wx.MessageBox("Failed to submit form. Please check the logs for details.", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error submitting form: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_test_google_sheets(self, event):
        """Handle the Test Google Sheets button click."""
        if not self.google_sheets_webhook:
            wx.MessageBox("Google Sheets webhook URL is not set in the configuration.", "Error", wx.OK | wx.ICON_ERROR)
            return

        # Mock data to send
        mock_data = {
            "sheet": "TestSheet",
            "log_type": "TestLog",
            "username": "TestUser",
            "action": "Test Action",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "details": "This is a test entry for Google Sheets."
        }

        try:
            # Send the mock data to Google Sheets
            success = self.event_handler.update_google_sheets(mock_data, "SC_Default")
            if success:
                wx.MessageBox("Test entry sent successfully to Google Sheets.", "Success", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox("Failed to send test entry to Google Sheets. Check the logs for details.", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error sending test entry to Google Sheets: {e}", "Error", wx.OK | wx.ICON_ERROR)


    def on_close(self, event):
        """Handle window close event."""
        self.save_window_info()
        # Disconnect event bindings to prevent callbacks after destruction
        self.Unbind(wx.EVT_MOVE)
        self.Unbind(wx.EVT_SIZE)
        self.save_timer.Stop()
        self.save_timer = None

        if self.monitoring:
            self.stop_monitoring()
        
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

    def async_init_tabs(self):
        """
        Initialize tabs asynchronously after the main window is loaded and stable.
        This prevents UI freezing during startup and improves user experience.
        """
        # Update status to indicate we're loading tabs
        self.SetStatusText("Loading data tabs...")
        
        # Create a timer to delay tab creation (ensures window is fully rendered)
        wx.CallLater(1000, self._create_and_load_tabs)
    
    def _create_and_load_tabs(self):
        """
        Create and load tabs with data after a delay to ensure main window is stable.
        Separated from async_init_tabs to allow different timing options.
        """
        try:
            # Only proceed if Google Sheets is enabled
            if self.google_sheets_webhook and self.googlesheet_check.IsChecked():
                # Log that we're starting to create tabs
                self.log_text.AppendText("Creating data tabs...\n")
                
                # Define required tabs with their configuration
                required_tabs = [
                    {"title": "Stats", "params": None},
                    {"title": "SC Default", "params": {"sheet": "SC_Default", "username": lambda self: self.username}},
                    {"title": "SC Squadrons Battle", "params": {"sheet": "EA_SquadronBattle", "username": lambda self: self.username}},
                    {"title": "Materials", "params": {"sheet": "Materials", "username": lambda self: self.username}, 
                    "form_fields": {"Material": "text", "Qty": "number", "committed": "check"}}
                ]
                
                # Create each tab asynchronously 
                for i, tab_info in enumerate(required_tabs):
                    # Use another delayed call to stagger tab creation
                    wx.CallLater(200 * i, self._create_single_tab, tab_info)
                
                # After all tabs are scheduled for creation, update status
                wx.CallLater(200 * len(required_tabs) + 500, 
                             lambda: self.SetStatusText("All tabs created"))
            else:
                self.SetStatusText("Google Sheets integration disabled")
        except Exception as e:
            self.log_text.AppendText(f"Error creating tabs: {e}\n")
            self.SetStatusText("Error creating tabs")
    
    def _create_single_tab(self, tab_info):
        """
        Create a single tab with its configuration.
        
        Args:
            tab_info (dict): Tab configuration information
        """
        try:
            title = tab_info["title"]
            self.SetStatusText(f"Creating tab: {title}...")
            
            # Create the tab based on its type
            if "form_fields" in tab_info:
                self.add_form_tab(
                    self.google_sheets_webhook, 
                    title,
                    params=tab_info["params"],
                    form_fields=tab_info["form_fields"]
                )
            else:
                self.add_tab(
                    self.google_sheets_webhook, 
                    title, 
                    params=tab_info["params"]
                )
                
            # Update log with creation status
            self.log_text.AppendText(f"Tab '{title}' created\n")
            
            # Check if this is the last tab and trigger refresh if needed
            if len(self.tab_references) == len(self._get_required_tabs()):
                # All tabs created, trigger initial data load
                wx.CallLater(500, self._refresh_all_tabs)
        except Exception as e:
            self.log_text.AppendText(f"Error creating tab '{tab_info.get('title', 'unknown')}': {e}\n")
    
    def _refresh_all_tabs(self):
        """Refresh all tabs with current data"""
        try:
            self.SetStatusText("Loading tab data...")
            for title, (grid, refresh_button) in self.tab_references.items():
                # Stagger refresh calls to prevent simultaneous requests
                wx.CallLater(300, self.execute_refresh_event, refresh_button)
            
            # Update status when complete
            wx.CallLater(500 + (300 * len(self.tab_references)), 
                         lambda: self.SetStatusText("Ready"))
        except Exception as e:
            self.log_text.AppendText(f"Error refreshing tabs: {e}\n")
    
    def _get_required_tabs(self):
        """Get the list of required tabs - factored out for maintainability"""
        return [
            "Stats", 
            "SC Default", 
            "SC Squadrons Battle", 
            "Materials"
        ]

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
                self.log_text.AppendText("Developer tools activated\n")
            else:
                self.SetStatusText("Ready")
                self.log_text.AppendText("Developer tools deactivated\n")
        
        # Process the event normally
        event.Skip()
        
    def update_debug_ui_visibility(self):
        """Update UI elements based on debug mode state"""
        if hasattr(self, 'test_google_sheets_button'):
            self.test_google_sheets_button.Show(self.debug_mode)
            
        # Force layout update
        if hasattr(self, 'log_page') and self.log_page:
            self.log_page.Layout()
            
        # Update GUI refresh
        if hasattr(self, 'GetMenuBar') and self.GetMenuBar():
            self.GetMenuBar().Refresh()
        self.Refresh()

def main():
    if os.path.basename(sys.argv[0]) in (UPDATER_EXECUTABLE,LEGACY_UPDATER):
        updater.update_application()    
    else:
        updater.cleanup_updater_script()
    app = wx.App()
    frame = LogAnalyzerFrame()
    frame.Show()
    frame.async_init_tabs()  # Initialize tabs asynchronously
    app.MainLoop()

if __name__ == "__main__":
    main()