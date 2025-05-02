import wx
import wx.adv
import threading
import time
import pyperclip
from typing import Callable, Optional

from .message_bus import message_bus, MessageLevel
from .supabase_manager import supabase_manager
from .config_utils import get_config_manager

class SupabaseOnboarding:
    """
    Handles the onboarding process for new Supabase connections.
    Only runs when switching from googlesheets to supabase in the config.
    """
    SOURCE = "supabase_onboarding"
    
    def __init__(self, parent_window):
        """Initialize the Supabase onboarding process."""
        self.parent = parent_window
        self.config_manager = get_config_manager()
        
        # SQL for run_sql function (extracted from supbase_functions.sql)
        self.run_sql_code = """
CREATE OR REPLACE FUNCTION public.run_sql(query text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
      EXECUTE query;
END;
$function$
;
"""
    
    def check_onboarding_needed(self) -> bool:
        """Check if onboarding is needed when switching to Supabase."""
        if not supabase_manager.is_connected():
            if not supabase_manager.connect():
                message_bus.publish(
                    content="Cannot connect to Supabase",
                    level=MessageLevel.WARNING,
                    metadata={"source": self.SOURCE}
                )
                return False
        
        # Check if run_sql function exists
        try:
            # Try to call run_sql with a simple query to test if it exists
            result = supabase_manager.supabase.rpc(
                'run_sql', 
                {'query': 'SELECT 1'}
            ).execute()
            
            if hasattr(result, 'error') and result.error:
                message_bus.publish(
                    content="run_sql function not found, onboarding needed",
                    level=MessageLevel.INFO,
                    metadata={"source": self.SOURCE}
                )
                return True
            
            # Function exists, no onboarding needed
            return False
            
        except Exception:
            # If we get an exception, assume onboarding is needed
            return True
    
    def start_onboarding(self) -> bool:
        """Show onboarding dialog and guide user through setup process."""
        # Show SQL setup dialog with the run_sql code
        setup_dialog = SupabaseSetupDialog(
            self.parent,
            sql_code=self.run_sql_code
        )
        
        if setup_dialog.ShowModal() != wx.ID_OK:
            # User cancelled, revert to Google Sheets
            message_bus.publish(
                content="Supabase onboarding cancelled by user, reverting to Google Sheets",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
            self._switch_to_google_sheets()
            return False
        
        # User wants to continue, run onboarding process
        progress_dialog = wx.ProgressDialog(
            "Supabase Onboarding",
            "Starting Supabase setup...",
            maximum=100,
            parent=self.parent,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME
        )
        
        try:
            # Phase 1: Wait for user to create the run_sql function
            progress_dialog.Update(20, "Checking for run_sql function...")
            
            # Test if the run_sql function is available
            run_sql_exists = self._test_run_sql()
            
            if not run_sql_exists:
                progress_dialog.Update(30, 
                    "Please create the run_sql function in your Supabase dashboard.\n"
                    "We'll check again in a few seconds..."
                )
                
                # Give the user time to create the function
                for i in range(5):  # Try 5 times
                    time.sleep(2)  # Wait 2 seconds between attempts
                    run_sql_exists = self._test_run_sql()
                    
                    if run_sql_exists:
                        progress_dialog.Update(50, "run_sql function detected! Continuing setup...")
                        break
                    
                    cont, skip = progress_dialog.Update(30 + (i * 4), 
                        f"Waiting for run_sql function... (Attempt {i+1}/5)"
                    )
                    
                    if not cont:  # User pressed Cancel
                        self._switch_to_google_sheets()
                        progress_dialog.Destroy()
                        return False
                
                if not run_sql_exists:
                    wx.MessageBox(
                        "The run_sql function was not detected after multiple attempts.\n"
                        "Reverting to Google Sheets datasource.",
                        "Setup Failed",
                        wx.OK | wx.ICON_WARNING
                    )
                    self._switch_to_google_sheets()
                    progress_dialog.Destroy()
                    return False
            
            # Phase 2: Create list_tables function using run_sql
            progress_dialog.Update(60, "Creating list_tables function...")
            
            # Create the list_tables function
            self._create_list_tables_function()
            
            # Keep checking for list_tables function until it's available or user cancels
            attempt = 0
            retry_delay = 1.5  # Start with 1.5 seconds
            list_tables_available = False

            while not list_tables_available:
                # Update progress dialog with current status
                message = f"Waiting for list_tables function to be available (attempt {attempt+1})...\nThis may take some time, please be patient."
                if attempt > 0:
                    message += "\nPress Cancel to abort and revert to Google Sheets."
                
                cont, skip = progress_dialog.Update(70, message)
                
                if not cont:  # User pressed Cancel
                    if wx.MessageBox(
                        "Do you want to cancel the Supabase setup and revert to Google Sheets?",
                        "Confirm Cancellation",
                        wx.YES_NO | wx.ICON_QUESTION
                    ) == wx.YES:
                        self._switch_to_google_sheets()
                        progress_dialog.Destroy()
                        return False
                
                # Test if the list_tables function is available
                if self._test_list_tables():
                    list_tables_available = True
                    message_bus.publish(
                        content=f"list_tables function available after {attempt+1} attempt(s)",
                        level=MessageLevel.INFO,
                        metadata={"source": self.SOURCE}
                    )
                    break
                
                # Log retry attempt
                message_bus.publish(
                    content=f"list_tables not available yet, retrying (attempt {attempt+1})...",
                    level=MessageLevel.INFO,
                    metadata={"source": self.SOURCE}
                )
                
                # Increase delay with exponential backoff but cap at 10 seconds
                retry_delay = min(retry_delay * 1.2, 10.0)
                attempt += 1
                
                # Wait before retrying
                time.sleep(retry_delay)
            
            progress_dialog.Update(80, "list_tables function is available! Testing it...")
            
            # Phase 3: Create Config table if it doesn't exist
            progress_dialog.Update(90, "Creating Config table if needed...")
            
            if not self._create_config_table():
                wx.MessageBox(
                    "Failed to create the Config table.\n"
                    "Reverting to Google Sheets datasource.",
                    "Setup Failed",
                    wx.OK | wx.ICON_WARNING
                )
                self._switch_to_google_sheets()
                progress_dialog.Destroy()
                return False
            
            # Onboarding completed successfully
            progress_dialog.Update(100, "Supabase setup completed successfully!")
            time.sleep(1)  # Brief pause to show success message
            
            wx.MessageBox(
                "Supabase setup completed successfully! You can now use Supabase as your data provider.",
                "Setup Complete",
                wx.OK | wx.ICON_INFORMATION
            )
            
            progress_dialog.Destroy()
            return True
            
        except Exception as e:
            message_bus.publish(
                content=f"Error during Supabase onboarding: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            progress_dialog.Destroy()
            
            wx.MessageBox(
                f"An error occurred during Supabase setup: {str(e)}\n"
                "Reverting to Google Sheets datasource.",
                "Setup Error",
                wx.OK | wx.ICON_ERROR
            )
            
            self._switch_to_google_sheets()
            return False
    
    def _test_run_sql(self) -> bool:
        """Test if the run_sql function exists and works."""
        try:
            result = supabase_manager.supabase.rpc(
                'run_sql', 
                {'query': 'SELECT 1'}
            ).execute()
            
            # If there's an error, the function doesn't exist or isn't working
            if hasattr(result, 'error') and result.error:
                return False
                
            # Function exists and works
            return True
            
        except Exception:
            return False
    
    def _create_list_tables_function(self) -> bool:
        """Create the list_tables function using run_sql."""
        if not self._test_run_sql():
            return False
        
        try:
            # SQL to create list_tables function
            list_tables_sql = """
CREATE OR REPLACE FUNCTION public.list_tables()
 RETURNS TABLE(table_name text)
 LANGUAGE sql
AS $function$
    select table_name
    from information_schema.tables
    where table_schema = 'public';
$function$
;
"""
            # Call run_sql to create the function
            result = supabase_manager.supabase.rpc(
                'run_sql', 
                {'query': list_tables_sql}
            ).execute()
            
            if hasattr(result, 'error') and result.error:
                message_bus.publish(
                    content=f"Failed to create list_tables function: {result.error}",
                    level=MessageLevel.ERROR,
                    metadata={"source": self.SOURCE}
                )
                return False
            
            # Add retry logic to verify the function is available
            message_bus.publish(
                content="Waiting for list_tables function to be available...",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
            
            # Give the database some time to make the function available
            max_retries = 5
            retry_delay = 1.5  # Start with 1.5 seconds
            
            for attempt in range(max_retries):
                # Exponential backoff for retries
                if attempt > 0:
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Increase delay with each attempt
                
                # Test if the function is available
                if self._test_list_tables():
                    message_bus.publish(
                        content=f"list_tables function available after {attempt+1} attempt(s)",
                        level=MessageLevel.INFO,
                        metadata={"source": self.SOURCE}
                    )
                    return True
                
                message_bus.publish(
                    content=f"list_tables not available yet, retrying ({attempt+1}/{max_retries})...",
                    level=MessageLevel.INFO,
                    metadata={"source": self.SOURCE}
                )
            
            # Final check after all retries
            if self._test_list_tables():
                return True
                
            message_bus.publish(
                content=f"list_tables function not available after {max_retries} attempts",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return False
            
        except Exception as e:
            message_bus.publish(
                content=f"Error creating list_tables function: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return False
    
    def _test_list_tables(self) -> bool:
        """Test if the list_tables function works."""
        try:
            result = supabase_manager.supabase.rpc('list_tables').execute()
            
            # If there's an error, the function doesn't exist or isn't working
            if hasattr(result, 'error') and result.error:
                return False
                
            # Function exists and works
            return True
            
        except Exception:
            return False
    
    def _create_config_table(self) -> bool:
        """Create the config table if it doesn't exist."""
        try:
            # Check if the table already exists
            result = supabase_manager.supabase.rpc('list_tables').execute()
            
            if hasattr(result, 'data') and result.data:
                table_list = [table['table_name'] for table in result.data if 'table_name' in table]
                if 'config' in table_list:
                    return True  # Table already exists
            
            # Create the table
            sample_data = {
                "key": "sample_key",
                "value": "sample_value"
            }
            
            if supabase_manager._create_table("config", sample_data):
                return True
            return False
            
        except Exception as e:
            message_bus.publish(
                content=f"Error creating config table: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return False
    
    def _switch_to_google_sheets(self):
        """Switch datasource back to Google Sheets."""
        try:
            self.config_manager.set('datasource', 'googlesheets')
            self.config_manager.save_config()
            message_bus.publish(
                content="Switched data provider to Google Sheets",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
        except Exception as e:
            message_bus.publish(
                content=f"Error switching to Google Sheets: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )


class SupabaseSetupDialog(wx.Dialog):
    """Dialog that explains the Supabase setup process."""
    def __init__(self, parent, sql_code: str):
        super().__init__(
            parent,
            title="Supabase Setup Required",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self.sql_code = sql_code
        
        # Create controls
        info_text = wx.StaticText(
            self, 
            label=(
                "Your Supabase project needs additional setup before it can be used.\n\n"
                "You need to create the run_sql function in your Supabase SQL editor:\n"
                "1. Copy the SQL code below\n"
                "2. Open your Supabase dashboard\n"
                "3. Go to the SQL Editor\n"
                "4. Paste the code and run it\n"
                "5. Return here and click Continue"
            )
        )
        
        # SQL code text box
        self.code_textctrl = wx.TextCtrl(
            self,
            value=self.sql_code,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        
        # Set monospace font for code
        font = wx.Font(
            9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
        )
        self.code_textctrl.SetFont(font)
        
        # Buttons
        self.copy_btn = wx.Button(self, label="Copy to Clipboard")
        self.continue_btn = wx.Button(self, id=wx.ID_OK, label="Continue")
        self.cancel_btn = wx.Button(self, id=wx.ID_CANCEL, label="Cancel")
        
        # Bind events
        self.copy_btn.Bind(wx.EVT_BUTTON, self._on_copy)
        
        # Layout
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Info section
        main_sizer.Add(info_text, flag=wx.ALL | wx.EXPAND, border=10)
        
        # SQL code section
        main_sizer.Add(
            wx.StaticText(self, label="SQL Code:"),
            flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10
        )
        main_sizer.Add(
            self.code_textctrl, proportion=1,
            flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10
        )
        
        # Buttons section
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.copy_btn, flag=wx.RIGHT, border=5)
        button_sizer.Add(self.continue_btn, flag=wx.RIGHT, border=5)
        button_sizer.Add(self.cancel_btn)
        
        main_sizer.Add(button_sizer, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
        
        # Set sizer and size
        self.SetSizer(main_sizer)
        self.SetMinSize((500, 400))
        self.SetSize((600, 500))
        self.Centre()
        
    def _on_copy(self, event):
        """Copy the SQL code to clipboard."""
        try:
            pyperclip.copy(self.sql_code)
            self.copy_btn.SetLabel("Copied!")
            
            # Reset the button label after a delay
            def reset_label():
                wx.CallLater(2000, lambda: self.copy_btn.SetLabel("Copy to Clipboard"))
            
            reset_label()
            
        except Exception as e:
            wx.MessageBox(
                f"Failed to copy to clipboard: {e}",
                "Copy Error",
                wx.OK | wx.ICON_ERROR
            )


def check_needs_onboarding(config_manager):
    """
    Check if Supabase needs onboarding.
    This should be called when the datasource is changed to 'supabase'.
    
    Args:
        config_manager: The configuration manager instance
        
    Returns:
        bool: True if onboarding is needed, False otherwise
    """
    if config_manager.get('datasource') != 'supabase':
        return False
    
    supabase_key = config_manager.get('supabase_key')
    if not supabase_key:
        return False
    
    # Connect to Supabase with the key
    from .supabase_manager import supabase_manager
    if not supabase_manager.is_connected() or supabase_manager.supabase_key != supabase_key:
        if not supabase_manager.connect(config_manager):
            # Can't connect to Supabase at all, likely invalid key
            return False
    
    # Now check if onboarding is needed by testing if the run_sql function exists
    try:
        result = supabase_manager.supabase.rpc(
            'run_sql', 
            {'query': 'SELECT 1'}
        ).execute()
        
        # If there's an error, the function doesn't exist - onboarding IS needed
        if hasattr(result, 'error') and result.error:
            return True
            
        # Function exists and works, no onboarding needed
        return False
    except Exception:
        # If we get an exception, assume onboarding is needed
        return True