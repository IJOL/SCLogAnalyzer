#!/usr/bin/env python
import wx
import wx.grid
import threading
import json
import time
import traceback
from typing import Dict, Any, List, Callable, Optional
from .message_bus import message_bus, MessageLevel
from .supabase_manager import supabase_manager
from .ui_components import GridManager, safe_call_after

class DataDisplayManager:
    """Manages data fetching and display in grids."""
    
    def __init__(self, parent_frame, config_manager=None):
        """
        Initialize the data display manager.
        
        Args:
            parent_frame: The parent frame that contains the grids
            config_manager: Configuration manager instance. If None, will try to get from parent.
        """
        self.parent = parent_frame
        # Initialize debug mode to False by default
        self.debug_mode = False
        
        # Use provided config_manager or try to get from parent as fallback
        self.config_manager = config_manager
        if self.config_manager is None and hasattr(self.parent, 'config_manager'):
            self.config_manager = self.parent.config_manager
        
        # Set default log level filter to INFO on startup
        self._set_log_level_filter(MessageLevel.INFO)
        
        # Subscribe to datasource change events using MessageBus
        # message_bus.on("datasource_changed", self.on_datasource_change)
            
        # Rastreo de operaciones de actualización
        self._refresh_operations = set()  # Conjunto de operaciones de refresco activas
        self._refresh_timer = None
        self._refresh_operation_counter = 0  # Contador para generar IDs únicos
    
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
            # Enable message bus debug mode - peek at messages without consuming them
            message_bus.set_debug_mode(True)
            message_bus.publish(
                content="Debug mode enabled - showing all log levels and peeking at message bus",
                level=MessageLevel.INFO
            )
        else:
            # Only show INFO and above when debug mode is off
            self._set_log_level_filter(MessageLevel.INFO)
            # Disable message bus debug mode
            message_bus.set_debug_mode(False)
            message_bus.publish(
                content="Debug mode disabled - hiding DEBUG level messages",
                level=MessageLevel.INFO
            )
        
   
    def fetch_and_update(self, params, target_grid):
        """
        Fetch data based on parameters and update the target grid.
        Uses a single data provider based on current configuration.
        
        Args:
            params (dict): Parameters for the request
            target_grid (wx.grid.Grid): Grid to update with the data
        """
        try:
            # Import data provider at function call time to avoid circular imports
            from .data_provider import get_data_provider
            
            # Get the appropriate data provider based on configuration
            data_provider = get_data_provider(self.config_manager)
            
            if not data_provider.is_connected():
                message_bus.publish(
                    content="No connected data provider available",
                    level=MessageLevel.ERROR
                )
                safe_call_after(wx.MessageBox, 
                                "No data provider configured correctly. Please check your settings.", 
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
    
    def create_tabs(self, refresh_tabs=[]):
        """
        Update data tabs based on current configuration.
        
        Args:
            refresh_tabs (list): List of tab titles to refresh, empty for all tabs
        """
        # Generar un ID único para esta operación
        operation_id = f"create_{int(time.time())}_{self._refresh_operation_counter}"
        self._refresh_operation_counter += 1
        
        # Comprobar si ya tenemos una operación de creación reciente (en los últimos 3 segundos)
        current_time = time.time()
        recent_operations = [op for op in self._refresh_operations 
                           if op.startswith("create_") and 
                           current_time - float(op.split('_')[1]) < 3]
        
        if recent_operations:
            message_bus.publish(
                content="Tab creation already in progress, skipping duplicate request",
                level=MessageLevel.INFO
            )
            return
            
        # Registrar esta operación
        self._refresh_operations.add(operation_id)
        
        message_bus.publish(
            content="Starting tab creation and refresh",
            level=MessageLevel.INFO
        )
        
        try:
            tab_creator = self.parent.tab_creator
            
            if not len(tab_creator.tab_references):
                # If no tabs exist yet, create them
                required_tabs = self._get_required_tab_configs()
                
                # Create each tab in sequence
                for tab_info in required_tabs:
                    self._create_single_tab(tab_info)
                
                # Add Users Connected tab if using Supabase and RealtimeBridge is available
                self._add_users_connected_tab()
                
                # No longer need to load tabs in advance as refresh is connected to tab change
                # wx.CallLater(500, self._refresh_all_tabs)
            else:            
                # If tabs already exist, just refresh them
                if refresh_tabs:
                    # Solo refrescar tabs específicos
                    for title, tab_components in tab_creator.tab_references.items():
                        if title in refresh_tabs:
                            self.execute_refresh_event(tab_components[1])
                else:
                    # Refrescar todos los tabs
                    self._refresh_all_tabs()
        except Exception as e:
            message_bus.publish(
                content=f"Error in tab creation: {e}",
                level=MessageLevel.ERROR
            )
            message_bus.publish(
                content=traceback.format_exc(),
                level=MessageLevel.DEBUG
            )
        finally:
            # Eliminar esta operación del conjunto después de un tiempo razonable
            wx.CallLater(4000, lambda op_id=operation_id: self._refresh_operations.discard(op_id))
    
    def update_data_source_tabs(self):
        """
        Update tabs based on the current data source configuration.
        Called when toggling between data sources.
        """
        try:
            # Import our data provider system
            from .data_provider import get_data_provider
            
            # Get the configured data provider
            data_provider = get_data_provider(self.config_manager)
            
            if data_provider.is_connected():
                message_bus.publish(
                    content=f"Using data provider: {data_provider.__class__.__name__}",
                    level=MessageLevel.INFO
                )
                # Use the standard create_tabs method to recreate tabs with the current data provider
                wx.CallAfter(self.create_tabs)
            else:
                message_bus.publish(
                    content=f"Data provider is not properly connected: {data_provider.__class__.__name__}",
                    level=MessageLevel.WARNING
                )
        except Exception as e:
            message_bus.publish(
                content=f"Error updating data source tabs: {e}",
                level=MessageLevel.ERROR
            )
            message_bus.publish(
                content=traceback.format_exc(),
                level=MessageLevel.DEBUG
            )
    
    def test_data_provider(self):
        """Handle testing the currently active data provider."""
        try:
            # Import data provider at function call time to avoid circular imports
            from .data_provider import get_data_provider
            
            # Get the appropriate data provider based on configuration
            data_provider = get_data_provider(self.config_manager)
            
            if not data_provider.is_connected():
                wx.MessageBox("No data provider is connected. Please check your configuration.", 
                             "Error", wx.OK | wx.ICON_ERROR)
                return
            
            provider_name = data_provider.__class__.__name__
            message_bus.publish(
                content=f"Testing data provider: {provider_name}",
                level=MessageLevel.INFO
            )
            
            # Mock data to send
            mock_data = {
                "sheet": "TestSheet",
                "log_type": "TestLog",
                "username": "TestUser",
                "action": "Test Action",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "details": f"This is a test entry for {provider_name}."
            }

            # Send the mock data using the monitoring service
            if not hasattr(self.parent, 'monitoring_service') or not hasattr(self.parent.monitoring_service, 'event_handler'):
                wx.MessageBox("Monitoring service is not available. Please try again later.", 
                             "Error", wx.OK | wx.ICON_ERROR)
                return
                
            event_handler = self.parent.monitoring_service.event_handler
            success = event_handler.update_data_queue(mock_data, "SC_Default")
            
            if success:
                wx.MessageBox(f"Test entry sent successfully to {provider_name}.", 
                             "Success", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox(f"Failed to send test entry to {provider_name}. Check the logs for details.", 
                             "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error testing data provider: {e}", 
                         "Error", wx.OK | wx.ICON_ERROR)
    
  
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
                    form_fields=tab_info["form_fields"],
                    tab_info=tab_info  # Pass the complete tab_info
                )
            else:
                tab_creator.add_tab(
                    title, 
                    params=tab_info["params"],
                    tab_info=tab_info  # Pass the complete tab_info
                )
                
            # Update log with creation status
            message_bus.publish(
                content=f"Tab \"{title}\" created",
                level=MessageLevel.INFO
            )
            
            # Check if this is the last tab and trigger refresh if needed
        except Exception as e:
            message_bus.publish(
                content=f"Error creating tab \"{tab_info.get('title', 'unknown')}\": {e}",
                level=MessageLevel.ERROR
            )
    
    def _refresh_all_tabs(self):
        """
        Refresh all tabs with current data in a staggered manner.
        This method ensures that not all tabs are refreshed at the same time.
        """
        try:
            self.parent.SetStatusText("Loading tab data...")
            tab_creator = self.parent.tab_creator
            
            # Don't refresh if username is Unknown or not set
            current_username = getattr(self.parent, "username", None)
            if current_username is None or current_username == "Unknown":
                message_bus.publish(
                    content="Skipping data load until valid username is available",
                    level=MessageLevel.INFO
                )
                self.parent.SetStatusText("Waiting for user login...")
                return
                
            # Generar un ID único para esta operación de refresco
            operation_id = f"refresh_{int(time.time())}_{self._refresh_operation_counter}"
            self._refresh_operation_counter += 1
            
            # Comprobar si ya tenemos una operación de refresco reciente (en los últimos 2 segundos)
            current_time = time.time()
            recent_operations = [op for op in self._refresh_operations 
                               if op.startswith("refresh_") and 
                               current_time - float(op.split('_')[1]) < 2]
                
            if recent_operations:
                message_bus.publish(
                    content=f"Skipping duplicate refresh request (recent operation in progress)",
                    level=MessageLevel.INFO
                )
                return
                
            # Registrar esta operación
            self._refresh_operations.add(operation_id)
                
            message_bus.publish(
                content=f"Loading data for user: {current_username}",
                level=MessageLevel.INFO
            )
            
            # Use a single staggered refresh approach
            tab_count = len(tab_creator.tab_references)
            index = 0
            
            for title, (grid, refresh_button) in tab_creator.tab_references.items():
                # Log the scheduled refresh
                message_bus.publish(
                    content=f"Scheduling refresh for tab: {title}",
                    level=MessageLevel.DEBUG
                )
                
                # Usar un retraso progresivo para evitar solicitudes simultáneas
                delay = 300 + (400 * index)
                wx.CallLater(delay, self.execute_refresh_event, refresh_button)
                index += 1
            
            # Update status when complete - add extra time based on tab count
            wx.CallLater(500 + (600 * tab_count), 
                         lambda: self.parent.SetStatusText("Ready"))
            
            # Eliminar esta operación del conjunto después de completarse
            wx.CallLater(500 + (800 * tab_count), 
                         lambda op_id=operation_id: self._refresh_operations.discard(op_id))
                         
        except Exception as e:
            message_bus.publish(
                content=f"Error refreshing tabs: {e}",
                level=MessageLevel.ERROR
            )

    def _add_users_connected_tab(self):
        """
        Añade la pestaña de usuarios conectados si estamos usando Supabase y RealtimeBridge está disponible.
        """
        try:
            # Comprobar si estamos usando Supabase y si RealtimeBridge está disponible
            if self.config_manager.get('datasource') != 'supabase':
                return
                
            if not hasattr(self.parent, 'realtime_bridge') or self.parent.realtime_bridge is None:
                message_bus.publish(
                    content="Realtime bridge not available, skipping connected users tab",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "data_display_manager"}
                )
                return
                
            message_bus.publish(
                content="Adding connected users tab",
                level=MessageLevel.INFO,
                metadata={"source": "data_display_manager"}
            )
            
            # Importar el panel de usuarios conectados
            from .connected_users_panel import ConnectedUsersPanel
            
            # Crear el panel y añadirlo como pestaña al notebook
            notebook = self.parent.notebook
            connected_users_panel = ConnectedUsersPanel(notebook)
            notebook.AddPage(connected_users_panel, "Usuarios conectados")
            
            message_bus.publish(
                content="Connected users tab added successfully",
                level=MessageLevel.INFO,
                metadata={"source": "data_display_manager"}
            )
            
        except Exception as e:
            message_bus.publish(
                content=f"Error adding connected users tab: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "data_display_manager"}
            )
            message_bus.publish(
                content=traceback.format_exc(),
                level=MessageLevel.DEBUG
            )

    def _get_required_tab_configs(self):
        """Get the list of tab configurations - centralized for maintainability"""
        # Hardcoded tabs - these will always be available
        hardcoded_tabs = [
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
        
        # Get dynamic tabs from config.json if any
        dynamic_tabs = []
        if self.config_manager:
            config_tabs = self.config_manager.get('tabs', {})
            if config_tabs and isinstance(config_tabs, dict):
                message_bus.publish(
                    content=f"Found {len(config_tabs)} dynamic tabs in configuration",
                    level=MessageLevel.INFO
                )
                
                # Check if we're using Supabase, and if so, ensure the views for dynamic tabs exist
                datasource = self.config_manager.get("datasource", "googlesheets")
                if datasource == "supabase":
                    from .data_provider import get_data_provider
                    
                    data_provider = get_data_provider(self.config_manager)
                    if hasattr(data_provider, 'ensure_dynamic_views'):
                        # Use our centralized method to ensure all dynamic views exist
                        message_bus.publish(
                            content="Ensuring dynamic tab views exist in Supabase using centralized method...",
                            level=MessageLevel.INFO
                        )
                        
                        # Filter out tab names that conflict with hardcoded tabs
                        valid_tab_configs = {}
                        for tab_name, query in config_tabs.items():
                            if any(tab["title"] == tab_name for tab in hardcoded_tabs):
                                message_bus.publish(
                                    content=f"Skipping dynamic tab '{tab_name}' as it conflicts with a hardcoded tab name",
                                    level=MessageLevel.WARNING
                                )
                            else:
                                valid_tab_configs[tab_name] = query
                        
                        # Create all views in a single operation
                        if valid_tab_configs:
                            data_provider.ensure_dynamic_views(valid_tab_configs)
                
                # Create a tab config for each entry in the tabs section
                for tab_name, query in config_tabs.items():
                    # Skip any tab that matches a hardcoded tab name to avoid collisions
                    if any(tab["title"] == tab_name for tab in hardcoded_tabs):
                        continue
                    
                    # For Supabase, check if the view actually exists before adding the tab
                    if datasource == "supabase":
                        # Check if this view actually exists in the database
                        if not data_provider.view_exists(tab_name):
                            message_bus.publish(
                                content=f"Skipping tab '{tab_name}' as the corresponding view does not exist in the database",
                                level=MessageLevel.INFO
                            )
                            continue
                    
                    # Create a tab configuration for this dynamic tab
                    dynamic_tabs.append({
                        "title": tab_name, 
                        "params": {"sheet": tab_name, 'username': lambda self: self.username},  # Use the tab name as the "sheet" parameter
                        "query": query  # Store the SQL query for later view creation
                    })
        
        # Combine hardcoded and dynamic tabs
        return hardcoded_tabs + dynamic_tabs
