import wx
import os
import json
import win32gui
from pynput.keyboard import Controller, Key
from PIL import Image
import mss
import time
import win32con  # Required for window constants like SW_RESTORE
import win32process  # Required for process-related functions
import win32api  # Required for sending keystrokes
import psutil  # Required for process management
import winreg
import wx.adv  # Import wx.adv for taskbar icon support
import sys

from version import get_version  # Using absolute import for module in parent directory
from .config_utils import get_application_path  # Direct import from same directory
from .message_bus import message_bus, MessageLevel  # Direct import from same directory

STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

class KeyValueGrid(wx.Panel):
    """A reusable grid for editing key-value pairs."""
    def __init__(self, parent, title, data, key_choices=None):
        super().__init__(parent)
        self.data = data
        self.key_choices = key_choices

        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add title
        title_label = wx.StaticText(self, label=title)
        main_sizer.Add(title_label, 0, wx.ALL, 5)

        # Create grid
        self.grid = wx.FlexGridSizer(cols=3, hgap=5, vgap=5)
        self.grid.AddGrowableCol(1, 1)

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

        # Convert list values to a comma-separated string
        value_str = ", ".join(value) if isinstance(value, list) else value
        value_ctrl = wx.TextCtrl(self, value=value_str, style=wx.TE_MULTILINE)
        value_ctrl.SetMinSize((200, 50))

        delete_button = wx.Button(self, label="-", size=(40, 40))
        delete_button.SetFont(wx.Font(wx.FontInfo(12).Bold()))

        self.grid.Add(key_ctrl, 0, wx.EXPAND)
        self.grid.Add(value_ctrl, 1, wx.EXPAND)
        self.grid.Add(delete_button, 0, wx.ALIGN_CENTER)

        self.controls.append((key_ctrl, value_ctrl, delete_button))

        # Bind button events
        delete_button.Bind(wx.EVT_BUTTON, lambda event: self.on_delete(key_ctrl, value_ctrl, delete_button))

        self.Layout()

    def on_add(self, event):
        """Handle add button click."""
        self.add_row("", "")

    def on_delete(self, key_ctrl, value_ctrl, delete_button):
        """Handle delete button click."""
        key_ctrl.Destroy()
        value_ctrl.Destroy()
        delete_button.Destroy()
        self.controls.remove((key_ctrl, value_ctrl, delete_button))
        self.Layout()

    def get_data(self):
        """Retrieve the data from the grid."""
        return {
            (key_ctrl.GetStringSelection() if isinstance(key_ctrl, wx.Choice) else key_ctrl.GetValue()): 
            # Convert comma-separated strings back to lists
            value_ctrl.GetValue()
            for key_ctrl, value_ctrl, _ in self.controls
        }


class ConfigDialog(wx.Frame):
    """Resizable, non-modal dialog for editing configuration options."""
    def __init__(self, parent, config_manager):
        super().__init__(parent, title="Edit Configuration", size=(600, 400))
        self.config_manager = config_manager
        self.app_name = "SCLogAnalyzer"
        self.app_path = f'"{os.path.join(get_application_path(), "SCLogAnalyzer.exe")}" --start-hidden'
        self.config_saved = False  # Track whether config was saved
        
        # Load the configuration data from the manager
        self.config_data = self.config_manager.get_all()

        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create notebook
        notebook = wx.Notebook(self)

        # Add tabs using the helper method
        self.general_controls = {}
        self.add_general_tab(notebook, "General Config", self.config_data)
        self.regex_patterns_grid = self.add_tab(notebook, "Regex Patterns", "regex_patterns")
        regex_keys = list(self.config_data.get("regex_patterns", {}).keys())
        regex_keys.append("mode_change")  # Add fixed options
        regex_keys.append("startup")
        regex_keys.append("shard_info")
        regex_keys.append("vip")
        self.messages_grid = self.add_tab(notebook, "Messages", "messages", regex_keys)
        self.discord_grid = self.add_tab(notebook, "Discord Messages", "discord", regex_keys)
        self.colors_grid = self.add_colors_tab(notebook, "Colors", self.config_data.get("colors", {}))  # Add colors tab
        self.tabs_grid = self.add_tab(notebook, "Dynamic Tabs", "tabs")  # Add tabs configuration grid
        self.add_vips_tab(notebook, "VIP Players", self.config_data.get("important_players", ""))

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)

        # Add Accept, Save, Cancel, and Startup buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        accept_button = wx.Button(self, label="Accept")
        cancel_button = wx.Button(self, label="Cancel")
        self.startup_button = wx.Button(self, label="")
        self.update_startup_button_label()
        button_sizer.Add(self.startup_button, 0, wx.ALL, 5)
        button_sizer.Add(accept_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.SetSizer(main_sizer)

        # Bind events
        accept_button.Bind(wx.EVT_BUTTON, self.on_accept)
        cancel_button.Bind(wx.EVT_BUTTON, self.on_close)
        self.startup_button.Bind(wx.EVT_BUTTON, self.on_toggle_startup)

    def update_startup_button_label(self):
        """Update the startup button label based on the current startup status."""
        if is_app_in_startup(self.app_name):
            self.startup_button.SetLabel("Remove from Startup")
        else:
            self.startup_button.SetLabel("Add to Startup")

    def on_toggle_startup(self, event):
        """Toggle adding/removing the app from Windows startup."""
        if is_app_in_startup(self.app_name):
            remove_app_from_startup(self.app_name)
            message = f"{self.app_name} removed from Windows startup."
            wx.MessageBox(message, "Info", wx.OK | wx.ICON_INFORMATION)
            message_bus.publish(content=message, level=MessageLevel.INFO)
        else:
            add_app_to_startup(self.app_name, self.app_path)
            message = f"{self.app_name} added to Windows startup with '--start-hidden' parameter."
            wx.MessageBox(message, "Info", wx.OK | wx.ICON_INFORMATION)
            message_bus.publish(content=message, level=MessageLevel.INFO)
        self.update_startup_button_label()

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

    def add_colors_tab(self, notebook, title, colors_data):
        """Add a tab for managing color settings."""
        panel = wx.ScrolledWindow(notebook)
        panel.SetScrollRate(5, 5)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Add a KeyValueGrid for colors
        self.colors_grid = KeyValueGrid(panel, title, colors_data)
        sizer.Add(self.colors_grid, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        notebook.AddPage(panel, title)
        return self.colors_grid

    def add_general_tab(self, notebook, title, config_data):
        panel = wx.Panel(notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Track which keys have been handled with special controls
        special_keys_handled = set()
        
        # Add data source selection dropdown first
        # This will replace the separate use_googlesheet and use_supabase boolean flags
        datasource_label = wx.StaticText(panel, label="Data Source")
        datasource_choices = ["googlesheets", "supabase"]
        
        # Get current datasource value or default to googlesheets
        current_datasource = config_data.get("datasource", "googlesheets")
        
        datasource_control = wx.Choice(panel, choices=datasource_choices)
        # Set the selected choice
        if current_datasource in datasource_choices:
            datasource_control.SetStringSelection(current_datasource)
        else:
            datasource_control.SetSelection(0)  # Default to googlesheets
            
        # Store the control for later retrieval
        self.general_controls["datasource"] = datasource_control
        
        # Create a row for the datasource dropdown
        row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        row_sizer.Add(datasource_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        row_sizer.Add(datasource_control, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(row_sizer, 0, wx.EXPAND)
        
        # Mark these keys as handled since we're replacing them with the datasource dropdown
        special_keys_handled.add("use_googlesheet")
        special_keys_handled.add("use_supabase")
        special_keys_handled.add("datasource")
        special_keys_handled.add("important_players")  # Username will be handled separately
        
        # Process other configuration keys
        for key, value in config_data.items():
            # Skip keys we've already handled with special controls
            if key in special_keys_handled or key == "username":
                continue
                
            if isinstance(value, (str, int, float, bool)):  # Only first-level simple values
                label = wx.StaticText(panel, label=key)
                control = wx.CheckBox(panel) if isinstance(value, bool) else wx.TextCtrl(panel, value=str(value))
                if isinstance(value, bool):
                    control.SetValue(value)
                self.general_controls[key] = control
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                row_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                row_sizer.Add(control, 1, wx.ALL | wx.EXPAND, 5)
                if key == "log_file_path":
                    browse_button = wx.Button(panel, label="Browse...")
                    browse_button.Bind(wx.EVT_BUTTON, lambda event, tc=control: self.on_browse_log_file(event, tc))
                    row_sizer.Add(browse_button, 0, wx.ALL, 5)
                sizer.Add(row_sizer, 0, wx.EXPAND)

        panel.SetSizer(sizer)
        notebook.AddPage(panel, title)

    def on_browse_log_file(self, event, text_ctrl):
        """Handle browse button click for log file path."""
        with wx.FileDialog(self, "Select log file", wildcard="Log files (*.log)|*.log|All files (*.*)|*.*",
                        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            text_ctrl.SetValue(file_dialog.GetPath())

    def save_config(self):
        """Save configuration using the ConfigManager."""
        # Store original config before making changes
        old_config = self.config_manager.get_all().copy()
        # Save general config values 
        for key, control in self.general_controls.items():
            value = control.GetStringSelection() if isinstance(control, wx.Choice) else control.GetValue()
            self.config_manager.set(key, value)

        # Save regex patterns data
        regex_patterns_data = self.regex_patterns_grid.get_data()
        self.config_manager.set("regex_patterns", regex_patterns_data)
        
        # Save messages data
        messages_data = self.messages_grid.get_data()
        self.config_manager.set("messages", messages_data)
        
        # Save discord data
        discord_data = self.discord_grid.get_data()
        self.config_manager.set("discord", discord_data)
        
        # Save colors data
        colors_data = self.colors_grid.get_data()
        self.config_manager.set("colors", colors_data)
        
        # Save tabs data
        tabs_data = self.tabs_grid.get_data()
        self.config_manager.set("tabs", tabs_data)
        
        # Save VIP string (from textarea)
        self.config_manager.set("important_players", self.get_vip_string())
        
        # Save to file
        self.config_manager.save_config()
        
        # Get new config after changes
        new_config = self.config_manager.get_all()
        
        # Emit a single event with both old and new configurations
        message_bus.emit("config.saved", 
                        old_config=old_config, 
                        new_config=new_config, 
                        config_manager=self.config_manager)
        
        # Check for specific changes that need immediate handling
        old_datasource = old_config.get('datasource', 'googlesheets')
        new_datasource = new_config.get('datasource', 'googlesheets')
        
        if old_datasource != new_datasource:
            # Re-use existing datasource change handling
            message_bus.emit("datasource_changed", old_datasource, new_datasource)

    def on_accept(self, event):
        """Handle the Accept button click."""
        self.save_config()
        self.config_saved = True  # Mark that config was saved
        self.Destroy()

    def on_close(self, event):
        """Handle the Cancel button click."""
        self.config_saved = False  # Mark that config was not saved
        self.Destroy()

    def add_vips_tab(self, notebook, title, vips_string):
        """Add the VIPs tab to the config dialog notebook (multiline TextCtrl, comma or LF separated input, always shown as LF-separated)."""
        panel = wx.ScrolledWindow(notebook)
        panel.SetScrollRate(5, 5)
        sizer = wx.BoxSizer(wx.VERTICAL)
        vip_doc = wx.StaticText(
            panel,
            label="List of VIP player names or regex patterns, one per line.\nEach entry can be a plain string or a regex pattern (Python re).\nInvalid patterns are ignored.\nExample: ^Admiral.*$ or player123"
        )
        sizer.Add(vip_doc, 0, wx.ALL | wx.EXPAND, 5)
        # Normalize input: split by comma or LF, strip, join by LF for display
        if vips_string:
            items = [x.strip() for part in vips_string.split('\n') for x in part.split(',')]
            items = [x for x in items if x]
            vips_text = '\n'.join(items)
        else:
            vips_text = ""
        self.vip_text_ctrl = wx.TextCtrl(
            panel, value=vips_text, style=wx.TE_MULTILINE | wx.TE_DONTWRAP
        )
        sizer.Add(self.vip_text_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        panel.SetSizer(sizer)
        notebook.AddPage(panel, title)
        return panel

    def get_vip_string(self):
        """Return VIPs as a single string from the TextCtrl (comma-separated, normalized)."""
        # Normalize: split by LF, strip, join by comma, remove empty
        raw = self.vip_text_ctrl.GetValue()
        items = [x.strip() for x in raw.split('\n') if x.strip()]
        return ','.join(items)

class ProcessDialog(wx.Dialog):
    """Dialog for selecting a file and processing it."""
    def __init__(self, parent):
        super().__init__(parent, title="Process Log File", size=(500, 250))

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title_label = wx.StaticText(panel, label="Select a Log File to Process")
        title_label.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        main_sizer.Add(title_label, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # File path selection
        file_sizer = wx.BoxSizer(wx.HORIZONTAL)
        file_label = wx.StaticText(panel, label="Log File:")
        self.file_path = wx.TextCtrl(panel, size=(300, -1))
        browse_button = wx.Button(panel, label="Browse...")
        file_sizer.Add(file_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        file_sizer.Add(self.file_path, 1, wx.ALL | wx.EXPAND, 5)
        file_sizer.Add(browse_button, 0, wx.ALL, 5)
        main_sizer.Add(file_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Accept and Cancel buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        accept_button = wx.Button(panel, label="Process")
        cancel_button = wx.Button(panel, label="Cancel")
        button_sizer.Add(accept_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(main_sizer)

        # Bind events
        browse_button.Bind(wx.EVT_BUTTON, self.on_browse)
        accept_button.Bind(wx.EVT_BUTTON, self.on_accept)
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)

    def on_browse(self, event):
        """Handle browse button click."""
        with wx.FileDialog(self, "Select log file", wildcard="Log files (*.log)|*.log|All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            self.file_path.SetValue(file_dialog.GetPath())

    def on_accept(self, event):
        """Handle accept button click."""
        log_file = self.file_path.GetValue()
        if not log_file:
            message = "Please select a log file."
            wx.MessageBox(message, "Error", wx.OK | wx.ICON_ERROR)
            message_bus.publish(content=message, level=MessageLevel.ERROR)
            return
        self.GetParent().run_process_log(log_file)
        self.Destroy()

    def on_cancel(self, event):
        """Handle cancel button click."""
        self.Destroy()


class AboutDialog(wx.Dialog):
    """A styled About dialog."""
    def __init__(self, parent, update_callback=None):
        super().__init__(parent, title="About SC Log Analyzer", size=(400, 430))  # Slightly reduced height

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Add application name
        app_name = wx.StaticText(panel, label="SC Log Analyzer")
        app_name.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(app_name, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Add version dynamically
        version = wx.StaticText(panel, label=f"Version: {get_version()}")
        sizer.Add(version, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        # Add description
        description = wx.StaticText(panel, label="A tool for analyzing Star Citizen logs.")
        description.Wrap(350)
        sizer.Add(description, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Add recent commits section
        try:
            from version import COMMIT_MESSAGES
            if COMMIT_MESSAGES:
                commits_label = wx.StaticText(panel, label="Recent Changes:")
                commits_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                sizer.Add(commits_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
                
                # Create a scrolled window for commit messages with fixed height
                commits_scrolled = wx.ScrolledWindow(panel, style=wx.VSCROLL)
                commits_scrolled.SetScrollRate(0, 10)
                commits_scrolled.SetMinSize((350, 120))  # Fixed height
                
                # Add commit messages to the scrolled window
                commits_sizer = wx.BoxSizer(wx.VERTICAL)
                for commit in COMMIT_MESSAGES:
                    commit_text = wx.StaticText(commits_scrolled, label=f"• {commit}")
                    commit_text.Wrap(330)  # Wrap text to fit in the panel
                    commits_sizer.Add(commit_text, 0, wx.EXPAND | wx.BOTTOM, 3)
                
                commits_scrolled.SetSizer(commits_sizer)
                sizer.Add(commits_scrolled, 0, wx.ALL | wx.EXPAND, 5)  # Not expanding vertically beyond min size
        except (ImportError, AttributeError):
            # Skip if COMMIT_MESSAGES is not available
            pass

        # Update credits to reflect the correct author
        credits = wx.StaticText(panel, label="Developed by IJOL.")
        credits.Wrap(350)
        sizer.Add(credits, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Place both buttons in the same horizontal row to save space
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Add Check for Updates button on the left
        self.update_button = wx.Button(panel, label="Check for Updates")
        if update_callback:
            self.update_button.Bind(wx.EVT_BUTTON, lambda event: update_callback())
        buttons_sizer.Add(self.update_button, 0, wx.RIGHT, 10)
        
        # Add close button on the right
        close_button = wx.Button(panel, wx.ID_CLOSE, label="Close")
        close_button.Bind(wx.EVT_BUTTON, lambda event: self.Close())
        buttons_sizer.Add(close_button, 0, wx.LEFT, 10)
        
        # Add the buttons sizer to main sizer with more compact margins
        sizer.Add(buttons_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        # Set sizer for panel and ensure dialog has standard button look
        panel.SetSizer(sizer)
        
        # Bind the close event to ensure proper closing
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
    def on_close(self, event):
        """Handle dialog close event."""
        self.EndModal(wx.ID_CLOSE)
        self.Destroy()


class WindowsHelper:
    PRINT_SCREEN_KEY = "print_screen"
    RETURN_KEY = "return"
    # Add a constant for the key next to "1" (backtick/tilde on US keyboards, º/ª on Spanish)
    CONSOLE_KEY = "console_key"
    
    @staticmethod
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

    @staticmethod
    def capture_window_screenshot(hwnd, output_path, **kwargs):
        """Capture a screenshot of a specific window using its handle."""
        if not hwnd:
            hwnd = WindowsHelper.find_window_by_title("Star Citizen", class_name="CryENGINE", process_name="StarCitizen.exe")

        full = 'full' in kwargs
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            if full:
                width = right - left
                height = bottom - top
            else:                
                width = 200
                height = 200
                left = right - width

            with mss.mss() as sct:
                monitor = {"top": top, "left": left, "width": width, "height": height}
                screenshot = sct.grab(monitor)

                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                img.save(output_path, format="JPEG", quality=85)
        except Exception as e:
            raise RuntimeError(f"Error capturing screenshot: {e}")

    @staticmethod
    def send_keystrokes_to_window(window_title, keystrokes, screenshots_folder, **kwargs):
        """Send keystrokes to a specific window and capture a screenshot if PRINT_SCREEN_KEY is triggered."""
        try:
            hwnd = WindowsHelper.focus_sc()
            if not hwnd:
                raise RuntimeError(f"Window with title '{window_title}' not found.")

            time.sleep(0.05)

            keyboard = Controller()
            for key in keystrokes:
                if key == WindowsHelper.PRINT_SCREEN_KEY:
                    timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
                    screenshot_path = os.path.join(screenshots_folder, f"screenshot_{timestamp}.jpg")
                    WindowsHelper.capture_window_screenshot(hwnd, screenshot_path)
                elif key == WindowsHelper.RETURN_KEY:
                    keyboard.tap(Key.enter)
                elif key == WindowsHelper.CONSOLE_KEY:   
                    # Use standard Windows API to send the key to the left of "1"
                    win32api.keybd_event(0, 0x29 , 0, 0)  # Press the key (0xC0 is the virtual key code for backtick/tilde)
                    time.sleep(0.05)
                    win32api.keybd_event( 0, 0x29 ,  win32con.KEYEVENTF_KEYUP, 0)  # Release the key
                elif isinstance(key, str):
                    for char in key:
                        keyboard.tap(char)
                        time.sleep(0.05)
                else:
                    keyboard.tap(key)
                time.sleep(0.05)
        except Exception as e:
            raise RuntimeError(f"Error sending keystrokes to window: {e}")

    @staticmethod
    def focus_sc():
        hwnd = WindowsHelper.find_window_by_title("Star Citizen", class_name="CryENGINE", process_name="StarCitizen.exe")
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return hwnd
        return None

class NumericValidator(wx.Validator):
    """Custom numeric validator for text controls."""
    def __init__(self, allow_float=True):
        wx.Validator.__init__(self)
        self.allow_float = allow_float
        self.Bind(wx.EVT_CHAR, self.on_char)

    def Clone(self):
        return NumericValidator(self.allow_float)

    def Validate(self, win):
        text_ctrl = self.GetWindow()
        text = text_ctrl.GetValue()
        if not text:
            return True  # Empty is valid
        try:
            if self.allow_float:
                float(text)
            else:
                int(text)
            return True
        except ValueError:
            return False

    def on_char(self, event):
        key = event.GetKeyCode()
        text_ctrl = self.GetWindow()
        current_text = text_ctrl.GetValue()

        # Allow control keys (backspace, delete, arrow keys, etc.)
        if key < wx.WXK_SPACE or key == wx.WXK_DELETE or key > 255:
            event.Skip()
            return

        # Allow digits
        if chr(key).isdigit():
            event.Skip()
            return

        # Allow decimal point if float is allowed and not already in the text
        if self.allow_float and chr(key) == '.' and '.' not in current_text:
            event.Skip()
            return

        # Allow minus sign as first character if not already present
        if chr(key) == '-' and current_text == '':
            event.Skip()
            return

        # Block all other characters
        return

def is_app_in_startup(app_name):
    """Check if the app is set to run at Windows startup."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_READ) as key:
            try:
                value = winreg.QueryValueEx(key, app_name)
                return True
            except FileNotFoundError:
                return False
    except Exception as e:
        print(f"Error checking startup registry key: {e}")
        return False

def add_app_to_startup(app_name, app_path):
    """Add the app to Windows startup."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
            print(f"{app_name} added to Windows startup.")
    except Exception as e:
        print(f"Error adding app to startup: {e}")

def remove_app_from_startup(app_name):
    """Remove the app from Windows startup."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_WRITE) as key:
            winreg.DeleteValue(key, app_name)
            print(f"{app_name} removed from Windows startup.")
    except FileNotFoundError:
        print(f"{app_name} is not in Windows startup.")
    except Exception as e:
        print(f"Error removing app from startup: {e}")

class TaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame, tooltip="SC Log Analyzer"):
        super().__init__()
        self.frame = frame
        self.tooltip = tooltip

        # Set the icon using the custom application icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SCLogAnalyzer.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO), self.tooltip)
        else:
            # Fallback to a stock icon if the custom icon is missing
            icon = wx.ArtProvider.GetIcon(wx.ART_INFORMATION, wx.ART_OTHER, (16, 16))
            self.SetIcon(icon, self.tooltip)

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


class DataTransferDialog(wx.Dialog):
    """Dialog for transferring data from Google Sheets to Supabase."""
    def __init__(self, parent):
        super().__init__(parent, title="Data Transfer", size=(550, 550), 
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)  # Increased height and added resize capability

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title_label = wx.StaticText(panel, label="Transfer Data from Google Sheets to Supabase")
        title_label.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        main_sizer.Add(title_label, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Description
        desc_text = (
            "This tool will transfer your data from Google Sheets to Supabase.\n"
            "Make sure both your Google Sheets webhook URL and Supabase credentials\n"
            "are correctly configured before proceeding."
        )
        description = wx.StaticText(panel, label=desc_text)
        main_sizer.Add(description, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        # Options
        options_box = wx.StaticBox(panel, label="Transfer Options")
        options_sizer = wx.StaticBoxSizer(options_box, wx.VERTICAL)

        # Transfer all data option
        self.all_data_radio = wx.RadioButton(options_box, label="Transfer all data", style=wx.RB_GROUP)
        options_sizer.Add(self.all_data_radio, 0, wx.ALL | wx.EXPAND, 5)
        
        # Config only option
        self.config_only_radio = wx.RadioButton(options_box, label="Transfer configuration only")
        options_sizer.Add(self.config_only_radio, 0, wx.ALL | wx.EXPAND, 5)

        # Add a separator
        options_sizer.Add(wx.StaticLine(options_box), 0, wx.EXPAND | wx.ALL, 5)
        
        # Data transfer mode options
        mode_label = wx.StaticText(options_box, label="Data Transfer Mode:")
        options_sizer.Add(mode_label, 0, wx.ALL, 5)
        
        # Purge first option
        self.purge_radio = wx.RadioButton(options_box, label="Delete existing data first (faster)", style=wx.RB_GROUP)
        options_sizer.Add(self.purge_radio, 0, wx.ALL | wx.EXPAND, 5)
        
        # Skip duplicates option
        self.skip_duplicates_radio = wx.RadioButton(options_box, label="Only add new records (skip duplicates)")
        options_sizer.Add(self.skip_duplicates_radio, 0, wx.ALL | wx.EXPAND, 5)

        # Batch size setting
        batch_sizer = wx.BoxSizer(wx.HORIZONTAL)
        batch_label = wx.StaticText(options_box, label="Batch size:")
        self.batch_size_ctrl = wx.SpinCtrl(options_box, min=10, max=100, initial=50)
        batch_tip = wx.StaticText(options_box, label="(Smaller batches are safer, but slower)")
        batch_sizer.Add(batch_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        batch_sizer.Add(self.batch_size_ctrl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        batch_sizer.Add(batch_tip, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        options_sizer.Add(batch_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Progress area
        progress_sizer = wx.BoxSizer(wx.VERTICAL)
        self.progress_text = wx.StaticText(panel, label="Status: Ready")
        progress_sizer.Add(self.progress_text, 0, wx.ALL | wx.EXPAND, 5)
        
        self.progress_bar = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.progress_bar.SetValue(0)
        progress_sizer.Add(self.progress_bar, 0, wx.ALL | wx.EXPAND, 5)

        # Add options and progress sections to main sizer
        main_sizer.Add(options_sizer, 0, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(progress_sizer, 0, wx.ALL | wx.EXPAND, 10)

        # Add a separator
        main_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 5)
        
        # Add a spacer to push content up
        main_sizer.AddStretchSpacer()
        
        # SIMPLIFIED BUTTON SECTION - Directly add buttons to the main panel 
        # without nesting in another panel
        button_sizer = wx.StdDialogButtonSizer()
        
        # Create larger buttons with clear labels
        self.start_button = wx.Button(panel, wx.ID_OK, label="Start Transfer", size=(140, 40))
        self.start_button.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, label="Cancel", size=(140, 40))
        self.cancel_button.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        # Add buttons to the standard dialog sizer
        button_sizer.AddButton(self.start_button)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()
        
        # Add the button sizer with a larger margin to ensure visibility
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 30)
        
        # Set the sizer and fit dialog to contents
        panel.SetSizer(main_sizer)
        
        # Bind events
        self.start_button.Bind(wx.EVT_BUTTON, self.on_start)
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        self.all_data_radio.Bind(wx.EVT_RADIOBUTTON, self.on_radio_change)
        self.config_only_radio.Bind(wx.EVT_RADIOBUTTON, self.on_radio_change)
        
        # Initialize state
        self.is_running = False
        self.transfer_task = None

    def on_radio_change(self, event):
        """Handle radio button changes."""
        # Enable/disable batch size control based on selection
        self.batch_size_ctrl.Enable(self.all_data_radio.GetValue())

    def on_start(self, event):
        """Start the data transfer process."""
        if self.is_running:
            return
        
        # Get options
        config_only = self.config_only_radio.GetValue()
        batch_size = self.batch_size_ctrl.GetValue()
        purge_first = self.purge_radio.GetValue()  # Get the selected transfer mode
        
        # Disable UI during transfer
        self.start_button.Disable()
        self.all_data_radio.Disable()
        self.config_only_radio.Disable()
        self.batch_size_ctrl.Disable()
        self.purge_radio.Disable()
        self.skip_duplicates_radio.Disable()
        self.is_running = True
        
        # Update UI
        self.progress_text.SetLabel("Status: Initializing transfer...")
        self.progress_bar.SetValue(10)
        
        # Start transfer in a separate thread
        import threading
        from .data_transfer import transfer_all_data_to_supabase, transfer_config_to_supabase
        from .message_bus import message_bus, MessageLevel
        
        def run_transfer():
            try:
                wx.CallAfter(self.progress_text.SetLabel, "Status: Connecting to data sources...")
                wx.CallAfter(self.progress_bar.SetValue, 20)
                
                # Get configuration manager from parent
                config_manager = self.GetParent().config_manager
                
                # Run the transfer based on options
                if config_only:
                    wx.CallAfter(self.progress_text.SetLabel, "Status: Transferring configuration...")
                    wx.CallAfter(self.progress_bar.SetValue, 40)
                    success = transfer_config_to_supabase(config_manager)
                else:
                    wx.CallAfter(self.progress_text.SetLabel, "Status: Transferring all data...")
                    wx.CallAfter(self.progress_bar.SetValue, 30)
                    success = transfer_all_data_to_supabase(config_manager, batch_size, purge_first)
                
                # Update UI based on result
                if success:
                    wx.CallAfter(self.progress_text.SetLabel, "Status: Transfer completed successfully")
                    wx.CallAfter(self.progress_bar.SetValue, 100)
                    
                    # Update data source to Supabase in config
                    config_manager.set('datasource', 'supabase')
                    config_manager.save_config()
                    
                    message_bus.publish(
                        content="Data transfer completed. Default data source set to 'supabase'.",
                        level=MessageLevel.INFO
                    )
                    
                  
                    # Update tabs based on data source change
#                    wx.CallAfter(self.GetParent().data_manager.update_data_source_tabs)
                    
                    # Show success message
                    wx.CallAfter(wx.MessageBox, 
                                "Data transfer completed successfully.\nDefault data source has been set to Supabase.",
                                "Transfer Complete", 
                                wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.CallAfter(self.progress_text.SetLabel, "Status: Transfer failed")
                    wx.CallAfter(self.progress_bar.SetValue, 0)
                    wx.CallAfter(wx.MessageBox, 
                                "Data transfer failed. Please check the logs for details.",
                                "Transfer Failed", 
                                wx.OK | wx.ICON_ERROR)
                
                # Re-enable UI
                wx.CallAfter(self.start_button.Enable)
                wx.CallAfter(self.all_data_radio.Enable)
                wx.CallAfter(self.config_only_radio.Enable)
                wx.CallAfter(self.batch_size_ctrl.Enable, self.all_data_radio.GetValue())
                wx.CallAfter(self.purge_radio.Enable)
                wx.CallAfter(self.skip_duplicates_radio.Enable)
                
                self.is_running = False
                
            except Exception as e:
                message_bus.publish(
                    content=f"Error during data transfer: {e}",
                    level=MessageLevel.ERROR
                )
                wx.CallAfter(self.progress_text.SetLabel, f"Status: Error - {e}")
                wx.CallAfter(self.progress_bar.SetValue, 0)
                wx.CallAfter(self.start_button.Enable)
                wx.CallAfter(self.all_data_radio.Enable)
                wx.CallAfter(self.config_only_radio.Enable)
                wx.CallAfter(self.batch_size_ctrl.Enable, self.all_data_radio.GetValue())
                wx.CallAfter(self.purge_radio.Enable)
                wx.CallAfter(self.skip_duplicates_radio.Enable)
                self.is_running = False
        
        self.transfer_task = threading.Thread(target=run_transfer)
        self.transfer_task.daemon = True
        self.transfer_task.start()

    def on_cancel(self, event):
        """Handle cancel button click."""
        if self.is_running:
            message_bus.publish(
                content="Data transfer canceled by user.",
                level=MessageLevel.WARNING
            )
            # We can't actually stop the thread, but we can at least close the dialog
            self.EndModal(wx.ID_CANCEL)
        else:
            self.EndModal(wx.ID_CANCEL)
