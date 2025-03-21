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

class RedirectText:
    """Class to redirect stdout to a text control"""
    def __init__(self, text_ctrl):
        self.text_ctrl = text_ctrl
        self.stdout = sys.stdout
        
    def write(self, string):
        """Write to both stdout and text control"""
        self.stdout.write(string)
        wx.CallAfter(self.text_ctrl.AppendText, string)
        
    def flush(self):
        self.stdout.flush()

class KeyValueGrid(wx.Panel):
    """A reusable grid for editing key-value pairs."""
    def __init__(self, parent, title, data):
        super().__init__(parent)
        self.data = data

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

        # Add buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_button = wx.Button(self, label="Add")
        button_sizer.Add(add_button, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT)

        self.SetSizer(main_sizer)

        # Bind events
        add_button.Bind(wx.EVT_BUTTON, self.on_add)

    def add_row(self, key="", value=""):
        """Add a row to the grid."""
        key_ctrl = wx.TextCtrl(self, value=key)
        value_ctrl = wx.TextCtrl(self, value=value)
        delete_button = wx.Button(self, label="Delete")

        self.grid.Add(key_ctrl, 0, wx.EXPAND)
        self.grid.Add(value_ctrl, 1, wx.EXPAND)
        self.grid.Add(delete_button, 0, wx.ALIGN_CENTER)

        self.controls.append((key_ctrl, value_ctrl, delete_button))

        # Bind delete button event
        delete_button.Bind(wx.EVT_BUTTON, lambda event: self.on_delete(key_ctrl, value_ctrl, delete_button))

        self.Layout()

    def on_add(self, event):
        """Handle add button click."""
        # Add a new row with empty inputs for key and value
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
        return {key_ctrl.GetValue(): value_ctrl.GetValue() for key_ctrl, value_ctrl, _ in self.controls}

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
        self.messages_grid = self.add_tab(notebook, "Messages", "messages")
        self.discord_grid = self.add_tab(notebook, "Discord Messages", "discord")
        self.sheets_mapping_grid = self.add_tab(notebook, "Google Sheets Mapping", "google_sheets_mapping")

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)

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

    def add_tab(self, notebook, title, config_key):
        """Helper method to add a tab with a KeyValueGrid."""
        panel = wx.ScrolledWindow(notebook)
        panel.SetScrollRate(5, 5)
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = KeyValueGrid(panel, title, self.config_data.get(config_key, {}))
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
                sizer.Add(row_sizer, 0, wx.EXPAND)
        panel.SetSizer(sizer)
        notebook.AddPage(panel, title)

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
        
        options_sizer.Add(self.process_all_check, 0, wx.ALL, 5)
        options_sizer.Add(self.discord_check, 0, wx.ALL, 5)
        options_sizer.Add(self.googlesheet_check, 0, wx.ALL, 5)
        
        # Create action buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.process_button = wx.Button(panel, label="Process Log Once")
        self.monitor_button = wx.Button(panel, label="Start Monitoring")
        
        button_sizer.Add(self.process_button, 0, wx.ALL, 5)
        button_sizer.Add(self.monitor_button, 0, wx.ALL, 5)
        
        # Create log output area
        log_label = wx.StaticText(panel, label="Log Output:")
        self.log_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        
        # Set font to a monospaced font for better log readability
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.log_text.SetFont(font)
        
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
        
    def ensure_default_config(self):
        """Ensure the default configuration file exists."""
        app_path = log_analyzer.get_application_path()
        config_path = os.path.join(app_path, "config.json")
        
        if not os.path.exists(config_path):
            log_analyzer.emit_default_config(config_path, in_gui=True)

    def load_default_config(self):
        """Load default log file path from config"""
        app_path = log_analyzer.get_application_path()
        config_path = os.path.join(app_path, "config.json")
        
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
        """Handle browse button click event"""
        if self.monitoring:
            self.stop_monitoring()
            self.monitor_button.SetLabel("Start Monitoring")
            self.process_button.Enable(True)
            self.SetStatusText("Monitoring stopped")
            self.monitoring = False
        
        with wx.FileDialog(self, "Select log file", wildcard="Log files (*.log)|*.log|All files (*.*)|*.*",
                          style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            self.file_path.SetValue(file_dialog.GetPath())
            self.config_data['log_file_path'] = file_dialog.GetPath()
    
    def on_process(self, event):
        """Handle process once button click event"""
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
        
        thread = threading.Thread(target=self.run_process_log, args=(log_file, process_all, use_discord, use_googlesheet))
        thread.daemon = True
        thread.start()
    
    def run_process_log(self, log_file, process_all, use_discord, use_googlesheet):
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
            wx.CallAfter(self.process_button.Enable, True)
            wx.CallAfter(self.monitor_button.Enable, True)
    
    def on_monitor(self, event):
        """Handle start/stop monitoring button click event"""
        if self.monitoring:
            self.stop_monitoring()
            self.monitor_button.SetLabel("Start Monitoring")
            self.process_button.Enable(True)
            self.SetStatusText("Monitoring stopped")
            self.monitoring = False
        else:
            self.start_monitoring()
            self.monitor_button.SetLabel("Stop Monitoring")
            self.process_button.Enable(False)
            self.SetStatusText("Monitoring active")
            self.monitoring = True
    
    def start_monitoring(self):
        """Start log file monitoring"""
        self.log_text.Clear()
        
        log_file = self.file_path.GetValue()
        process_all = self.process_all_check.GetValue()
        use_discord = self.discord_check.GetValue()
        use_googlesheet = self.googlesheet_check.GetValue()
        
        # Run in a separate thread to keep UI responsive
        thread = threading.Thread(target=self.run_monitoring, args=(log_file, process_all, use_discord, use_googlesheet))
        thread.daemon = True
        thread.start()
    
    def run_monitoring(self, log_file, process_all, use_discord, use_googlesheet):
        """Run monitoring in thread"""
        try:
            # Call main without process_once
            result = log_analyzer.main(
                process_all=process_all,
                use_discord=use_discord,
                process_once=False,
                use_googlesheet=use_googlesheet,
                log_file_path=log_file
            )

            if result:
                self.event_handler, self.observer = result
        except Exception as e:
            wx.CallAfter(self.log_text.AppendText, f"Error starting monitoring: {e}\n")
            wx.CallAfter(self.monitor_button.SetLabel, "Start Monitoring")
            wx.CallAfter(self.process_button.Enable, True)
            wx.CallAfter(self.SetStatusText, "Error during monitoring")
            self.monitoring = False
    
    def stop_monitoring(self):
        """Stop log file monitoring"""
        if self.event_handler and self.observer:
            log_analyzer.stop_monitor(self.event_handler, self.observer)
            self.event_handler = None
            self.observer = None
    
    def append_log_message(self, message):
        """Append a log message to the GUI log output area."""
        wx.CallAfter(self.log_text.AppendText, message + "\n")

    def on_edit_config(self, event):
        """Open the configuration dialog."""
        app_path = log_analyzer.get_application_path()
        config_path = os.path.join(app_path, "config.json")
        if not hasattr(self, 'config_dialog') or not self.config_dialog:
            self.config_dialog = ConfigDialog(self, config_path)
        self.config_dialog.Show()
        self.config_dialog.Raise()

    def on_close(self, event):
        """Handle window close event"""
        if self.monitoring:
            self.stop_monitoring()
        
        # Restore original stdout
        sys.stdout = sys.__stdout__

        # Remove the custom log handler
        log_analyzer.main.gui_log_handler = None

        # Destroy the taskbar icon
        self.taskbar_icon.RemoveIcon()
        self.taskbar_icon.Destroy()

        # Destroy the window
        self.Destroy()

class TaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame

        # Set the icon using a stock icon
        icon = wx.ArtProvider.GetIcon(wx.ART_INFORMATION, wx.ART_OTHER, (16, 16))
        self.SetIcon(icon, "SC Log Analyzer")

        # Bind events
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_click)
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, self.on_right_click)

    def on_left_click(self, event):
        """Show or hide the main window on left-click"""
        if self.frame.IsShown():
            self.frame.Hide()
        else:
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
        wx.CallAfter(self.frame.Close)

def main():
    app = wx.App()
    frame = LogAnalyzerFrame()
    frame.Show()
    app.MainLoop()

if __name__ == "__main__":
    main()
