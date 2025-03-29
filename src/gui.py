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
import wx.lib.newevent  # For custom events

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

class RedirectText:
    """Class to redirect stdout to a text control"""
    def __init__(self, text_ctrl):
        self.text_ctrl = text_ctrl
        self.stdout = sys.stdout
        
    def write(self, string):
        """Write to both stdout and text control"""
        if self.stdout:
            self.stdout.write(string)
        wx.CallAfter(self.text_ctrl.AppendText, string)
        
    def flush(self):
        if self.stdout:
            self.stdout.flush()

class KeyValueGrid(wx.Panel):
    """A reusable grid for editing key-value pairs."""
    def __init__(self, parent, title, data, key_choices=None):
        super().__init__(parent)
        self.data = data
        self.key_choices = key_choices  # List of available keys for selection

        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add title
        title_label = wx.StaticText(self, label=title)
        main_sizer.Add(title_label, 0, wx.ALL, 5)

        # Create grid
        self.grid = wx.FlexGridSizer(cols=3, hgap=5, vgap=5)
        self.grid.AddGrowableCol(1, 1)  # Make value column expandable

        # Add headers
        self.grid.Add(wx.StaticText(self, label="Key"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(wx.StaticText(self, label="Value"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(wx.StaticText(self, label="Actions"), 0, wx.ALIGN_CENTER_VERTICAL)

        # Populate grid with data
        self.controls = []
        for key, value in self.data.items():
            self.add_row(key, value)

        main_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)

        # Add buttons at the bottom
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_button = wx.Button(self, label="+", size=(40, 40))
        add_button.SetFont(wx.Font(wx.FontInfo(12).Bold()))
        button_sizer.Add(add_button, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT)

        self.SetSizer(main_sizer)

        # Bind events
        add_button.Bind(wx.EVT_BUTTON, self.on_add)

    def add_row(self, key="", value=""):
        """Add a row to the grid."""
        if self.key_choices:
            key_ctrl = wx.Choice(self, choices=self.key_choices)
            if key in self.key_choices:
                key_ctrl.SetStringSelection(key)
        else:
            key_ctrl = wx.TextCtrl(self, value=key)

        # Use a multiline TextCtrl for the value field
        value_ctrl = wx.TextCtrl(self, value=value, style=wx.TE_MULTILINE)
        value_ctrl.SetMinSize((200, 50))  # Set a minimum size for better usability

        delete_button = wx.Button(self, label="-", size=(40, 40))
        delete_button.SetFont(wx.Font(wx.FontInfo(12).Bold()))
        move_up_button = wx.Button(self, label="↑", size=(40, 40))
        move_up_button.SetFont(wx.Font(wx.FontInfo(12).Bold()))
        move_down_button = wx.Button(self, label="↓", size=(40, 40))
        move_down_button.SetFont(wx.Font(wx.FontInfo(12).Bold()))

        self.grid.Add(key_ctrl, 0, wx.EXPAND)
        self.grid.Add(value_ctrl, 1, wx.EXPAND)
        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        action_sizer.Add(delete_button, 0, wx.ALL, 2)
        action_sizer.Add(move_up_button, 0, wx.ALL, 2)
        action_sizer.Add(move_down_button, 0, wx.ALL, 2)
        self.grid.Add(action_sizer, 0, wx.ALIGN_CENTER)

        self.controls.append((key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button))

        # Bind button events
        delete_button.Bind(wx.EVT_BUTTON, lambda event: self.on_delete(key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button))
        move_up_button.Bind(wx.EVT_BUTTON, lambda event: self.on_move_up(key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button))
        move_down_button.Bind(wx.EVT_BUTTON, lambda event: self.on_move_down(key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button))

        self.Layout()

    def on_add(self, event):
        """Handle add button click."""
        # Add a new row with empty inputs for key and value
        self.add_row("", "")

    def on_delete(self, key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button):
        """Handle delete button click."""
        wx.CallAfter(self._delete_row, key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button)

    def _delete_row(self, key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button):
        """Perform the actual deletion of a row."""
        key_ctrl.Destroy()
        value_ctrl.Destroy()
        delete_button.Destroy()
        move_up_button.Destroy()
        move_down_button.Destroy()
        self.controls.remove((key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button))
        self.refresh_grid()

    def on_move_up(self, key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button):
        """Move the row up."""
        wx.CallAfter(self._move_row, key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button, -1)

    def on_move_down(self, key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button):
        """Move the row down."""
        wx.CallAfter(self._move_row, key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button, 1)

    def _move_row(self, key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button, direction):
        """Perform the actual row movement."""
        index = self.controls.index((key_ctrl, value_ctrl, delete_button, move_up_button, move_down_button))
        new_index = index + direction
        if 0 <= new_index < len(self.controls):
            # Swap the rows
            self.controls[index], self.controls[new_index] = self.controls[new_index], self.controls[index]
            self.refresh_grid()

    def refresh_grid(self):
        """Refresh the grid to reflect the updated order."""
        wx.CallAfter(self._refresh_grid)

    def _refresh_grid(self):
        """Perform the actual grid refresh."""
        data=self.get_data()  # Save the data before clearing the grid

        self.grid.Clear(True)  # Clear the grid layout
        self.controls = []
        # Re-add headers
        self.grid.Add(wx.StaticText(self, label="Key"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(wx.StaticText(self, label="Value"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(wx.StaticText(self, label="Actions"), 0, wx.ALIGN_CENTER_VERTICAL)

        # Rebuild the controls list and recreate rows
        new_controls = []
        for key,value in data.items():
            self.add_row(key, value)

        self.Layout()

    def get_data(self):
        """Retrieve the data from the grid."""
        return {
            (key_ctrl.GetStringSelection() if isinstance(key_ctrl, wx.Choice) else key_ctrl.GetValue()): value_ctrl.GetValue()
            for key_ctrl, value_ctrl, _, _, _ in self.controls
        }

class ConfigDialog(wx.Frame):
    """Resizable, non-modal dialog for editing configuration options."""
    def __init__(self, parent, config_path):
        super().__init__(parent, title="Edit Configuration", size=(600, 400))
        self.config_path = config_path
        self.config_data = {}

        # Load the configuration file
        self.load_config()

        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create notebook
        notebook = wx.Notebook(self)

        # Add tabs using the helper method
        self.general_controls = {}
        self.add_general_tab(notebook, "General Config", self.config_data)
        self.regex_patterns_grid = self.add_tab(notebook, "Regex Patterns", "regex_patterns")
        regex_keys = list(self.config_data.get("regex_patterns", {}).keys())
        regex_keys.append("mode_change")  # Add the fixed option
        self.messages_grid = self.add_tab(notebook, "Messages", "messages", regex_keys)
        self.discord_grid = self.add_tab(notebook, "Discord Messages", "discord", regex_keys)
        self.sheets_mapping_grid = self.add_tab(notebook, "Google Sheets Mapping", "google_sheets_mapping", regex_keys)

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)

        # Add startup configuration section
        startup_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.startup_label = wx.StaticText(self, label="Startup: Checking...")
        self.startup_button = wx.Button(self, label="Toggle Startup")
        startup_sizer.Add(self.startup_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        startup_sizer.Add(self.startup_button, 0, wx.ALL, 5)
        main_sizer.Add(startup_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Add Accept, Save, and Cancel buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        accept_button = wx.Button(self, label="Accept")
        save_button = wx.Button(self, label="Save")
        cancel_button = wx.Button(self, label="Cancel")
        button_sizer.Add(accept_button, 0, wx.ALL, 5)
        button_sizer.Add(save_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.SetSizer(main_sizer)

        # Bind events
        accept_button.Bind(wx.EVT_BUTTON, self.on_accept)
        save_button.Bind(wx.EVT_BUTTON, self.on_save)
        cancel_button.Bind(wx.EVT_BUTTON, self.on_close)
        self.startup_button.Bind(wx.EVT_BUTTON, self.on_toggle_startup)

        # Check startup status
        self.check_startup_status()

    def check_startup_status(self):
        """Check if the application is set to run on Windows startup."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, STARTUP_APP_NAME)
            winreg.CloseKey(key)
            if value:
                self.startup_label.SetLabel("Startup: Enabled")
                self.startup_button.SetLabel("Disable Startup")
        except FileNotFoundError:
            self.startup_label.SetLabel("Startup: Disabled")
            self.startup_button.SetLabel("Enable Startup")
        except Exception as e:
            self.startup_label.SetLabel(f"Startup: Error ({e})")
            self.startup_button.Disable()

    def on_toggle_startup(self, event):
        """Toggle the startup entry in the Windows registry."""
        try:
            app_path = sys.executable  # Path to the Python executable or bundled EXE
            startup_command = f'"{app_path}" {STARTUP_COMMAND_FLAG}'

            if self.startup_button.GetLabel() == "Enable Startup":
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, STARTUP_APP_NAME, 0, winreg.REG_SZ, startup_command)
                winreg.CloseKey(key)
                wx.MessageBox("Startup enabled successfully.", "Info", wx.OK | wx.ICON_INFORMATION)
            else:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, STARTUP_APP_NAME)
                winreg.CloseKey(key)
                wx.MessageBox("Startup disabled successfully.", "Info", wx.OK | wx.ICON_INFORMATION)

            # Refresh the startup status
            self.check_startup_status()
        except FileNotFoundError:
            wx.MessageBox("Startup entry not found.", "Info", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"Failed to toggle startup: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def add_tab(self, notebook, title, config_key, key_choices=None):
        """Helper method to add a tab with a KeyValueGrid."""
        panel = wx.ScrolledWindow(notebook)
        panel.SetScrollRate(5, 5)
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = KeyValueGrid(panel, title, self.config_data.get(config_key, {}), key_choices)
        sizer.Add(grid, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)
        notebook.AddPage(panel, title)
        return grid

    def add_general_tab(self, notebook, title, config_data):
        """Helper method to add the general configuration tab."""
        panel = wx.Panel(notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        for key, value in config_data.items():
            if isinstance(value, (str, int, float, bool)):  # Only first-level simple values
                label = wx.StaticText(panel, label=key)
                if isinstance(value, bool):
                    control = wx.CheckBox(panel)
                    control.SetValue(value)
                else:
                    control = wx.TextCtrl(panel, value=str(value))
                self.general_controls[key] = control
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                row_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                row_sizer.Add(control, 1, wx.ALL | wx.EXPAND, 5)

                # Add a "Browse" button for the "log_file_path" key
                if key == "log_file_path":
                    browse_button = wx.Button(panel, label="Browse...")
                    row_sizer.Add(browse_button, 0, wx.ALL, 5)
                    browse_button.Bind(wx.EVT_BUTTON, lambda event: self.on_browse_log_file(control))

                sizer.Add(row_sizer, 0, wx.EXPAND)
        panel.SetSizer(sizer)
        notebook.AddPage(panel, title)

    def on_browse_log_file(self, control):
        """Handle the Browse button click for log_file_path."""
        with wx.FileDialog(self, "Select log file", wildcard=LOG_FILE_WILDCARD,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            control.SetValue(file_dialog.GetPath())

    def load_config(self):
        """Load configuration from the JSON file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as config_file:
                self.config_data = json.load(config_file)

    def save_config(self):
        """Save configuration to the JSON file."""
        # Save general config values
        for key, control in self.general_controls.items():
            if isinstance(control, wx.CheckBox):
                self.config_data[key] = control.GetValue()
            else:
                value = control.GetValue()
                try:
                    # Try to convert to int or float if applicable
                    if value.isdigit():
                        value = int(value)
                    else:
                        value = float(value)
                except ValueError:
                    pass
                self.config_data[key] = value

        # Save grid data
        self.config_data["regex_patterns"] = self.regex_patterns_grid.get_data()
        self.config_data["messages"] = self.messages_grid.get_data()
        self.config_data["discord"] = self.discord_grid.get_data()
        self.config_data["google_sheets_mapping"] = self.sheets_mapping_grid.get_data()

    def save_to_file(self):
        """Save the current configuration to the JSON file."""
        with open(self.config_path, 'w', encoding='utf-8') as config_file:
            json.dump(self.config_data, config_file, indent=4)

    def on_accept(self, event):
        """Handle the Accept button click."""
        self.save_config()
        self.Destroy()

    def on_save(self, event):
        """Handle the Save button click."""
        self.save_config()
        self.save_to_file()
        wx.MessageBox("Configuration saved successfully.", "Info", wx.OK | wx.ICON_INFORMATION)
        self.Destroy()
        

    def on_close(self, event):
        """Handle the Cancel button click."""
        self.Destroy()

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
        
        # Create log file selection controls
        file_sizer = wx.BoxSizer(wx.HORIZONTAL)
        file_label = wx.StaticText(panel, label="Log File:")
        self.file_path = wx.TextCtrl(panel, size=(400, -1))
        browse_button = wx.Button(panel, label="Browse...")
        
        file_sizer.Add(file_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        file_sizer.Add(self.file_path, 1, wx.ALL | wx.EXPAND, 5)
        file_sizer.Add(browse_button, 0, wx.ALL, 5)
        
        # Create option checkboxes
        options_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.process_all_check = wx.CheckBox(panel, label="Process Entire Log")
        self.discord_check = wx.CheckBox(panel, label="Use Discord")
        self.googlesheet_check = wx.CheckBox(panel, label="Use Google Sheets")
        self.autoshard_check = wx.CheckBox(panel, label="Auto Shard")  # Add Auto Shard checkbox

        options_sizer.Add(self.process_all_check, 0, wx.ALL, 5)
        options_sizer.Add(self.discord_check, 0, wx.ALL, 5)
        options_sizer.Add(self.googlesheet_check, 0, wx.ALL, 5)
        options_sizer.Add(self.autoshard_check, 0, wx.ALL, 5)  # Add to options sizer
        
        # Create action buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.process_button = wx.Button(panel, label="Process Log Once")
        self.monitor_button = wx.Button(panel, label="Start Monitoring")
        self.autoshard_button = wx.Button(panel, label="Auto Shard")  # Add Auto Shard button
        self.autoshard_button.Enable(False)  # Initially disable the button
        
        button_sizer.Add(self.process_button, 0, wx.ALL, 5)
        button_sizer.Add(self.monitor_button, 0, wx.ALL, 5)
        button_sizer.Add(self.autoshard_button, 0, wx.ALL, 5)  # Add to button sizer
        
        # Create log output area
        log_label = wx.StaticText(panel, label="Log Output:")
        self.log_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)

        # Set font to a monospaced font for better log readability
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.log_text.SetFont(font)

        # Set black background and green text
        self.log_text.SetBackgroundColour(wx.Colour(0, 0, 0))  # Black background
        self.log_text.SetForegroundColour(wx.Colour(0, 255, 0))  # Green text
        
        # Add all controls to main sizer
        main_sizer.Add(file_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(options_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(log_label, 0, wx.ALL, 5)
        main_sizer.Add(self.log_text, 1, wx.EXPAND | wx.ALL, 5)
        
        # Set the main sizer
        panel.SetSizer(main_sizer)
        
        # Status bar
        self.CreateStatusBar()
        self.SetStatusText("Ready")
        
        # Bind events
        browse_button.Bind(wx.EVT_BUTTON, self.on_browse)
        self.process_button.Bind(wx.EVT_BUTTON, self.on_process)
        self.monitor_button.Bind(wx.EVT_BUTTON, self.on_monitor)
        self.autoshard_button.Bind(wx.EVT_BUTTON, self.on_autoshard)  # Bind Auto Shard button event
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Add a menu bar with a Config menu
        menu_bar = wx.MenuBar()
        config_menu = wx.Menu()
        edit_config_item = config_menu.Append(wx.ID_ANY, "Edit Config...")
        menu_bar.Append(config_menu, "Config")
        self.SetMenuBar(menu_bar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_edit_config, edit_config_item)
        
        # Try to get the default log file path from config
        self.load_default_config()
        
        # Set up stdout redirection
        sys.stdout = RedirectText(self.log_text)

        # Create taskbar icon
        self.taskbar_icon = TaskBarIcon(self)

        # Check if the app is started with Windows
        if STARTUP_COMMAND_FLAG in sys.argv:
            self.Hide()
        # Start monitoring by default when GUI is launched
        wx.CallAfter(self.start_monitoring)
        wx.CallAfter(self.update_monitoring_buttons, True)

        self.save_timer = wx.Timer(self)  # Timer to delay saving window info
        self.Bind(wx.EVT_TIMER, self.on_save_timer, self.save_timer)
        self.Bind(wx.EVT_MOVE, self.on_window_move_or_resize)
        self.Bind(wx.EVT_SIZE, self.on_window_move_or_resize)

        self.restore_window_info()  # Restore window position, size, and state from the registry

        # Bind close event to save window position
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def update_monitoring_buttons(self, started):
        """
        Update the state of the monitoring and process buttons.

        Args:
            started (bool): True if monitoring has started, False otherwise.
        """
        if self.monitoring:  # Check the actual monitoring state
            self.monitor_button.SetLabel("Stop Monitoring")
            self.process_button.Enable(False)
            self.autoshard_button.Enable(True)  # Enable Auto Shard button
            self.SetStatusText("Monitoring active")
        else:
            self.monitor_button.SetLabel("Start Monitoring")
            self.process_button.Enable(True)
            self.autoshard_button.Enable(False)  # Disable Auto Shard button
            self.SetStatusText("Monitoring stopped")
        
    def ensure_default_config(self):
        """Ensure the default configuration file exists."""
        app_path = log_analyzer.get_application_path()
        config_path = os.path.join(app_path, CONFIG_FILE_NAME)
        
        if not os.path.exists(config_path):
            log_analyzer.emit_default_config(config_path, in_gui=True)

    def load_default_config(self):
        """Load default log file path from config"""
        app_path = log_analyzer.get_application_path()
        config_path = os.path.join(app_path, CONFIG_FILE_NAME)
        
        if os.path.exists(config_path):
            try:
                import json
                with open(config_path, 'r', encoding='utf-8') as config_file:
                    config = json.load(config_file)
                    
                log_file_path = config.get('log_file_path', '')
                if not os.path.isabs(log_file_path):
                    log_file_path = os.path.join(app_path, log_file_path)
                
                self.file_path.SetValue(log_file_path)
                
                # Set checkbox defaults from config
                self.process_all_check.SetValue(config.get('process_all', True))
                self.discord_check.SetValue(config.get('use_discord', True))  # Default to True
                self.googlesheet_check.SetValue(config.get('use_googlesheet', True))  # Default to True
                
            except Exception as e:
                self.log_text.AppendText(f"Error loading config: {e}\n")
    
    def on_browse(self, event):
        """Handle browse button click event."""
        if self.monitoring:
            self.stop_monitoring()
            self.update_monitoring_buttons(started=False)  # Use the new method
            self.monitoring = False
        
        with wx.FileDialog(self, "Select log file", wildcard=LOG_FILE_WILDCARD,
                          style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            self.file_path.SetValue(file_dialog.GetPath())
    
    def on_process(self, event):
        """Handle process once button click event"""
        if not self or not self.IsShown():
            return  # Prevent actions if the frame is destroyed
        if self.monitoring:
            wx.MessageBox("Stop monitoring first before processing log", "Cannot Process", wx.OK | wx.ICON_INFORMATION)
            return
        
        self.log_text.Clear()
        self.SetStatusText("Processing log file...")
        
        # Disable buttons during processing
        self.process_button.Enable(False)
        self.monitor_button.Enable(False)
        
        # Run log analyzer in a separate thread to keep UI responsive
        log_file = self.file_path.GetValue()
        process_all = self.process_all_check.GetValue()
        use_discord = self.discord_check.GetValue()
        use_googlesheet = self.googlesheet_check.GetValue()
        autoshard = self.autoshard_check.GetValue()  # Get Auto Shard value
        
        thread = threading.Thread(target=self.run_process_log, args=(log_file, process_all, use_discord, use_googlesheet, autoshard))
        thread.daemon = True
        thread.start()
    
    def run_process_log(self, log_file, process_all, use_discord, use_googlesheet, autoshard):
        """Run log analysis in thread"""
        try:
            # Call main with process_once=True
            log_analyzer.main(
                process_all=process_all,
                use_discord=use_discord,
                process_once=True,
                use_googlesheet=use_googlesheet,
                log_file_path=log_file,
                autoshard=autoshard  # Pass Auto Shard to main
            )
            wx.CallAfter(self.SetStatusText, "Processing completed")
        except Exception as e:
            wx.CallAfter(self.log_text.AppendText, f"Error processing log: {e}\n")
            wx.CallAfter(self.SetStatusText, "Error during processing")
        finally:
            wx.CallAfter(self.process_button.Enable, True)
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
        
        log_file = self.file_path.GetValue()
        process_all = self.process_all_check.GetValue()
        use_discord = self.discord_check.GetValue()
        use_googlesheet = self.googlesheet_check.GetValue()
        autoshard = self.autoshard_check.GetValue()  # Get Auto Shard value
        
        # Run in a separate thread to keep UI responsive
        thread = threading.Thread(target=self.run_monitoring, args=(log_file, process_all, use_discord, use_googlesheet, autoshard))
        thread.daemon = True
        thread.start()

    def run_monitoring(self, log_file, process_all, use_discord, use_googlesheet, autoshard):
        """Run monitoring in thread."""
        try:
            # Call main without process_once
            result = log_analyzer.main(
                process_all=process_all,
                use_discord=use_discord,
                process_once=False,
                use_googlesheet=use_googlesheet,
                log_file_path=log_file,
                autoshard=autoshard  # Pass Auto Shard to main
            )

            if result:
                self.event_handler, self.observer = result
                # Trigger startup actions explicitly after monitoring starts
                if self.event_handler:
                    self.event_handler.send_startup_keystrokes()
        except Exception as e:
            wx.CallAfter(self.log_text.AppendText, f"Error starting monitoring: {e}\n")
            wx.CallAfter(self.update_monitoring_buttons, False)  # Use the new method
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

    def on_edit_config(self, event):
        """Open the configuration dialog."""
        app_path = log_analyzer.get_application_path()
        config_path = os.path.join(app_path, CONFIG_FILE_NAME)
        if not hasattr(self, 'config_dialog') or not self.config_dialog:
            self.config_dialog = ConfigDialog(self, config_path)
        
        # Ensure the config dialog is within the main window boundaries
        main_window_position = self.GetPosition()
        main_window_size = self.GetSize()
        config_dialog_size = self.config_dialog.GetSize()
        
        new_x = max(main_window_position.x, min(main_window_position.x + main_window_size.x - config_dialog_size.x, self.config_dialog.GetPosition().x))
        new_y = max(main_window_position.y, min(main_window_position.y + main_window_size.y - config_dialog_size.y, self.config_dialog.GetPosition().y))
        
        self.config_dialog.SetPosition(wx.Point(new_x, new_y))
        
        self.config_dialog.Show()
        self.config_dialog.Raise()

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
        if self.event_handler:
            try:
                self.event_handler.send_keystrokes_to_sc()  # Call the method to send keystrokes
                self.log_text.AppendText("Auto Shard keystrokes sent.\n")
            except Exception as e:
                self.log_text.AppendText(f"Error sending Auto Shard keystrokes: {e}\n")
        else:
            self.log_text.AppendText("No event handler available for Auto Shard.\n")
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

def main():
    app = wx.App()
    frame = LogAnalyzerFrame()
    frame.Show()
    app.MainLoop()

if __name__ == "__main__":
    main()