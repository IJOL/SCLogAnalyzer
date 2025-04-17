import requests
import json
import time
import traceback
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, Union
from .message_bus import message_bus, MessageLevel
from .supabase_manager import supabase_manager

class DataProvider(ABC):
    """
    Abstract base class for data providers (Google Sheets or Supabase).
    """
    SOURCE = "data_provider"
    
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
    
    @abstractmethod
    def process_data(self, batch: List[Dict[str, Any]]) -> bool:
        """
        Process a batch of data items.
        
        Args:
            batch: List of dictionaries with 'data' and 'sheet' keys
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def fetch_config(self) -> Dict[str, Any]:
        """
        Fetch configuration data from the data source.
        
        Returns:
            Dict[str, Any]: Dictionary of configuration key-value pairs
        """
        pass
        

class GoogleSheetsDataProvider(DataProvider):
    """
    Data provider for Google Sheets.
    """
    SOURCE = "google_sheets_provider"
    
    def __init__(self, webhook_url: str, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the Google Sheets data provider.
        
        Args:
            webhook_url: The Google Sheets webhook URL
            max_retries: Maximum number of retry attempts for failed operations
            retry_delay: Delay in seconds between retry attempts
        """
        self.webhook_url = webhook_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session = None
            
    @property
    def session(self):
        """Lazy initialization of requests session"""
        if self._session is None:
            self._session = requests.Session()
        return self._session
            
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
            message_bus.publish(
                content="Google Sheets webhook URL is not set",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return []
            
        # Prepare query parameters
        params = {}
        if table_name:
            params["sheet"] = table_name
        if username:
            params["username"] = username
            
        return self._make_request("GET", params=params)
    
    def _make_request(self, method: str, params: Dict = None, data: Any = None) -> List[Dict[str, Any]]:
        """
        Make an HTTP request to the Google Sheets webhook with retry logic.
        
        Args:
            method: HTTP method (GET, POST)
            params: URL parameters for the request
            data: JSON data for POST requests
            
        Returns:
            List of dictionaries with the response data or empty list on failure
        """
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                message_bus.publish(
                    content=f"Making {method} request to Google Sheets (attempt {attempt+1}/{self.max_retries})",
                    level=MessageLevel.DEBUG,
                    metadata={"source": self.SOURCE}
                )
                
                if method.upper() == "GET":
                    response = self.session.get(self.webhook_url, params=params, timeout=10)
                else:  # POST
                    response = self.session.post(self.webhook_url, json=data, timeout=10)
                
                if response.status_code not in [200, 201, 204]:
                    message_bus.publish(
                        content=f"Request failed with status {response.status_code}: {response.text[:100]}",
                        level=MessageLevel.WARNING,
                        metadata={"source": self.SOURCE}
                    )
                    last_error = f"HTTP {response.status_code}"
                    attempt += 1
                    time.sleep(self.retry_delay)
                    continue
                
                try:
                    result = response.json() if response.content and method.upper() == "GET" else [1]
                    if isinstance(result, list):
                        message_bus.publish(
                            content=f"Successfully processed {len(result)} records from Google Sheets",
                            level=MessageLevel.DEBUG,
                            metadata={"source": self.SOURCE}
                        )
                        return result
                    else:
                        message_bus.publish(
                            content=f"Unexpected response format: {type(result).__name__}",
                            level=MessageLevel.WARNING,
                            metadata={"source": self.SOURCE}
                        )
                        return []
                except json.JSONDecodeError:
                    message_bus.publish(
                        content=f"Invalid JSON response: {response.text[:100]}",
                        level=MessageLevel.ERROR,
                        metadata={"source": self.SOURCE}
                    )
                    return []
                    
            except requests.RequestException as e:
                last_error = str(e)
                message_bus.publish(
                    content=f"Network error (attempt {attempt+1}/{self.max_retries}): {e}",
                    level=MessageLevel.WARNING,
                    metadata={"source": self.SOURCE}
                )
            except Exception as e:
                last_error = str(e)
                message_bus.publish(
                    content=f"Unexpected error (attempt {attempt+1}/{self.max_retries}): {e}",
                    level=MessageLevel.ERROR,
                    metadata={"source": self.SOURCE}
                )
                message_bus.publish(
                    content=traceback.format_exc(),
                    level=MessageLevel.DEBUG,
                    metadata={"source": self.SOURCE}
                )
            
            # Increment attempt counter and delay before retry
            attempt += 1
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        
        # All attempts failed
        message_bus.publish(
            content=f"All {self.max_retries} attempts failed: {last_error}",
            level=MessageLevel.ERROR,
            metadata={"source": self.SOURCE}
        )
        return []
    
    def is_connected(self) -> bool:
        """
        Check if Google Sheets provider is connected.
        
        Returns:
            bool: True if webhook URL is set, False otherwise
        """
        return bool(self.webhook_url)
    
    def process_data(self, batch: List[Dict[str, Any]]) -> bool:
        """
        Process a batch of data for Google Sheets.
        
        Args:
            batch: List of dictionaries with 'data' and 'sheet' keys
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        if not batch:
            return True  # Empty batch is considered successful
            
        try:
            # Send the batch data to Google Sheets webhook
            result = self._make_request("POST", data=batch)
            
            # Check if the request was successful (non-empty result list)
            success = len(result) > 0 if result else False
            if success:
                message_bus.publish(
                    content=f"Successfully processed batch of {len(batch)} items",
                    level=MessageLevel.INFO,
                    metadata={"source": self.SOURCE}
                )
            else:
                message_bus.publish(
                    content=f"Failed to process batch of {len(batch)} items",
                    level=MessageLevel.ERROR,
                    metadata={"source": self.SOURCE}
                )
            
            return success
        except Exception as e:
            message_bus.publish(
                content=f"Unhandled exception during batch processing: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            message_bus.publish(
                content=traceback.format_exc(),
                level=MessageLevel.DEBUG,
                metadata={"source": self.SOURCE}
            )
            return False

    def fetch_config(self) -> Dict[str, Any]:
        """
        Fetch configuration data from Google Sheets.
        
        Returns:
            Dict[str, Any]: Dictionary of configuration key-value pairs
        """
        if not self.webhook_url:
            message_bus.publish(
                content="Google Sheets webhook URL is not set",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return {}
            
        # Prepare query parameters to specifically fetch the Config sheet
        params = {"sheet": "Config"}
        
        # Make the request to get config data
        config_data = self._make_request("GET", params=params)
        if not config_data:
            message_bus.publish(
                content="No configuration data found in Google Sheets",
                level=MessageLevel.WARNING,
                metadata={"source": self.SOURCE}
            )
            return {}
            
        # Convert the list of dictionaries to a single dictionary with Key/Value pairs
        # Expecting a structure like [{"Key": "setting_name", "Value": "setting_value"}, ...]
        try:
            config_dict = {item["Key"]: item["Value"] for item in config_data if "Key" in item and "Value" in item}
            message_bus.publish(
                content=f"Successfully fetched {len(config_dict)} configuration items from Google Sheets",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
            return config_dict
        except (KeyError, TypeError) as e:
            message_bus.publish(
                content=f"Invalid config data format: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return {}


class SupabaseDataProvider(DataProvider):
    """
    Data provider for Supabase.
    """
    SOURCE = "supabase_provider"
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the Supabase data provider.
        
        Args:
            max_retries: Maximum number of retry attempts for failed operations
            retry_delay: Delay in seconds between retry attempts
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
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
            message_bus.publish(
                content="Supabase is not connected",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return []

        # Special handling for "Resumen" (summary) table
        if table_name.lower() == "resumen":
            # Check if view exists, create it if it doesn't
            if not self._ensure_resumen_view_exists():
                message_bus.publish(
                    content="Failed to create or verify Resumen view",
                    level=MessageLevel.ERROR,
                    metadata={"source": self.SOURCE}
                )
                return []
            
            # Use the view directly
            attempt = 0
            last_error = None
            
            while attempt < self.max_retries:
                try:
                    # Query the view
                    query = supabase_manager.supabase.table("resumen_view")
                    
                    # Add username filter if provided
                    if username:
                        query = query.eq('username', username)
                    
                    # Execute the query
                    result = query.execute()
                    data = result.data if hasattr(result, 'data') else []
                    message_bus.publish(
                        content=f"Successfully fetched {len(data)} records from Resumen view",
                        level=MessageLevel.DEBUG,
                        metadata={"source": self.SOURCE}
                    )
                    return data
                    
                except Exception as e:
                    last_error = str(e)
                    message_bus.publish(
                        content=f"Error fetching from Resumen view (attempt {attempt+1}/{self.max_retries}): {e}",
                        level=MessageLevel.WARNING,
                        metadata={"source": self.SOURCE}
                    )
                    message_bus.publish(
                        content=traceback.format_exc(),
                        level=MessageLevel.DEBUG,
                        metadata={"source": self.SOURCE}
                    )
                
                # Increment attempt counter and delay before retry
                attempt += 1
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
            
            # All attempts failed
            message_bus.publish(
                content=f"All {self.max_retries} attempts failed to query Resumen view: {last_error}",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return []
            
        # Standard table query for non-Resumen tables
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                # Sanitize the table name to match how it would be stored
                sanitized_table = supabase_manager._sanitize_table_name(table_name)
                
                # Build the query
                query = supabase_manager.supabase.table(sanitized_table)
                
                # Add username filter if provided
                if username:
                    query = query.eq('username', username)
                    
                # First try ordered query (by created_at)
                try:
                    result = query.order('created_at', desc=True).execute()
                    data = result.data if hasattr(result, 'data') else []
                    message_bus.publish(
                        content=f"Successfully fetched {len(data)} records from Supabase",
                        level=MessageLevel.DEBUG,
                        metadata={"source": self.SOURCE}
                    )
                    return data
                except Exception as order_error:
                    # Ordering failed, try without ordering
                    message_bus.publish(
                        content=f"Order by created_at failed, trying without: {order_error}",
                        level=MessageLevel.DEBUG,
                        metadata={"source": self.SOURCE}
                    )
                    result = query.execute()
                    data = result.data if hasattr(result, 'data') else []
                    message_bus.publish(
                        content=f"Successfully fetched {len(data)} records from Supabase (unordered)",
                        level=MessageLevel.DEBUG,
                        metadata={"source": self.SOURCE}
                    )
                    return data
                    
            except Exception as e:
                last_error = str(e)
                message_bus.publish(
                    content=f"Error fetching from Supabase (attempt {attempt+1}/{self.max_retries}): {e}",
                    level=MessageLevel.WARNING,
                    metadata={"source": self.SOURCE}
                )
                message_bus.publish(
                    content=traceback.format_exc(),
                    level=MessageLevel.DEBUG,
                    metadata={"source": self.SOURCE}
                )
            
            # Increment attempt counter and delay before retry
            attempt += 1
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        
        # All attempts failed
        message_bus.publish(
            content=f"All {self.max_retries} attempts failed: {last_error}",
            level=MessageLevel.ERROR,
            metadata={"source": self.SOURCE}
        )
        return []
        
    def _ensure_resumen_view_exists(self) -> bool:
        """
        Ensure that the Resumen view exists in the database.
        Creates it if it doesn't exist.
        
        Returns:
            bool: True if the view exists or was created successfully, False otherwise
        """
        # Check if view already exists in table cache
        if "resumen_view" in supabase_manager.existing_tables:
            return True
            
        message_bus.publish(
            content="Creating or updating Resumen view in Supabase",
            level=MessageLevel.INFO,
            metadata={"source": self.SOURCE}
        )
        
        # SQL to create the Resumen view with separate columns for SC_Default (Live) and Squadron Battle (SB)
        create_view_sql = """
        CREATE OR REPLACE VIEW resumen_view AS
        WITH filtered_sc_default AS (
            -- Only select records reported by the player themselves from SC_Default (Live)
            SELECT
                username,
                killer,
                victim
            FROM 
                sc_default
            -- Only count reports made by the player themselves
            WHERE 
                username IS NOT NULL
        ),
        
        filtered_ea_squadronbattle AS (
            -- Only select records reported by the player themselves from EA_SquadronBattle (SB)
            SELECT
                username,
                killer,
                victim
            FROM 
                ea_squadronbattle
            -- Only count reports made by the player themselves
            WHERE 
                username IS NOT NULL
        ),
        
        sc_default_stats AS (
            -- Count kills from SC_Default (Live)
            SELECT 
                username,
                COUNT(*) AS kills_live,
                0 AS deaths_live
            FROM 
                filtered_sc_default
            WHERE 
                killer = username
            GROUP BY 
                username
            
            UNION ALL
            
            -- Count deaths from SC_Default (Live)
            SELECT 
                username,
                0 AS kills_live,
                COUNT(*) AS deaths_live
            FROM 
                filtered_sc_default
            WHERE 
                victim = username
            GROUP BY 
                username
        ),
        
        ea_squadronbattle_stats AS (
            -- Count kills from EA_SquadronBattle (SB)
            SELECT 
                username,
                COUNT(*) AS kills_sb,
                0 AS deaths_sb
            FROM 
                filtered_ea_squadronbattle
            WHERE 
                killer = username
            GROUP BY 
                username
            
            UNION ALL
            
            -- Count deaths from EA_SquadronBattle (SB)
            SELECT 
                username,
                0 AS kills_sb,
                COUNT(*) AS deaths_sb
            FROM 
                filtered_ea_squadronbattle
            WHERE 
                victim = username
            GROUP BY 
                username
        ),
        
        -- Aggregate SC_Default (Live) stats
        aggregated_live_stats AS (
            SELECT 
                username,
                SUM(kills_live) AS kills_live,
                SUM(deaths_live) AS deaths_live
            FROM 
                sc_default_stats
            GROUP BY 
                username
        ),
        
        -- Aggregate EA_SquadronBattle (SB) stats
        aggregated_sb_stats AS (
            SELECT 
                username,
                SUM(kills_sb) AS kills_sb,
                SUM(deaths_sb) AS deaths_sb
            FROM 
                ea_squadronbattle_stats
            GROUP BY 
                username
        )
        
        -- Combine all stats with separate columns for each game mode
        SELECT 
            COALESCE(live.username, sb.username) AS username,
            -- Live mode stats (SC_Default)
            COALESCE(live.kills_live, 0) AS kills_live,
            COALESCE(live.deaths_live, 0) AS deaths_live,
            -- Squadron Battle stats
            COALESCE(sb.kills_sb, 0) AS kills_sb,
            COALESCE(sb.deaths_sb, 0) AS deaths_sb,
            -- Total kills and deaths across both modes
            COALESCE(live.kills_live, 0) + COALESCE(sb.kills_sb, 0) AS total_kills,
            COALESCE(live.deaths_live, 0) + COALESCE(sb.deaths_sb, 0) AS total_deaths,
            -- KDR for Live mode
            CASE 
                WHEN COALESCE(live.deaths_live, 0) = 0 THEN COALESCE(live.kills_live, 0)
                ELSE ROUND(CAST(COALESCE(live.kills_live, 0) AS NUMERIC) / 
                     NULLIF(COALESCE(live.deaths_live, 0), 0), 2)
            END AS kdr_live,
            -- KDR for Squadron Battle mode
            CASE 
                WHEN COALESCE(sb.deaths_sb, 0) = 0 THEN COALESCE(sb.kills_sb, 0)
                ELSE ROUND(CAST(COALESCE(sb.kills_sb, 0) AS NUMERIC) / 
                     NULLIF(COALESCE(sb.deaths_sb, 0), 0), 2)
            END AS kdr_sb,
            -- Overall KDR across both modes
            CASE 
                WHEN (COALESCE(live.deaths_live, 0) + COALESCE(sb.deaths_sb, 0)) = 0 
                THEN (COALESCE(live.kills_live, 0) + COALESCE(sb.kills_sb, 0))
                ELSE ROUND(CAST((COALESCE(live.kills_live, 0) + COALESCE(sb.kills_sb, 0)) AS NUMERIC) / 
                     NULLIF((COALESCE(live.deaths_live, 0) + COALESCE(sb.deaths_sb, 0)), 0), 2)
            END AS kdr_total
        FROM 
            aggregated_live_stats live
        FULL OUTER JOIN
            aggregated_sb_stats sb ON live.username = sb.username
        ORDER BY 
            total_kills DESC;
        """
        
        # Execute the SQL
        success, result = supabase_manager._execute_sql(create_view_sql)
        
        if success:
            message_bus.publish(
                content="Successfully created or updated Resumen view",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
            # Add the view to the cache
            supabase_manager.existing_tables.add("resumen_view")
            return True
        else:
            message_bus.publish(
                content=f"Failed to create Resumen view: {result}",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return False

    def fetch_config(self) -> Dict[str, Any]:
        """
        Fetch configuration data from Supabase.
        
        Returns:
            Dict[str, Any]: Dictionary of configuration key-value pairs
        """
        if not supabase_manager.is_connected():
            message_bus.publish(
                content="Supabase is not connected",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return {}
        
        # Connect to the 'config' table in Supabase
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                # Use sanitized table name for config table
                config_table = supabase_manager._sanitize_table_name("Config")
                
                # Check if the config table exists
                if config_table not in supabase_manager.existing_tables:
                    # Table doesn't exist, we'll need to create it
                    message_bus.publish(
                        content=f"Config table '{config_table}' does not exist in Supabase, creating it",
                        level=MessageLevel.INFO,
                        metadata={"source": self.SOURCE}
                    )
                    
                    # Prepare sample data structure for table creation
                    sample_data = {
                        "key": "sample_key",
                        "value": "sample_value"
                    }
                    
                    # Define RLS policies for the config table
                    rls_policies = [
                        {
                            "name": "Allow read access to config",
                            "action": "SELECT",
                            "using": "true"
                        },
                        {
                            "name": "Allow insert access to config",
                            "action": "INSERT",
                            "check": "true"
                        },
                        {
                            "name": "Allow update access to config",
                            "action": "UPDATE",
                            "using": "true",
                            "check": "true"
                        }
                    ]
                    
                    # Use the enhanced _create_table method with RLS support
                    if not supabase_manager._create_table(
                        config_table, 
                        sample_data, 
                        enable_rls=True, 
                        rls_policies=rls_policies
                    ):
                        message_bus.publish(
                            content=f"Failed to create config table",
                            level=MessageLevel.ERROR,
                            metadata={"source": self.SOURCE}
                        )
                        return {}
                
                # Query the config table
                result = supabase_manager.supabase.table(config_table).execute()
                config_data = result.data if hasattr(result, 'data') else []
                
                if not config_data:
                    message_bus.publish(
                        content="No configuration data found in Supabase",
                        level=MessageLevel.WARNING,
                        metadata={"source": self.SOURCE}
                    )
                    return {}
                
                # Convert to dictionary format (Key/Value pairs)
                config_dict = {item.get("key"): item.get("value") for item in config_data if item.get("key")}
                
                message_bus.publish(
                    content=f"Successfully fetched {len(config_dict)} configuration items from Supabase",
                    level=MessageLevel.INFO,
                    metadata={"source": self.SOURCE}
                )
                return config_dict
                
            except Exception as e:
                last_error = str(e)
                message_bus.publish(
                    content=f"Error fetching configuration from Supabase (attempt {attempt+1}/{self.max_retries}): {e}",
                    level=MessageLevel.WARNING,
                    metadata={"source": self.SOURCE}
                )
                message_bus.publish(
                    content=traceback.format_exc(),
                    level=MessageLevel.DEBUG,
                    metadata={"source": self.SOURCE}
                )
            
            # Increment attempt counter and delay before retry
            attempt += 1
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        
        # All attempts failed
        message_bus.publish(
            content=f"All {self.max_retries} attempts failed to fetch configuration: {last_error}",
            level=MessageLevel.ERROR,
            metadata={"source": self.SOURCE}
        )
        return {}

def get_data_provider(config_manager) -> DataProvider:
    """
    Factory function to get the appropriate data provider based on configuration.
    Returns a single data provider based on configuration settings with mutual exclusivity.
    
    Args:
        config_manager: The configuration manager instance
        
    Returns:
        A DataProvider instance (either Supabase or Google Sheets)
    """
    use_supabase = config_manager.get('use_supabase', False)
    use_googlesheet = config_manager.get('use_googlesheet', True)
    
    # Ensure mutual exclusivity - if Supabase is enabled, disable Google Sheets
    if use_supabase:
        use_googlesheet = False
        # Update the config to reflect this change
        config_manager.set('use_googlesheet', False)
    
    # If both are somehow disabled, default to Google Sheets
    if not use_supabase and not use_googlesheet:
        use_googlesheet = True
        config_manager.set('use_googlesheet', True)
    
    # Primary check for Supabase - use if enabled and connected
    if use_supabase:
        # Try to connect to Supabase if not already connected
        if not supabase_manager.is_connected():
            if not supabase_manager.connect():
                message_bus.publish(
                    content="Failed to connect to Supabase. Please check your Supabase settings.",
                    level=MessageLevel.WARNING
                )
                # If Supabase connection fails, fall back to Google Sheets
                use_googlesheet = True
                config_manager.set('use_googlesheet', True)
                config_manager.set('use_supabase', False)
            else:
                return SupabaseDataProvider(
                    max_retries=config_manager.get('data_provider_max_retries', 3),
                    retry_delay=config_manager.get('data_provider_retry_delay', 1.0)
                )
        else:
            return SupabaseDataProvider(
                max_retries=config_manager.get('data_provider_max_retries', 3),
                retry_delay=config_manager.get('data_provider_retry_delay', 1.0)
            )
    
    # Use Google Sheets if enabled or if Supabase failed
    if use_googlesheet:
        google_sheets_webhook = config_manager.get('google_sheets_webhook', '')
        if google_sheets_webhook:
            return GoogleSheetsDataProvider(
                webhook_url=google_sheets_webhook,
                max_retries=config_manager.get('data_provider_max_retries', 3),
                retry_delay=config_manager.get('data_provider_retry_delay', 1.0)
            )
    
    # Fallback message if nothing is configured
    message_bus.publish(
        content="No data provider is properly configured. Please check your settings.",
        level=MessageLevel.WARNING
    )
    
    # Return a non-functional Google Sheets provider if nothing is configured
    return GoogleSheetsDataProvider('')