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
from config_utils import emit_default_config, get_application_path, renew_config  # Import renew_config
from gui_module import RedirectText, KeyValueGrid, ConfigDialog, ProcessDialog, WindowsHelper, NumericValidator  # Import reusable components
from PIL import Image
import mss
from pyzbar.pyzbar import decode
import shutil  # For file operations
import tempfile  # For temporary directories
import subprocess

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
GITHUB_API_URL = "https://api.github.com/repos/IJOL/SCLogAnalyzer/releases"
APP_EXECUTABLE = "SCLogAnalyzer.exe"  # Replace with your app's executable name

class LogAnalyzerFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="SC Log Analyzer", size=(800, 600))
               # Set flag for GUI mode
        log_analyzer.main.in_gui = True  # Ensure GUI mode is enabled        
        # Ensure default config exists
        self.ensure_default_config()

        # Set up a custom log handler for GUI
        log_analyzer.main.gui_log_handler = self.append_log_message
        
        # Initialize variables
        self.observer = None
        self.event_handler = None
        self.monitoring = False
        
        # Create main panel
        panel = wx.Panel(self)

        # Create main vertical sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add dynamic labels for username, shard, and version
        bold_font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.username_label = wx.StaticText(panel, label="Username: Loading...")
        self.username_label.SetFont(bold_font)
        self.shard_label = wx.StaticText(panel, label="Shard: Loading...")
        self.shard_label.SetFont(bold_font)
        self.version_label = wx.StaticText(panel, label="Version: Loading...")
        self.version_label.SetFont(bold_font)
        label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        label_sizer.Add(self.username_label, 1, wx.ALL | wx.EXPAND, 5)
        label_sizer.Add(self.shard_label, 1, wx.ALL | wx.EXPAND, 5)
        label_sizer.Add(self.version_label, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(label_sizer, 0, wx.EXPAND)

        # Create notebook for log output and Google Sheets data
        self.notebook = wx.Notebook(panel)
        self.log_page = wx.Panel(self.notebook)
        self.notebook.AddPage(self.log_page, "Main Log")

        # Create a vertical sizer for the log page
        log_page_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add a horizontal sizer for buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

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
        self.monitor_button.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,wx.FONTWEIGHT_BOLD))

        # Add buttons to the horizontal button sizer
        button_sizer.Add(self.process_log_button, 0, wx.ALL, 2)
        button_sizer.Add(self.autoshard_button, 0, wx.ALL, 2)
        button_sizer.Add(self.monitor_button, 0, wx.ALL, 2)

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
        
        # Try to get the default log file path from config
        self.default_log_file_path = None
        self.google_sheets_webhook = None
        self.discord_webhook_url = None
        self.console_key = "º"  # Default console key
        self.load_default_config()
        self.validate_startup_settings()  # Validate settings before proceeding

        # Only add Google Sheets tabs if the webhook URL is valid
        if self.google_sheets_webhook:
            self.update_google_sheets_tabs()

        # Set up stdout redirection
        sys.stdout = RedirectText(self.log_text)

        # Create taskbar icon
        self.taskbar_icon = TaskBarIcon(self)

        # Check if the app is started with the --start-hidden flag
        if STARTUP_COMMAND_FLAG in sys.argv:
            self.Hide()  # Hide the main window at startup

        # Start monitoring by default when GUI is launched
        wx.CallAfter(self.start_monitoring)
        wx.CallAfter(self.update_monitoring_buttons, True)

        # Check for updates at app initialization
        wx.CallAfter(self.check_for_updates)

        self.save_timer = wx.Timer(self)  # Timer to delay saving window info
        self.Bind(wx.EVT_TIMER, self.on_save_timer, self.save_timer)
        self.Bind(wx.EVT_MOVE, self.on_window_move_or_resize)
        self.Bind(wx.EVT_SIZE, self.on_window_move_or_resize)

        self.restore_window_info()  # Restore window position, size, and state from the registry

        # Bind close event to save window position
        self.Bind(wx.EVT_CLOSE, self.on_close)
        wx.CallAfter(self.update_dynamic_labels) 

    def check_for_updates(self):
        """Check for updates by querying the GitHub API."""
        try:
            response = requests.get(GITHUB_API_URL)
            if response.status_code != 200:
                wx.MessageBox("Failed to check for updates.", "Error", wx.OK | wx.ICON_ERROR)
                return

            releases = response.json()
            if not isinstance(releases, list) or not releases:
                wx.MessageBox("No releases found.", "Error", wx.OK | wx.ICON_ERROR)
                return

            # Find the latest release named SCLogAnalyzer
            latest_release = max(
                (release for release in releases if release.get("name").startswith("SCLogAnalyzer")),
                key=lambda r: r.get("published_at", ""),
                default=None
            )

            if not latest_release:
                wx.MessageBox("No valid release named 'SCLogAnalyzer' found.", "Error", wx.OK | wx.ICON_ERROR)
                return

            latest_version = latest_release.get("tag_name", "").split('-')[0].lstrip('v')
            download_url = latest_release.get("assets", [{}])[0].get("browser_download_url")

            if not latest_version or not download_url:
                wx.MessageBox("Invalid release information.", "Error", wx.OK | wx.ICON_ERROR)
                return

            current_version = get_version().split('-')[0].lstrip('v')  # Remove 'v' prefix and extract version

            # Compare versions numerically
            def version_to_tuple(version):
                return tuple(map(int, version.split('.')))

            if version_to_tuple(latest_version) > version_to_tuple(current_version):
                if wx.MessageBox(f"A new version ({latest_version}) is available. Do you want to update?",
                                 "Update Available", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                    self.download_and_update(download_url)
        except Exception as e:
            wx.MessageBox(f"Error checking for updates: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def download_and_update(self, download_url):
        """Download the update and replace the running application."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file = os.path.join(temp_dir, "update.zip")
                with requests.get(download_url, stream=True) as response:
                    response.raise_for_status()
                    with open(temp_file, "wb") as f:
                        shutil.copyfileobj(response.raw, f)
    
                # Extract the update
                update_dir = os.path.join(temp_dir, "update")
                shutil.unpack_archive(temp_file, update_dir)
    
                # Move the updater script to a persistent location
                updated_exe = os.path.join(update_dir, APP_EXECUTABLE)
                persistent_updater_script = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "updater.py")
                shutil.copyfile(updated_exe, persistent_updater_script)
    
            # Launch the updater script
            subprocess.Popen([persistent_updater_script, os.path.dirname(os.path.abspath(sys.argv[0])), APP_EXECUTABLE])
            # Exit the current application
            self.Close()
            sys.exit(0)
        except Exception as e:
            wx.MessageBox(f"Error downloading or applying the update: {e}", "Error", wx.OK | wx.ICON_ERROR)

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
        for i in range(notebook.GetPageCount()):
            if notebook.GetPageText(i) == tab_title:
                return None  # Return None if the tab already exists

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

        return grid  # Return the grid for further updates

    def add_tab(self, url, tab_title, params=None, top_panel=None):
        """
        Add a new tab to the notebook with a grid and optional top panel.

        Args:
            url (str): The URL to fetch JSON data from.
            tab_title (str): The title of the new tab.
            params (dict, optional): A dictionary of parameters to pass to the request.
            top_panel (wx.Panel, optional): A panel to place above the grid (e.g., a form).
        """
        # Use _add_tab to create the base tab with a grid and refresh button
        grid = self._add_tab(self.notebook, tab_title, url, params)

        if grid and top_panel:
            # Add the top panel to the tab's sizer
            parent_panel = grid.GetParent()
            parent_sizer = parent_panel.GetSizer()
            parent_sizer.Insert(0, top_panel, 0, wx.EXPAND | wx.ALL, 5)
            parent_panel.Layout()

        # Trigger initial refresh if the grid was created
        if grid:
            self.execute_refresh_event(grid)

        return grid

    def execute_refresh_event(self, grid):
        refresh_button = grid.GetParent().FindWindowByLabel("Refresh")
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
        # Create the base tab first
        grid = self._add_tab(self.notebook, tab_title, url, params)

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
            submit_button.Bind(wx.EVT_BUTTON, lambda event: self.on_form_submit(event, url, grid, form_controls, params.get("sheet", "")))

        return grid

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
                wx.CallAfter(wx.MessageBox, "No URL configured for this tab.", 
                            "Error", wx.OK | wx.ICON_ERROR)
                return
                
            response = requests.get(url, params=params)
            if response.status_code != 200:
                wx.CallAfter(wx.MessageBox, 
                            f"Failed to fetch data. HTTP Status: {response.status_code}", 
                            "Error", wx.OK | wx.ICON_ERROR)
                return

            data = response.json()
            if not isinstance(data, list) or not data:
                wx.CallAfter(wx.MessageBox, 
                        "The response data is empty or not in the expected format.", 
                        "Error", wx.OK | wx.ICON_ERROR)
                return

            # Update the grid with data
            wx.CallAfter(self.update_sheets_grid, data, target_grid)
        except requests.RequestException as e:
            wx.CallAfter(wx.MessageBox, f"Network error: {e}", 
                    "Error", wx.OK | wx.ICON_ERROR)
        except json.JSONDecodeError:
            wx.CallAfter(wx.MessageBox, "Failed to decode JSON response.", 
                    "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Unexpected error: {e}", 
                    "Error", wx.OK | wx.ICON_ERROR)
        finally:
            # Clear loading state
            wx.CallAfter(self.set_grid_loading, target_grid, False)

    def update_dynamic_labels(self):
        """Update the username, shard, and version labels dynamically."""
        try:
            if self.event_handler:
                username = getattr(self.event_handler, "username", "Unknown")
                shard = getattr(self.event_handler, "current_shard", "Unknown")
                version = getattr(self.event_handler, "current_version", "Unknown")
            else:
                username, shard, version = "Unknown", "Unknown", "Unknown"

            self.username_label.SetLabel(f"Username: {username}")
            self.shard_label.SetLabel(f"Shard: {shard}")
            self.version_label.SetLabel(f"Version: {version}")
        except Exception as e:
            self.log_text.AppendText(f"Error updating labels: {e}\n")

    def on_shard_version_update(self, shard, version, username):
        """
        Handle updates to the shard, version, and username.

        Args:
            shard (str): The updated shard name.
            version (str): The updated version.
            username (str): The updated username.
        """
        try:
            self.update_dynamic_labels()  # Call update_dynamic_labels directly
        except Exception as e:
            self.log_text.AppendText(f"Error updating shard/version/username: {e}\n")

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

    def ensure_default_config(self):
        """Ensure the default configuration file exists."""
        app_path = get_application_path()
        config_path = os.path.join(app_path, CONFIG_FILE_NAME)
        
        if not os.path.exists(config_path):
            emit_default_config(config_path, in_gui=True)
            return True
        else:
            renew_config()
            return False
    def load_default_config(self):
        """Load default log file path and Google Sheets webhook from config."""
        app_path = get_application_path()
        config_path = os.path.join(app_path, CONFIG_FILE_NAME)
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as config_file:
                    config = json.load(config_file)
                    
                self.default_log_file_path = config.get('log_file_path', '')
                self.google_sheets_webhook = config.get('google_sheets_webhook', '')
                self.discord_webhook_url = config.get('discord_webhook_url', '')
                self.console_key = config.get('console_key', '')  # Load console key with default
           
                # Set checkbox defaults from config
                self.discord_check.Check(config.get('use_discord', True))  # Default to True
                self.googlesheet_check.Check(config.get('use_googlesheet', True))  # Default to True
                
            except Exception as e:
                self.log_text.AppendText(f"Error loading config: {e}\n")

    def validate_startup_settings(self):
        """Validate critical settings and show the config dialog if necessary."""
        missing_settings = []
        if not self.default_log_file_path:
            missing_settings.append("Log file path")
        else:
            if not os.path.exists(self.default_log_file_path):
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
    
    def start_monitoring(self):
        """Start log file monitoring."""
        if self.monitoring:  # Prevent starting monitoring if already active
            return
        self.log_text.Clear()
        self.monitoring = True  # Update monitoring state here
        
        # Use the default log file path from the configuration
        log_file = self.default_log_file_path
        if not log_file:
            wx.MessageBox("Log file path is not set in the configuration.", "Error", wx.OK | wx.ICON_ERROR)
            self.monitoring = False
            return

        process_all = True  # Always process the entire log
        use_discord = self.discord_check.IsChecked()
        use_googlesheet = self.googlesheet_check.IsChecked()
        
        # Run in a separate thread to keep UI responsive
        thread = threading.Thread(target=self.run_monitoring, args=(log_file, process_all, use_discord, use_googlesheet))
        thread.daemon = True
        thread.start()

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
                on_mode_change=self.on_mode_change
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
    
    def append_log_message(self, message):
        """Append a log message to the GUI log output area."""
        if self.log_text and self.log_text.IsShownOnScreen():
            wx.CallAfter(self.log_text.AppendText, message + "\n")

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
        app_path = get_application_path()
        config_path = os.path.join(app_path, CONFIG_FILE_NAME)
        if not hasattr(self, 'config_dialog') or not self.config_dialog:
            self.config_dialog = ConfigDialog(self, config_path)
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
        
        # Reload configuration after the dialog is closed
        self.load_default_config()
        self.validate_startup_settings()
        if self.monitoring:
            self.stop_monitoring()
            self.start_monitoring()
        self.update_google_sheets_tabs()  # Update tabs after reloading config


    def update_google_sheets_tabs(self):
        """Update Google Sheets tabs based on current configuration."""
        # Remove all existing Google Sheets tabs
        for i in range(self.notebook.GetPageCount() - 1, 0, -1):  # Skip the first tab (Main Log)
            self.notebook.DeletePage(i)
        
        # Only add Google Sheets tabs if the webhook URL is valid
        if self.google_sheets_webhook and self.googlesheet_check.IsChecked():
            self.add_tab(self.google_sheets_webhook, "Stats")
            self.add_tab(self.google_sheets_webhook, "SC Default", params={"sheet": "SC_Default", "username": lambda self: self.event_handler.username})
            self.add_tab(self.google_sheets_webhook, "SC Squadrons Battle", params={"sheet": "EA_SquadronBattle", "username": lambda self: self.event_handler.username})
            self.add_form_tab(self.google_sheets_webhook, "Materials",
                                params={"sheet": "Materials", "username": lambda self: self.event_handler.username},
                                form_fields={"Material": "text", "Qty": "number", "committed": "check"}) # Update labels dynamically


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

    def on_form_submit(self, event, url, grid, form_controls, sheet):
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
                self.execute_refresh_event(grid)
            else:
                wx.MessageBox("Failed to submit form. Please check the logs for details.", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error submitting form: {e}", "Error", wx.OK | wx.ICON_ERROR)

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

class TaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame

        # Set the icon using a stock icon
        icon = wx.ArtProvider.GetIcon(wx.ART_INFORMATION, wx.ART_OTHER, (16, 16))
        self.SetIcon(icon, TASKBAR_ICON_TOOLTIP)

        # Bind events
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_click)
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, self.on_right_click)

    def on_left_click(self, event):
        """Show or hide the main window on left-click"""
        if self.frame and self.frame.IsShown():
            self.frame.Hide()
        elif self.frame:
            self.frame.Show()
            self.frame.Raise()

    def on_right_click(self, event):
        """Show a context menu on right-click"""
        menu = wx.Menu()
        show_item = menu.Append(wx.ID_ANY, "Show Main Window")
        exit_item = menu.Append(wx.ID_EXIT, "Exit")

        self.Bind(wx.EVT_MENU, self.on_show, show_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)

        self.PopupMenu(menu)
        menu.Destroy()

    def on_show(self, event):
        """Show the main window"""
        if not self.frame.IsShown():
            self.frame.Show()
            self.frame.Raise()

    def on_exit(self, event):
        """Exit the application"""
        if self.frame:
            wx.CallAfter(self.frame.Close)

def cleanup_updater_script():
    updater_script = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "updater.py")
    if os.path.exists(updater_script):
        try:
            os.remove(updater_script)
            print("Cleaned up updater.py.")
        except Exception as e:
            print(f"Failed to clean up updater.py: {e}")

def main():
    if os.path.basename(sys.argv[0]) == "updater.py":
        update_application()    
    else:
        cleanup_updater_script()
    app = wx.App()
    frame = LogAnalyzerFrame()
    frame.Show()
    app.MainLoop()

def update_application():

    if len(sys.argv) < 3:
        print("Usage: updater.py <target_dir> <app_executable>")
        sys.exit(1)

    target_dir = sys.argv[1]
    app_executable = sys.argv[2]

    # Wait for the main application to exit
    time.sleep(5)

    # Replace the original executable with the updated one
    src_file = os.path.abspath(sys.argv[0])  # This script itself
    dest_file = os.path.join(target_dir, app_executable)

    try:
        shutil.move(src_file, dest_file)
        print(f"Replaced {dest_file} successfully.")
    except Exception as e:
        print(f"Failed to replace {dest_file}: {e}")
        sys.exit(1)

    # Restart the application
    try:
        os.execv(dest_file, [dest_file])
    except Exception as e:
        print(f"Failed to restart the application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()