#!/usr/bin/env python
import wx
import wx.grid
import threading
import json
import time
from typing import Dict, Any, List, Callable, Optional
from .message_bus import message_bus, MessageLevel
from .supabase_manager import supabase_manager
from .ui_components import GridManager, safe_call_after

class DataDisplayManager:
    """Manages data fetching and display in grids."""
    
    def __init__(self, parent_frame):
        """
        Initialize the data display manager.
        
        Args:
            parent_frame: The parent frame that contains the grids
        """
        self.parent = parent_frame
        # Initialize debug mode to False by default
        self.debug_mode = False
        # Set default log level filter to INFO on startup
        self._set_log_level_filter(MessageLevel.INFO)
    
    def _set_log_level_filter(self, level):
        """
        Set the log level filter for the main log display.
        
        Args:
            level (MessageLevel): Minimum message level to display
        """
        # Set filter on the message bus for the main frame's log subscription
        if hasattr(self.parent, 'log_subscription_name'):
            message_bus.set_filter(
                self.parent.log_subscription_name,
                'level',
                level
            )
    
    def set_debug_mode(self, enabled):
        """
        Enable or disable debug mode, affecting log level visibility.
        
        Args:
            enabled (bool): True to enable debug mode, False to disable
        """
        self.debug_mode = enabled
        
        # Update the log level filter based on debug mode
        if enabled:
            # Show all messages including DEBUG when debug mode is on
            self._set_log_level_filter(MessageLevel.DEBUG)
            message_bus.publish(
                content="Debug mode enabled - showing all log levels",
                level=MessageLevel.INFO
            )
        else:
            # Only show INFO and above when debug mode is off
            self._set_log_level_filter(MessageLevel.INFO)
            message_bus.publish(
                content="Debug mode disabled - hiding DEBUG level messages",
                level=MessageLevel.INFO
            )
        
        # Save debug mode in configuration if available
        if hasattr(self.parent, 'config_manager'):
            self.parent.config_manager.set("debug_mode", enabled)
    
    def fetch_and_update(self, params, target_grid):
        """
        Fetch data based on parameters and update the target grid.
        
        Args:
            params (dict): Parameters for the request
            target_grid (wx.grid.Grid): Grid to update with the data
        """
        try:
            # Import data provider at function call time to avoid circular imports
            from .data_provider import get_data_provider
            
            # Use the config_manager as the source of truth for data source
            use_supabase = self.parent.config_manager.get("use_supabase", False)
            
            # Log which data source we're attempting to use
            message_bus.publish(
                content=f"Attempting to fetch data using {'Supabase' if use_supabase else 'Google Sheets'}",
                level=MessageLevel.DEBUG
            )
            
            # If Supabase is configured but not connected, fall back to Google Sheets
            if use_supabase and not supabase_manager.is_connected():
                message_bus.publish(
                    content="Supabase connection failed. Falling back to Google Sheets.",
                    level=MessageLevel.WARNING
                )
                use_supabase = False
                # Update config to reflect the actual state
                self.parent.config_manager.set("use_supabase", False)
                self.parent.config_manager.set("use_googlesheet", True)
                # Update UI to match config
                safe_call_after(self.parent.supabase_check.Check, False)
                safe_call_after(self.parent.googlesheet_check.Check, True)
                
            # Get the appropriate data provider based on configuration
            data_provider = get_data_provider(self.parent.config_manager)
            
            if not data_provider:
                message_bus.publish(
                    content="No data provider available",
                    level=MessageLevel.ERROR
                )
                safe_call_after(wx.MessageBox, 
                                "No data provider configured. Please set up either Google Sheets or Supabase.", 
                                "Error", wx.OK | wx.ICON_ERROR)
                return
                
            # Log the actual data provider type we're using
            message_bus.publish(
                content=f"Using data provider: {data_provider.__class__.__name__}",
                level=MessageLevel.DEBUG
            )
            
            # Default sheet name
            sheet_name = "Resumen"
            username = None
            
            # Extract sheet name from params if available
            if params:
                if "sheet" in params and params["sheet"]:
                    sheet_name = params["sheet"]
                if "username" in params:
                    username = params["username"]
            
            # Log the request parameters
            message_bus.publish(
                content=f"Fetching data from sheet '{sheet_name}' with username filter: {username}",
                level=MessageLevel.DEBUG
            )
                
            # Use the data provider to fetch data with the sheet name and username
            data = data_provider.fetch_data(sheet_name, username)
            
            # Log the result
            if data:
                message_bus.publish(
                    content=f"Fetched {len(data)} records from data source",
                    level=MessageLevel.DEBUG
                )
            else:
                message_bus.publish(
                    content="No data returned from data source",
                    level=MessageLevel.WARNING
                )
            
            if not isinstance(data, list) or not data:
                return

            # Update the grid with data
            safe_call_after(GridManager.update_sheets_grid, data, target_grid)
        except Exception as e:
            # Create a local function that captures e in its scope
            def show_error(error=e):
                message_bus.publish(
                    content=f"Error during data fetch: {error}",
                    level=MessageLevel.ERROR
                )
            # Call the function through safe_call_after
            safe_call_after(show_error)
        finally:
            # Clear loading state
            safe_call_after(GridManager.set_grid_loading, target_grid, False)
    
    def on_refresh_tab(self, event):
        """
        Handle refresh button click.
        Extracts grid and params from the button and refreshes data.
        
        Args:
            event: The button click event
        """
        button = event.GetEventObject()
        params = button.params
        
        # Set loading state in the grid
        GridManager.set_grid_loading(button.grid, True)
        
        # Resolve callable parameters if necessary
        if params:
            resolved_params = {}
            for key, value in params.items():
                if callable(value):
                    try:
                        resolved_params[key] = value(self.parent)
                    except Exception as e:
                        wx.MessageBox(f"Error resolving parameter \"{key}\": {e}", 
                                    "Error", wx.OK | wx.ICON_ERROR)
                        return
                else:
                    resolved_params[key] = value
            params = resolved_params
        
        # Start the fetch in a separate thread
        threading.Thread(
            target=self.fetch_and_update, 
            args=(params, button.grid), 
            daemon=True
        ).start()
    
    def on_form_submit(self, event, url, refresh_button, form_controls, sheet):
        """
        Handle form submission.

        Args:
            event (wx.Event): The event object.
            url (str): The URL to send the form data to (deprecated, kept for compatibility).
            refresh_button (wx.Button): The refresh button for the grid.
            form_controls (dict): Dictionary of form controls.
            sheet (str): The sheet name to update.
        """
        try:
            # Collect form data
            form_data = {}
            for field, control in form_controls.items():
                # Check numeric fields specifically
                if hasattr(control, "field_type") and control.field_type == "number":
                    try:
                        # Convert to appropriate numeric type before adding to form_data
                        value = control.GetValue()
                        if "." in value:
                            form_data[field] = float(value)
                        else:
                            form_data[field] = int(value) if value else 0
                    except ValueError:
                        wx.MessageBox(f"\"{field}\" must be a valid number.", "Validation Error", wx.OK | wx.ICON_ERROR)
                        return
                else:
                    form_data[field] = control.GetValue()
            form_data["sheet"] = sheet  # Add the sheet name to the form data
            
            # Send data to the queue via the event handler
            if not hasattr(self.parent, 'monitoring_service') or not hasattr(self.parent.monitoring_service, 'event_handler'):
                wx.MessageBox("Monitoring service is not available. Please try again later.", 
                             "Error", wx.OK | wx.ICON_ERROR)
                return
                
            event_handler = self.parent.monitoring_service.event_handler
            
            # Use the unified data queue
            success = event_handler.update_data_queue(form_data, sheet)
            
            if success:
                wx.MessageBox("Form submitted successfully.", "Success", wx.OK | wx.ICON_INFORMATION)
                # Clear all form fields after successful submission
                for field, control in form_controls.items():
                    if hasattr(control, "field_type") and control.field_type == "number":
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
    
    def execute_refresh_event(self, refresh_button):
        """
        Execute a refresh event on a button.
        
        Args:
            refresh_button (wx.Button): The button to generate a refresh event for
        """
        event = wx.CommandEvent(wx.wxEVT_BUTTON)
        event.SetEventObject(refresh_button)
        self.on_refresh_tab(event)
    
    def update_google_sheets_tabs(self, refresh_tabs=[]):
        """
        Update Google Sheets tabs based on current configuration.
        
        Args:
            refresh_tabs (list): List of tab titles to refresh, empty for all tabs
        """
        # Only add/update Google Sheets tabs if the webhook URL is valid
        google_sheets_webhook = self.parent.config_manager.get("google_sheets_webhook", "")
        googlesheet_check = self.parent.googlesheet_check.IsChecked()
        
        if google_sheets_webhook and googlesheet_check:
            # Define the tabs we want to ensure exist
            tab_creator = self.parent.tab_creator
            
            if not len(tab_creator.tab_references):
                # If no tabs exist yet, create them
                required_tabs = self._get_required_tab_configs()
                
                # Create each tab
                for tab_info in required_tabs:
                    self._create_single_tab(tab_info)
            else:            
                # If tabs already exist, just refresh them
                for title, tab_components in tab_creator.tab_references.items():
                    if title in refresh_tabs or len(refresh_tabs) == 0:
                        self.execute_refresh_event(tab_components[1])
    
    def update_data_source_tabs(self):
        """
        Update tabs based on the current data source (Google Sheets or Supabase).
        Called when toggling between data sources.
        """
        try:
            # Import our data provider system
            from .data_provider import get_data_provider
            
            # Determine which tabs need to be refreshed
            active_tabs = []
            
            tab_creator = self.parent.tab_creator
            
            use_supabase = self.parent.config_manager.get("use_supabase", False)
            supabase_check = self.parent.supabase_check.IsChecked()
            
            use_googlesheet = self.parent.config_manager.get("use_googlesheet", True)
            googlesheet_check = self.parent.googlesheet_check.IsChecked()
            
            if use_supabase and supabase_check:
                message_bus.publish(
                    content="Updating tabs to use Supabase data source",
                    level=MessageLevel.INFO
                )
                
                # Refresh all tabs - they'll now use Supabase data
                for title, (grid, refresh_button) in tab_creator.tab_references.items():
                    active_tabs.append(title)
                    # Update the URL to indicate Supabase is being used
                    refresh_button.is_supabase = True
                    
            elif use_googlesheet and googlesheet_check:
                message_bus.publish(
                    content="Updating tabs to use Google Sheets data source",
                    level=MessageLevel.INFO
                )
                
                # Refresh all tabs - they'll now use Google Sheets data
                for title, (grid, refresh_button) in tab_creator.tab_references.items():
                    active_tabs.append(title)
                    # Update the URL to indicate Google Sheets is being used
                    refresh_button.is_supabase = False
                    
            # Refresh tabs with the current data source
            for title in active_tabs:
                grid, refresh_button = tab_creator.tab_references[title]
                wx.CallLater(300, self.execute_refresh_event, refresh_button)
                
        except Exception as e:
            message_bus.publish(
                content=f"Error updating data source tabs: {e}",
                level=MessageLevel.ERROR
            )
            self.parent.SetStatusText("Error updating tabs")
    
    def test_google_sheets(self):
        """Handle the Test Google Sheets button click."""
        google_sheets_webhook = self.parent.config_manager.get("google_sheets_webhook", "")
        
        if not google_sheets_webhook:
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
            success = self.parent.monitoring_service.event_handler.update_google_sheets(mock_data, "SC_Default")
            if success:
                wx.MessageBox("Test entry sent successfully to Google Sheets.", "Success", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox("Failed to send test entry to Google Sheets. Check the logs for details.", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error sending test entry to Google Sheets: {e}", "Error", wx.OK | wx.ICON_ERROR)
    
    def async_init_tabs(self):
        """
        Initialize tabs asynchronously after the main window is loaded and stable.
        This prevents UI freezing during startup and improves user experience.
        """
        # Update status to indicate we're loading tabs
        self.parent.SetStatusText("Loading data tabs...")
        
        # Create a timer to delay tab creation (ensures window is fully rendered)
        wx.CallLater(1000, self._create_and_load_tabs)
    
    def _create_and_load_tabs(self):
        """
        Create and load tabs with data after a delay to ensure main window is stable.
        Separated from async_init_tabs to allow different timing options.
        """
        try:
            google_sheets_webhook = self.parent.config_manager.get("google_sheets_webhook", "")
            googlesheet_check = self.parent.googlesheet_check.IsChecked()
            
            # Only proceed if Google Sheets is enabled
            if google_sheets_webhook and googlesheet_check:
                # Log that we're starting to create tabs
                message_bus.publish(
                    content="Creating data tabs...",
                    level=MessageLevel.INFO
                )
                
                # Get required tabs with their configuration from the centralized method
                required_tabs = self._get_required_tab_configs()
                
                # Create each tab asynchronously 
                for i, tab_info in enumerate(required_tabs):
                    # Use another delayed call to stagger tab creation
                    wx.CallLater(200 * i, self._create_single_tab, tab_info)
                
                # After all tabs are scheduled for creation, update status
                wx.CallLater(200 * len(required_tabs) + 500, 
                             lambda: self.parent.SetStatusText("All tabs created"))
            else:
                self.parent.SetStatusText("Google Sheets integration disabled")
        except Exception as e:
            message_bus.publish(
                content=f"Error creating tabs: {e}",
                level=MessageLevel.ERROR
            )
            self.parent.SetStatusText("Error creating tabs")
    
    def _create_single_tab(self, tab_info):
        """
        Create a single tab with its configuration.
        
        Args:
            tab_info (dict): Tab configuration information
        """
        try:
            title = tab_info["title"]
            self.parent.SetStatusText(f"Creating tab: {title}...")
            
            tab_creator = self.parent.tab_creator
            
            # Create the tab based on its type
            if "form_fields" in tab_info:
                tab_creator.add_form_tab(
                    title,
                    params=tab_info["params"],
                    form_fields=tab_info["form_fields"]
                )
            else:
                tab_creator.add_tab(
                    title, 
                    params=tab_info["params"]
                )
                
            # Update log with creation status
            message_bus.publish(
                content=f"Tab \"{title}\" created",
                level=MessageLevel.INFO
            )
            
            # Check if this is the last tab and trigger refresh if needed
            if len(tab_creator.tab_references) == len(self._get_required_tabs()):
                # All tabs created, trigger initial data load
                wx.CallLater(500, self._refresh_all_tabs)
        except Exception as e:
            message_bus.publish(
                content=f"Error creating tab \"{tab_info.get('title', 'unknown')}\": {e}",
                level=MessageLevel.ERROR
            )
    
    def _refresh_all_tabs(self):
        """Refresh all tabs with current data"""
        try:
            self.parent.SetStatusText("Loading tab data...")
            tab_creator = self.parent.tab_creator
            
            # Don't refresh if username is Unknown or not set
            current_username = getattr(self.parent, "username", None)
            if current_username is None or current_username == "Unknown":
                message_bus.publish(
                    content="Skipping initial data load until valid username is available",
                    level=MessageLevel.INFO
                )
                self.parent.SetStatusText("Waiting for user login...")
                return
                
            message_bus.publish(
                content=f"Loading data for user: {current_username}",
                level=MessageLevel.INFO
            )
            
            for title, (grid, refresh_button) in tab_creator.tab_references.items():
                # Stagger refresh calls to prevent simultaneous requests
                wx.CallLater(300, self.execute_refresh_event, refresh_button)
            
            # Update status when complete
            wx.CallLater(500 + (300 * len(tab_creator.tab_references)), 
                         lambda: self.parent.SetStatusText("Ready"))
        except Exception as e:
            message_bus.publish(
                content=f"Error refreshing tabs: {e}",
                level=MessageLevel.ERROR
            )

    def _get_required_tabs(self):
        """Get the list of required tabs - factored out for maintainability"""
        return [
            "Stats", 
            "SC Default", 
            "SC Squadrons Battle", 
            "Materials"
        ]

    def _get_required_tab_configs(self):
        """Get the list of tab configurations - centralized for maintainability"""
        return [
            {"title": "Stats", "params": {"sheet": "Resumen"}},
            {"title": "SC Default", "params": {"sheet": "SC_Default", "username": lambda self: self.username}},
            {
                "title": "SC Squadrons Battle", 
                "params": {"sheet": "EA_SquadronBattle", "username": lambda self: self.username}
            },
            {
                "title": "Materials", 
                "params": {"sheet": "Materials", "username": lambda self: self.username}, 
                "form_fields": {"Material": "text", "Qty": "number", "committed": "check"}
            }
        ]