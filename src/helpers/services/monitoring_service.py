#!/usr/bin/env python
import threading
import os
import wx
import time
from watchdog.observers.polling import PollingObserver as Observer
from helpers.core import log_analyzer
from helpers.core.message_bus import message_bus, MessageLevel

class MonitoringService:
    """Manages log file monitoring."""
    
    def __init__(self, parent_frame):
        """
        Initialize the monitoring service.
        
        Args:
            parent_frame: The parent frame that contains UI elements to update
        """
        self.parent = parent_frame
        self.observer = None
        self.event_handler = None
        self.monitoring = False
        
        # Subscribe to environment change events (MULTI-ENV-LOG-001 Fase 4)
        message_bus.on("environment_changed", self._on_environment_changed)
        
    def start_monitoring(self, delay_ms=0):
        """
        Start log file monitoring.
        
        Args:
            delay_ms (int): Delay in milliseconds before starting the monitoring
        """
        if self.monitoring:  # Prevent starting monitoring if already active
            return
            
        self.monitoring = True  # Update monitoring state here
        self.parent.SetStatusText("Preparing to monitor log file...")
        
        # Use the default log file path from the configuration
        log_file = self.parent.default_log_file_path
        if not log_file:
            wx.MessageBox("Log file path is not set in the configuration.", "Error", wx.OK | wx.ICON_ERROR)
            self.monitoring = False
            return

        # Get parameters from configuration manager (source of truth)
        process_all = True  # Always process the entire log
        use_discord = self.parent.config_manager.get('use_discord', True)
        datasource = self.parent.config_manager.get('datasource', 'googlesheets')
        
        # Delay the start of monitoring to ensure UI is fully loaded
        if delay_ms > 0:
            wx.CallLater(delay_ms, self._start_monitoring_thread, log_file, process_all, 
                        use_discord, datasource)
            # Use message bus instead of direct AppendText
            message_bus.publish(
                content=f"Monitoring will start in {delay_ms/1000:.1f} seconds...",
                level=MessageLevel.INFO
            )
        else:
            self._start_monitoring_thread(log_file, process_all, use_discord, datasource)
        self.update_monitoring_buttons()

    def _start_monitoring_thread(self, log_file, process_all, use_discord, datasource):
        """
        Start the actual monitoring thread after any delay.
        
        Args:
            log_file (str): Path to the log file to monitor
            process_all (bool): Whether to process the entire log
            use_discord (bool): Whether to use Discord integration
            datasource (str): The datasource to use ('googlesheets' or 'supabase')
        """
        if not self.monitoring:  # Check if monitoring was canceled during delay
            return
            
        # Use message bus instead of direct AppendText
        message_bus.publish(
            content="Starting log monitoring...",
            level=MessageLevel.INFO
        )
        
        # Run in a separate thread to keep UI responsive
        thread = threading.Thread(
            target=self.run_monitoring, 
            args=(log_file, process_all, use_discord, datasource)
        )
        thread.daemon = True
        thread.start()
    
    def run_monitoring(self, log_file, process_all, use_discord, datasource):
        """
        Run monitoring in a separate thread.
        
        Args:
            log_file (str): Path to the log file to monitor
            process_all (bool): Whether to process the entire log
            use_discord (bool): Whether to use Discord integration
            datasource (str): The datasource to use ('googlesheets' or 'supabase')
        """
        try:
            # Start continuous environment monitoring if enabled
            self.parent.config_manager.start_environment_monitoring()
            
            # Get the log file path (environment detection will happen in log_analyzer.startup)
            updated_log_file = self.parent.config_manager.get('log_file_path', log_file)
            
            # Call startup without passing event subscriptions
            result = log_analyzer.startup(
                process_all=process_all,
                use_discord=use_discord,
                process_once=False,
                datasource=datasource,
                log_file_path=updated_log_file
            )

            if result:
                self.event_handler, self.observer = result
                wx.CallAfter(self.parent.update_dynamic_labels)  # Update labels after starting monitoring

                # Start the observer thread explicitly
                if self.observer:
                    self.observer.start()

        except Exception as e:
            wx.CallAfter(lambda e=e: message_bus.publish(
                content=f"Error starting monitoring: {e}",
                level=MessageLevel.ERROR
            ))
            self.monitoring = False
            wx.CallAfter(self.parent.monitoring_service.update_monitoring_buttons)
    
    def stop_monitoring(self):
        """Stop log file monitoring."""
        if not self.monitoring:  # Prevent stopping monitoring if not active
            return
            
        if self.event_handler and self.observer:
            log_analyzer.stop_monitor(self.event_handler, self.observer)
            self.event_handler = None
            self.observer = None
        
        # Stop environment monitoring thread
        self.parent.config_manager.stop_environment_monitoring()
        
        self.monitoring = False  # Ensure monitoring state is updated
        wx.CallAfter(self.update_monitoring_buttons)

    def is_monitoring(self):
        """
        Check if monitoring is currently active.
        
        Returns:
            bool: True if monitoring is active, False otherwise
        """
        return self.monitoring
    
    def _on_environment_changed(self, old_env, new_env, new_path):
        """
        Handle environment change events by restarting the log file handler.
        
        Args:
            old_env (str): The previous environment name
            new_env (str): The new environment name
            new_path (str): The new log file path
        """
        if self.monitoring and self.event_handler and self.observer:
            try:
                message_bus.publish(
                    content=f"Environment changed from {old_env} to {new_env}, restarting log monitoring with {new_path}",
                    level=MessageLevel.INFO
                )
                
                # Store current monitoring parameters
                process_all = True
                use_discord = self.parent.config_manager.get('use_discord', True)
                datasource = self.parent.config_manager.get('datasource', 'googlesheets')
                
                # Stop current monitoring
                log_analyzer.stop_monitor(self.event_handler, self.observer)
                self.event_handler = None
                self.observer = None
                
                # Restart monitoring with new path
                self.run_monitoring(new_path, process_all, use_discord, datasource)
                
            except Exception as e:
                message_bus.publish(
                    content=f"Error restarting monitoring after environment change: {e}",
                    level=MessageLevel.ERROR
                )
        
    def update_monitoring_buttons(self):
        """
        Update the state of the monitoring and process buttons.

        Args:
            started (bool): True if monitoring has started, False otherwise.
        """
        if self.monitoring:  # Check the actual monitoring state
            self.parent.monitor_button.SetLabel("⏹️ Stop")
            self.parent.process_log_button.Enable(False)
            self.parent.SetStatusText("Monitoring active")
        else:
            self.parent.monitor_button.SetLabel("▶ Start")
            self.parent.process_log_button.Enable(True)
            self.parent.SetStatusText("Monitoring stopped")
    
    def run_process_log(self, log_file):
        """
        Run log processing.
        
        Args:
            log_file (str): Path to the log file to process
        """
        if not self.parent or not self.parent.IsShown():
            return  # Prevent actions if the frame is destroyed
            
        if self.monitoring:
            wx.MessageBox("Stop monitoring first before processing log", "Cannot Process", wx.OK | wx.ICON_INFORMATION)
            return
        
        self.parent.log_text.Clear()
        self.parent.SetStatusText("Processing log file...")
        
        # Disable buttons during processing
        self.parent.process_log_button.Enable(False)
        self.parent.monitor_button.Enable(False)
        
        # Get parameters from configuration manager (source of truth)
        use_discord = self.parent.config_manager.get('use_discord', False)
        datasource = self.parent.config_manager.get('datasource', 'googlesheets')
        
        thread = threading.Thread(
            target=self.run_process_log_thread, 
            args=(log_file, True, use_discord, datasource)
        )
        thread.daemon = True
        thread.start()

    def run_process_log_thread(self, log_file, process_all, use_discord, datasource):
        """
        Run log analysis in thread.
        
        Args:
            log_file (str): Path to the log file to process
            process_all (bool): Whether to process the entire log
            use_discord (bool): Whether to use Discord integration
            datasource (str): The datasource to use ('googlesheets' or 'supabase')
        """
        try:
            # Call main with process_once=True
            log_analyzer.main(
                process_all=process_all,
                use_discord=use_discord,
                process_once=True,
                datasource=datasource,
                log_file_path=log_file
            )
            wx.CallAfter(self.parent.SetStatusText, "Processing completed")
        except Exception as e:
            # Use message bus instead of direct AppendText
            wx.CallAfter(lambda e=e: message_bus.publish(
                content=f"Error processing log: {e}",
                level=MessageLevel.ERROR
            ))
            wx.CallAfter(self.parent.SetStatusText, "Error during processing")
        finally:
            wx.CallAfter(self.parent.process_log_button.Enable, True)
            wx.CallAfter(self.parent.monitor_button.Enable, True)