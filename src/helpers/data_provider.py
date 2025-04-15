import requests
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from .message_bus import message_bus, MessageLevel
from .supabase_manager import supabase_manager

class DataProvider(ABC):
    """
    Abstract base class for data providers (Google Sheets or Supabase).
    """
    @abstractmethod
    def insert_data(self, data: Dict[str, Any], table_name: str) -> bool:
        """
        Insert data into the specified table.
        
        Args:
            data: Dictionary containing the data to insert
            table_name: The name of the table/sheet to insert into
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def fetch_data(self, table_name: str, username: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch data from the specified table.
        
        Args:
            table_name: The name of the table/sheet to fetch from
            username: Optional username filter
            
        Returns:
            List of dictionaries containing the fetched data
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if the provider is connected.
        
        Returns:
            bool: True if connected, False otherwise
        """
        pass
        

class GoogleSheetsDataProvider(DataProvider):
    """
    Data provider for Google Sheets.
    """
    def __init__(self, webhook_url: str):
        """
        Initialize the Google Sheets data provider.
        
        Args:
            webhook_url: The Google Sheets webhook URL
        """
        self.webhook_url = webhook_url
        
    def insert_data(self, data: Dict[str, Any], table_name: str) -> bool:
        """
        Insert data into Google Sheets using the webhook.
        
        Args:
            data: Dictionary containing the data to insert
            table_name: The sheet name to insert into
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.webhook_url:
            self._log_message("Google Sheets webhook URL is not set", "ERROR")
            return False
        
        try:
            # Ensure the sheet parameter is set
            if 'sheet' not in data:
                data['sheet'] = table_name
                
            # Send the data to Google Sheets via webhook
            response = requests.post(self.webhook_url, json=data)
            
            if response.status_code == 200:
                self._log_message(f"Data sent to Google Sheets successfully", "INFO")
                return True
            else:
                self._log_message(f"Error sending data to Google Sheets: HTTP {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self._log_message(f"Exception sending data to Google Sheets: {e}", "ERROR")
            return False
    
    def fetch_data(self, table_name: str, username: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch data from Google Sheets.
        
        Args:
            table_name: The sheet name to fetch from
            username: Optional username filter
            
        Returns:
            List of dictionaries containing the fetched data
        """
        if not self.webhook_url:
            self._log_message("Google Sheets webhook URL is not set", "ERROR")
            return []
            
        try:
            # Prepare query parameters
            params = {"sheet": table_name}
            if username:
                params["username"] = username
                
            # Get data from Google Sheets
            response = requests.get(self.webhook_url, params=params)
            
            if response.status_code != 200:
                self._log_message(f"Failed to fetch data from Google Sheets. HTTP Status: {response.status_code}", "ERROR")
                return []
                
            # Parse the JSON response
            data = response.json()
            if not isinstance(data, list):
                self._log_message("Invalid data format received from Google Sheets", "ERROR")
                return []
                
            return data
        except requests.RequestException as e:
            self._log_message(f"Network error while fetching data from Google Sheets: {e}", "ERROR")
            return []
        except json.JSONDecodeError:
            self._log_message("Failed to decode JSON response from Google Sheets", "ERROR")
            return []
        except Exception as e:
            self._log_message(f"Unexpected error fetching data from Google Sheets: {e}", "ERROR")
            return []
    
    def is_connected(self) -> bool:
        """
        Check if Google Sheets provider is connected.
        
        Returns:
            bool: True if webhook URL is set, False otherwise
        """
        return bool(self.webhook_url)
    
    def _log_message(self, content, level="INFO"):
        """Send message through the message bus"""
        level_map = {
            "DEBUG": MessageLevel.DEBUG,
            "INFO": MessageLevel.INFO,
            "WARNING": MessageLevel.WARNING,
            "ERROR": MessageLevel.ERROR,
            "CRITICAL": MessageLevel.CRITICAL
        }
        msg_level = level_map.get(level.upper(), MessageLevel.INFO)
        
        message_bus.publish(
            content=content,
            level=msg_level,
            metadata={"source": "google_sheets_provider"}
        )
        

class SupabaseDataProvider(DataProvider):
    """
    Data provider for Supabase.
    """
    def __init__(self):
        """Initialize the Supabase data provider."""
        pass
        
    def insert_data(self, data: Dict[str, Any], table_name: str) -> bool:
        """
        Insert data into Supabase.
        
        Args:
            data: Dictionary containing the data to insert
            table_name: The table name to insert into
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not supabase_manager.is_connected():
            return False
            
        # Data already has the necessary information for insert_log
        # Just ensure the sheet parameter is set
        if 'sheet' not in data and table_name:
            data['sheet'] = table_name
            
        return supabase_manager.insert_log(data)
    
    def fetch_data(self, table_name: str, username: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch data from Supabase.
        
        Args:
            table_name: The table name to fetch from
            username: Optional username filter
            
        Returns:
            List of dictionaries containing the fetched data
        """
        if not supabase_manager.is_connected():
            return []
            
        try:
            # Sanitize the table name to match how it would be stored
            sanitized_table = supabase_manager._sanitize_table_name(table_name)
            
            # Build the query
            query = supabase_manager.supabase.table(sanitized_table)
            
            # Add username filter if provided
            if username:
                query = query.eq('username', username)
                
            # Order by most recent first (if created_at column exists)
            try:
                result = query.order('created_at', desc=True).execute()
            except:
                # If ordering by created_at fails, try without ordering
                result = query.execute()
                
            # Extract the data from the result
            if hasattr(result, 'data'):
                return result.data
            return []
        except Exception as e:
            self._log_message(f"Error fetching data from Supabase: {e}", "ERROR")
            return []
    
    def is_connected(self) -> bool:
        """
        Check if Supabase provider is connected.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return supabase_manager.is_connected()
    
    def _log_message(self, content, level="INFO"):
        """Send message through the message bus"""
        level_map = {
            "DEBUG": MessageLevel.DEBUG,
            "INFO": MessageLevel.INFO,
            "WARNING": MessageLevel.WARNING,
            "ERROR": MessageLevel.ERROR,
            "CRITICAL": MessageLevel.CRITICAL
        }
        msg_level = level_map.get(level.upper(), MessageLevel.INFO)
        
        message_bus.publish(
            content=content,
            level=msg_level,
            metadata={"source": "supabase_provider"}
        )


def get_data_provider(config_manager) -> DataProvider:
    """
    Factory function to get the appropriate data provider based on configuration.
    
    Args:
        config_manager: The configuration manager instance
        
    Returns:
        A DataProvider instance
    """
    use_supabase = config_manager.get('use_supabase', False)
    
    if use_supabase and supabase_manager.is_connected():
        # Use Supabase as the data provider
        return SupabaseDataProvider()
    else:
        # Fall back to Google Sheets
        google_sheets_webhook = config_manager.get('google_sheets_webhook', '')
        return GoogleSheetsDataProvider(google_sheets_webhook)