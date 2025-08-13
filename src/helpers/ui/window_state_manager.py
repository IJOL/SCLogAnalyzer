#!/usr/bin/env python
import wx
import os
import winreg
import sys
from helpers.core.message_bus import message_bus, MessageLevel

# Registry paths as constants
REGISTRY_KEY_PATH = r"Software\SCLogAnalyzer\WindowInfo"
STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_APP_NAME = "SCLogAnalyzer"
DEFAULT_WINDOW_POSITION = (50, 50)
DEFAULT_WINDOW_SIZE = (800, 600)

class WindowStateManager:
    """Manages window state persistence and restoration."""
    
    def __init__(self, parent_frame):
        """
        Initialize the window state manager.
        
        Args:
            parent_frame: The parent frame whose state to manage
        """
        self.parent = parent_frame
        self.save_timer = wx.Timer(parent_frame)
        self.parent.Bind(wx.EVT_TIMER, self.on_save_timer, self.save_timer)
        self.parent.Bind(wx.EVT_MOVE, self.on_window_move_or_resize)
        self.parent.Bind(wx.EVT_SIZE, self.on_window_move_or_resize)
        
    def save_window_info(self):
        """Save the window's current position, size, and state to the Windows registry."""
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY_PATH)
            position = list(self.parent.GetPosition())
            size = list(self.parent.GetSize())
            is_maximized = self.parent.IsMaximized()
            is_iconized = self.parent.IsIconized()
            winreg.SetValueEx(key, "Position", 0, winreg.REG_SZ, f"{position[0]},{position[1]}")
            winreg.SetValueEx(key, "Size", 0, winreg.REG_SZ, f"{size[0]},{size[1]}")
            winreg.SetValueEx(key, "Maximized", 0, winreg.REG_SZ, str(is_maximized))
            winreg.SetValueEx(key, "Iconized", 0, winreg.REG_SZ, str(is_iconized))
            winreg.CloseKey(key)
        except Exception as e:
            message_bus.publish(
                content=f"Error saving window info: {e}",
                level=MessageLevel.ERROR
            )

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
            self.parent.SetPosition(wx.Point(*position))
            self.parent.SetSize(wx.Size(*size))

            # Restore maximized or iconized state
            if is_maximized:
                self.parent.Maximize()
            elif is_iconized:
                self.parent.Iconize()
        except FileNotFoundError:
            # Use default position and size if registry key is not found
            self.parent.SetPosition(wx.Point(*DEFAULT_WINDOW_POSITION))
            self.parent.SetSize(wx.Size(*DEFAULT_WINDOW_SIZE))
        except Exception as e:
            message_bus.publish(
                content=f"Error restoring window info: {e}",
                level=MessageLevel.ERROR
            )
    
    def on_window_move_or_resize(self, event):
        """
        Handle window move or resize events.
        
        Args:
            event: The move or resize event
        """
        if not self.save_timer.IsRunning():
            self.save_timer.Start(500)  # Start the timer only if it's not already running
        event.Skip()

    def on_save_timer(self, event):
        """
        Save window info when the timer fires.
        
        Args:
            event: The timer event
        """
        self.save_window_info()
        self.save_timer.Stop()
        
    def cleanup(self):
        """
        Clean up resources, unbind events, and stop timers.
        Called when the window is closing.
        """
        # Save the window state one final time
        self.save_window_info()
        
        # Stop and nullify the timer
        if self.save_timer and self.save_timer.IsRunning():
            self.save_timer.Stop()
            
        # Unbind events to prevent callbacks after destruction
        self.parent.Unbind(wx.EVT_MOVE)
        self.parent.Unbind(wx.EVT_SIZE)
        self.parent.Unbind(wx.EVT_TIMER, handler=self.on_save_timer)


def is_app_in_startup(app_name):
    """
    Check if the app is set to run at Windows startup.
    
    Args:
        app_name (str): The name of the application in the registry
        
    Returns:
        bool: True if the app is set to run at startup, False otherwise
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_READ) as key:
            try:
                value = winreg.QueryValueEx(key, app_name)
                return True
            except FileNotFoundError:
                return False
    except Exception as e:
        message_bus.publish(
            content=f"Error checking startup registry key: {e}",
            level=MessageLevel.ERROR
        )
        return False

def add_app_to_startup(app_name, app_path):
    """
    Add the app to Windows startup.
    
    Args:
        app_name (str): The name to register the app as
        app_path (str): The full path to the app executable with any parameters
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
            message_bus.publish(
                content=f"{app_name} added to Windows startup.",
                level=MessageLevel.INFO
            )
            return True
    except Exception as e:
        message_bus.publish(
            content=f"Error adding app to startup: {e}",
            level=MessageLevel.ERROR
        )
        return False

def remove_app_from_startup(app_name):
    """
    Remove the app from Windows startup.
    
    Args:
        app_name (str): The name of the app to remove
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_WRITE) as key:
            winreg.DeleteValue(key, app_name)
            message_bus.publish(
                content=f"{app_name} removed from Windows startup.",
                level=MessageLevel.INFO
            )
            return True
    except FileNotFoundError:
        message_bus.publish(
            content=f"{app_name} is not in Windows startup.",
            level=MessageLevel.INFO
        )
        return True  # Not an error condition
    except Exception as e:
        message_bus.publish(
            content=f"Error removing app from startup: {e}",
            level=MessageLevel.ERROR
        )
        return False