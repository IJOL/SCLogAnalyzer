import wx
import os
import json
from config_utils import get_application_path  # Ensure this is imported if needed
import win32gui
from pynput.keyboard import Controller, Key
from PIL import Image
import mss
import time
import win32con  # Required for window constants like SW_RESTORE
import win32process  # Required for process-related functions
import win32api  # Required for sending keystrokes
import psutil  # Required for process management
from version import get_version  # Import get_version to fetch the version dynamically

class RedirectText:
    """Class to redirect stdout to a text control."""
    def __init__(self, text_ctrl):
        self.text_ctrl = text_ctrl

    def write(self, string):
        """Write to the text control."""
        wx.CallAfter(self.text_ctrl.AppendText, string)

    def flush(self):
        pass


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

        value_ctrl = wx.TextCtrl(self, value=value, style=wx.TE_MULTILINE)
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
            (key_ctrl.GetStringSelection() if isinstance(key_ctrl, wx.Choice) else key_ctrl.GetValue()): value_ctrl.GetValue()
            for key_ctrl, value_ctrl, _ in self.controls
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

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)

        # Add Accept, Save, and Cancel buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        accept_button = wx.Button(self, label="Accept")
        cancel_button = wx.Button(self, label="Cancel")
        button_sizer.Add(accept_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.SetSizer(main_sizer)

        # Bind events
        accept_button.Bind(wx.EVT_BUTTON, self.on_accept)
        cancel_button.Bind(wx.EVT_BUTTON, self.on_close)

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
            if key == "username":
                continue  # Skip username-related logic
            if isinstance(value, (str, int, float, bool)):  # Only first-level simple values
                label = wx.StaticText(panel, label=key)
                control = wx.CheckBox(panel) if isinstance(value, bool) else wx.TextCtrl(panel, value=str(value))
                control.SetValue(value) if isinstance(value, bool) else None
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
    def load_config(self):
        """Load configuration from the JSON file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as config_file:
                self.config_data = json.load(config_file)
                self.config_data.pop("username", None)  # Remove username if it exists
                self.config_data.pop("google_sheets_mapping", None)  # Remove google_sheets_mapping if it exists

    def save_config(self):
        """Save configuration to the JSON file."""
        # Save general config values
        for key, control in self.general_controls.items():
            self.config_data[key] = control.GetValue() if isinstance(control, wx.CheckBox) else control.GetValue()

    def on_accept(self, event):
        """Handle the Save button click."""
        self.save_config()
        with open(self.config_path, 'w', encoding='utf-8') as config_file:
            json.dump(self.config_data, config_file, indent=4)
        self.Destroy()

    def on_close(self, event):
        """Handle the Cancel button click."""
        self.Destroy()


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
            wx.MessageBox("Please select a log file.", "Error", wx.OK | wx.ICON_ERROR)
            return
        self.GetParent().run_process_log(log_file)
        self.Destroy()

    def on_cancel(self, event):
        """Handle cancel button click."""
        self.Destroy()


class AboutDialog(wx.Dialog):
    """A styled About dialog."""
    def __init__(self, parent):
        super().__init__(parent, title="About SC Log Analyzer", size=(400, 300))

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

        # Update credits to reflect the correct author
        credits = wx.StaticText(panel, label="Developed by IJOL.")
        credits.Wrap(350)
        sizer.Add(credits, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Add close button
        close_button = wx.Button(panel, label="Close")
        close_button.Bind(wx.EVT_BUTTON, lambda event: self.Close())
        sizer.Add(close_button, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel.SetSizer(sizer)


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
    def capture_window_screenshot(hwnd, output_path):
        """Capture a screenshot of a specific window using its handle."""
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
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
            hwnd = WindowsHelper.find_window_by_title(window_title, kwargs.get('class_name'), kwargs.get('process_name'))
            if not hwnd:
                raise RuntimeError(f"Window with title '{window_title}' not found.")

            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
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
