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
from config_utils import emit_default_config, get_application_path
from gui_module import RedirectText, KeyValueGrid, ConfigDialog, ProcessDialog  # Import reusable components

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

        # Create main horizontal sizer to place notebook
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create notebook for log output and Google Sheets data
        notebook = wx.Notebook(panel)
        self.log_page = wx.Panel(notebook)
        notebook.AddPage(self.log_page, "Main Log")

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

        self.monitor_button = wx.Button(self.log_page, label=" Start Monitoring")
        self.monitor_button.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_EXECUTABLE_FILE, wx.ART_BUTTON, (16, 16)))
        self.monitor_button.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

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

        # Add a new page for Google Sheets data
        self.sheets_page = wx.Panel(notebook)
        notebook.AddPage(self.sheets_page, "Google Sheets")

        # Create a vertical sizer for the sheets page
        sheets_page_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add a refresh button
        self.refresh_button = wx.Button(self.sheets_page, label="Refresh")
        sheets_page_sizer.Add(self.refresh_button, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        # Add a grid to display the JSON data
        self.sheets_grid = wx.grid.Grid(self.sheets_page)
        self.sheets_grid.CreateGrid(0, 0)  # Start with an empty grid
        sheets_page_sizer.Add(self.sheets_grid, 1, wx.EXPAND | wx.ALL, 2)

        # Set the sizer for the sheets page
        self.sheets_page.SetSizer(sheets_page_sizer)

        # Add notebook to the main sizer
        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 2)

        # Set the sizer for the main panel
        panel.SetSizer(main_sizer)

        # Bind buttons
        self.process_log_button.Bind(wx.EVT_BUTTON, self.on_process_log)
        self.autoshard_button.Bind(wx.EVT_BUTTON, self.on_autoshard)
        self.monitor_button.Bind(wx.EVT_BUTTON, self.on_monitor)
        self.refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_sheets)

        # Add menu items
        menu_bar = wx.MenuBar()
        config_menu = wx.Menu()
        self.process_all_check = config_menu.AppendCheckItem(wx.ID_ANY, "Process Entire Log")
        self.discord_check = config_menu.AppendCheckItem(wx.ID_ANY, "Use Discord")
        self.googlesheet_check = config_menu.AppendCheckItem(wx.ID_ANY, "Use Google Sheets")
        config_menu.AppendSeparator()
        edit_config_item = config_menu.Append(wx.ID_ANY, "Edit Configuration")  # Add menu item for config dialog
        menu_bar.Append(config_menu, "Config")
        self.SetMenuBar(menu_bar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_toggle_check, self.process_all_check)
        self.Bind(wx.EVT_MENU, self.on_toggle_check, self.discord_check)
        self.Bind(wx.EVT_MENU, self.on_toggle_check, self.googlesheet_check)
        self.Bind(wx.EVT_MENU, self.on_edit_config, edit_config_item)  # Bind the new menu item

        # Status bar
        self.CreateStatusBar()
        self.SetStatusText("Ready")
        
        # Try to get the default log file path from config
        self.default_log_file_path = None
        self.google_sheets_webhook = None
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
            self.process_log_button.Enable(False)
            self.autoshard_button.Enable(True)  # Enable Auto Shard button
            self.SetStatusText("Monitoring active")
        else:
            self.monitor_button.SetLabel("Start Monitoring")
            self.process_log_button.Enable(True)
            self.autoshard_button.Enable(False)  # Disable Auto Shard button
            self.SetStatusText("Monitoring stopped")
        
    def ensure_default_config(self):
        """Ensure the default configuration file exists."""
        app_path = get_application_path()
        config_path = os.path.join(app_path, CONFIG_FILE_NAME)
        
        if not os.path.exists(config_path):
            emit_default_config(config_path, in_gui=True)

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

                if not os.path.isabs(self.default_log_file_path):
                    self.default_log_file_path = os.path.join(app_path, self.default_log_file_path)
                
                # Set checkbox defaults from config
                self.process_all_check.Check(config.get('process_all', True))
                self.discord_check.Check(config.get('use_discord', True))  # Default to True
                self.googlesheet_check.Check(config.get('use_googlesheet', True))  # Default to True
                
            except Exception as e:
                self.log_text.AppendText(f"Error loading config: {e}\n")
    
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
        
        # Run log analyzer in a separate thread to keep UI responsive
        process_all = self.process_all_check.IsChecked()
        use_discord = self.discord_check.IsChecked()
        use_googlesheet = self.googlesheet_check.IsChecked()
        autoshard = False  # Auto Shard is not used in this context
        
        thread = threading.Thread(target=self.run_process_log_thread, args=(log_file, process_all, use_discord, use_googlesheet, autoshard))
        thread.daemon = True
        thread.start()

    def run_process_log_thread(self, log_file, process_all, use_discord, use_googlesheet, autoshard):
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

        process_all = self.process_all_check.IsChecked()
        use_discord = self.discord_check.IsChecked()
        use_googlesheet = self.googlesheet_check.IsChecked()
        autoshard = False  # Auto Shard is not used in this context
        
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
        
        # Ensure the config dialog is within the main window boundaries
        main_window_position = self.GetPosition()
        main_window_size = self.GetSize()
        config_dialog_size = self.config_dialog.GetSize()
        
        new_x = max(main_window_position.x, min(main_window_position.x + main_window_size.x - config_dialog_size.x, self.config_dialog.GetPosition().x))
        new_y = max(main_window_position.y, min(main_window_position.y + main_window_size.y - config_dialog_size.y, self.config_dialog.GetPosition().y))
        
        self.config_dialog.SetPosition(wx.Point(new_x, new_y))
        
        self.config_dialog.Show()
        self.config_dialog.Raise()

    def on_refresh_sheets(self, event):
        """Refresh the Google Sheets data and update the grid."""
        try:
            # Fetch JSON data from Google Sheets
            json_data = self.fetch_google_sheets_data()

            # Update the grid with the new data
            self.update_sheets_grid(json_data)
        except Exception as e:
            wx.MessageBox(f"Failed to refresh Google Sheets data: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def fetch_google_sheets_data(self):
        """Fetch JSON data from Google Sheets using the webhook URL."""
        if not self.google_sheets_webhook:
            wx.MessageBox("Google Sheets webhook URL is not configured.", "Error", wx.OK | wx.ICON_ERROR)
            return []

        try:
            response = requests.get(self.google_sheets_webhook)
            if response.status_code != 200:
                wx.MessageBox(f"Failed to fetch data from Google Sheets. HTTP Status: {response.status_code}", "Error", wx.OK | wx.ICON_ERROR)
                return []

            data = response.json()
            if not isinstance(data, list) or not data:
                wx.MessageBox("The response data is empty or not in the expected format.", "Error", wx.OK | wx.ICON_ERROR)
                return []

            return data
        except requests.RequestException as e:
            wx.MessageBox(f"Error fetching data from Google Sheets: {e}", "Error", wx.OK | wx.ICON_ERROR)
            return []
        except json.JSONDecodeError:
            wx.MessageBox("Failed to decode JSON response from Google Sheets.", "Error", wx.OK | wx.ICON_ERROR)
            return []

    def update_sheets_grid(self, json_data):
        """Update the grid with the given JSON data."""
        if not json_data:
            self.sheets_grid.ClearGrid()
            return

        # Get the keys from the first dictionary as column headers
        headers = list(json_data[0].keys())

        # Resize the grid to fit the data
        self.sheets_grid.ClearGrid()
        if self.sheets_grid.GetNumberRows() > 0:
            self.sheets_grid.DeleteRows(0, self.sheets_grid.GetNumberRows())
        if self.sheets_grid.GetNumberCols() > 0:
            self.sheets_grid.DeleteCols(0, self.sheets_grid.GetNumberCols())
        self.sheets_grid.AppendCols(len(headers))
        self.sheets_grid.AppendRows(len(json_data))

        # Set column headers
        for col, header in enumerate(headers):
            self.sheets_grid.SetColLabelValue(col, header)

        # Populate the grid with data
        for row, entry in enumerate(json_data):
            for col, header in enumerate(headers):
                self.sheets_grid.SetCellValue(row, col, str(entry[header]))

        # Auto-size columns
        self.sheets_grid.AutoSizeColumns()

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