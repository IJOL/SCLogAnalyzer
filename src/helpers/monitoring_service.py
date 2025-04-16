#!/usr/bin/env python
import threading
import os
import wx
import time
from watchdog.observers.polling import PollingObserver as Observer
import log_analyzer
from .message_bus import message_bus, MessageLevel

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

        process_all = True  # Always process the entire log
        use_discord = self.parent.discord_check.IsChecked()
        use_googlesheet = self.parent.googlesheet_check.IsChecked()
        use_supabase = self.parent.supabase_check.IsChecked()
        
        # Delay the start of monitoring to ensure UI is fully loaded
        if delay_ms > 0:
            wx.CallLater(delay_ms, self._start_monitoring_thread, log_file, process_all, 
                        use_discord, use_googlesheet, use_supabase)
            # Use message bus instead of direct AppendText
            message_bus.publish(
                content=f"Monitoring will start in {delay_ms/1000:.1f} seconds...",
                level=MessageLevel.INFO
            )
        else:
            self._start_monitoring_thread(log_file, process_all, use_discord, use_googlesheet, use_supabase)
    
    def _start_monitoring_thread(self, log_file, process_all, use_discord, use_googlesheet, use_supabase):
        """
        Start the actual monitoring thread after any delay.
        
        Args:
            log_file (str): Path to the log file to monitor
            process_all (bool): Whether to process the entire log
            use_discord (bool): Whether to use Discord integration
            use_googlesheet (bool): Whether to use Google Sheets integration
            use_supabase (bool): Whether to use Supabase integration
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
            args=(log_file, process_all, use_discord, use_googlesheet, use_supabase)
        )
        thread.daemon = True
        thread.start()
    
    def run_monitoring(self, log_file, process_all, use_discord, use_googlesheet, use_supabase):
        """
        Run monitoring in a separate thread.
        
        Args:
            log_file (str): Path to the log file to monitor
            process_all (bool): Whether to process the entire log
            use_discord (bool): Whether to use Discord integration
            use_googlesheet (bool): Whether to use Google Sheets integration
            use_supabase (bool): Whether to use Supabase integration
        """
        try:
            # Call startup with event subscriptions passed as kwargs
            result = log_analyzer.startup(
                process_all=process_all,
                use_discord=use_discord,
                process_once=False,
                use_googlesheet=use_googlesheet,
                use_supabase=use_supabase,
                log_file_path=log_file,
                on_shard_version_update=self.parent.on_shard_version_update,
                on_mode_change=self.parent.on_mode_change,
                on_username_change=self.parent.on_username_change,
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
            wx.CallAfter(self.parent.monitoring_service.update_monitoring_buttons, False)
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
        
    def is_monitoring(self):
        """
        Check if monitoring is currently active.
        
        Returns:
            bool: True if monitoring is active, False otherwise
        """
        return self.monitoring
        
    def update_monitoring_buttons(self, started):
        """
        Update the state of the monitoring and process buttons.

        Args:
            started (bool): True if monitoring has started, False otherwise.
        """
        if self.monitoring:  # Check the actual monitoring state
            self.parent.monitor_button.SetLabel("Stop Monitoring")
            self.parent.process_log_button.Enable(False)
            self.parent.SetStatusText("Monitoring active")
        else:
            self.parent.monitor_button.SetLabel("Start Monitoring")
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
        
        thread = threading.Thread(
            target=self.run_process_log_thread, 
            args=(log_file, True, False, False)
        )
        thread.daemon = True
        thread.start()

    def run_process_log_thread(self, log_file, process_all, use_discord, use_googlesheet):
        """
        Run log analysis in thread.
        
        Args:
            log_file (str): Path to the log file to process
            process_all (bool): Whether to process the entire log
            use_discord (bool): Whether to use Discord integration
            use_googlesheet (bool): Whether to use Google Sheets integration
        """
        try:
            # Call main with process_once=True
            log_analyzer.main(
                process_all=process_all,
                use_discord=use_discord,
                process_once=True,
                use_googlesheet=use_googlesheet,
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