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
        
    @abstractmethod
    def purge(self, table_name: str, username: Optional[str] = None) -> bool:
        """
        Delete data from the specified table/sheet.
        
        Args:
            table_name: The name of the table/sheet to purge
            username: Optional username filter. If provided, only data for this username will be deleted.
            
        Returns:
            bool: True if purge was successful, False otherwise
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

    def purge(self, table_name: str, username: Optional[str] = None) -> bool:
        """
        No-op implementation for Google Sheets as purging is not needed.
        
        Args:
            table_name: The name of the sheet (ignored)
            username: Optional username filter (ignored in this implementation)
            
        Returns:
            bool: Always returns True
        """
        if username:
            message_bus.publish(
                content=f"Purge operation with username filter not implemented for Google Sheets (sheet: {table_name}, username: {username})",
                level=MessageLevel.DEBUG,
                metadata={"source": self.SOURCE}
            )
        else:
            message_bus.publish(
                content=f"Purge operation not implemented for Google Sheets (sheet: {table_name})",
                level=MessageLevel.DEBUG,
                metadata={"source": self.SOURCE}
            )
        return True


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
        # Single list of excluded fields for all tables
        self.excluded_fields = ['direction_x', 'direction_y', 'direction_z']
        
    
    def is_connected(self) -> bool:
        """
        Check if Supabase provider is connected.
        
        Returns:
            bool: True if connected to Supabase, False otherwise
        """
        return supabase_manager.is_connected()
    
    def process_data(self, batch: List[Dict[str, Any]]) -> bool:
        """
        Process a batch of data for Supabase.
        
        Args:
            batch: List of dictionaries with 'data' and 'sheet' keys
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        if not batch:
            return True  # Empty batch is considered successful
            
        if not supabase_manager.is_connected():
            message_bus.publish(
                content="Supabase is not connected",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return False
        
        try:
            success_count = 0
            for item in batch:
                data = item.get('data', {})
                sheet = item.get('sheet', 'game_logs')
                
                if supabase_manager.insert_data(sheet, 
                                                {k.lower(): v for k, v in data.items() if k not in self.excluded_fields}):
                    success_count += 1
            
            # Report results
            if success_count == len(batch):
                message_bus.publish(
                    content=f"Successfully processed all {len(batch)} items",
                    level=MessageLevel.INFO,
                    metadata={"source": self.SOURCE}
                )
                return True
            elif success_count > 0:
                message_bus.publish(
                    content=f"Partially successful: processed {success_count}/{len(batch)} items",
                    level=MessageLevel.WARNING,
                    metadata={"source": self.SOURCE}
                )
                return success_count > 0  # Consider partial success as success
            else:
                message_bus.publish(
                    content="Failed to process any items in the batch",
                    level=MessageLevel.ERROR,
                    metadata={"source": self.SOURCE}
                )
                return False
                
        except Exception as e:
            message_bus.publish(
                content=f"Error processing batch: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            message_bus.publish(
                content=traceback.format_exc(),
                level=MessageLevel.DEBUG,
                metadata={"source": self.SOURCE}
            )
            return False
        
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
            
            # Use the view directly - table_name is already "resumen_view" in the database
            return self._execute_table_query("resumen_view", username=username)
            
        # Standard table query for non-Resumen tables
        # Sanitize the table name to match how it would be stored
        sanitized_table = supabase_manager._sanitize_table_name(table_name)
        return self._execute_table_query(sanitized_table, username=username)
    
    def _execute_table_query(self, table_name: str, username: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Execute a query against a Supabase table with retry logic.
        
        Args:
            table_name: The sanitized table name to query
            username: Optional username filter
            
        Returns:
            List of dictionaries containing the fetched data
        """
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                # Build the query
                query = supabase_manager.supabase.table(table_name).select('*')
                
                # Add username filter if provided
                if username:
                    query = query.eq('username', username)
                    
                # Check if this is the resumen_view which doesn't have a created_at column
                # Instead, it should be ordered by total_kills which is included in the view
                if table_name == "resumen_view":
                    try:
                        result = query.order('total_kills', desc=True).execute()
                        data = result.data if hasattr(result, 'data') else []
                        message_bus.publish(
                            content=f"Successfully fetched {len(data)} records from view '{table_name}'",
                            level=MessageLevel.DEBUG,
                            metadata={"source": self.SOURCE}
                        )
                        return data
                    except Exception as order_error:
                        message_bus.publish(
                            content=f"Order by total_kills failed for {table_name}, trying without ordering: {order_error}",
                            level=MessageLevel.DEBUG,
                            metadata={"source": self.SOURCE}
                        )
                        result = query.execute()
                        data = result.data if hasattr(result, 'data') else []
                        return data
                else:
                    # First try ordered query (by created_at)
                    try:
                        result = query.order('created_at', desc=True).execute()
                        data = result.data if hasattr(result, 'data') else []
                        message_bus.publish(
                            content=f"Successfully fetched {len(data)} records from table '{table_name}'",
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
                            content=f"Successfully fetched {len(data)} records from table '{table_name}' (unordered)",
                            level=MessageLevel.DEBUG,
                            metadata={"source": self.SOURCE}
                        )
                        return data
                    
            except Exception as e:
                last_error = str(e)
                message_bus.publish(
                    content=f"Error fetching from table '{table_name}' (attempt {attempt+1}/{self.max_retries}): {e}",
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
            content=f"All {self.max_retries} attempts failed to query table '{table_name}': {last_error}",
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
        # Check if view already exists using table_exists method
        if supabase_manager._table_exists("resumen_view"):
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
        ),
        
        -- Calculate average kills for each mode
        avg_stats AS (
            SELECT 
                AVG(kills_live) AS avg_kills_live,
                AVG(kills_sb) AS avg_kills_sb,
                AVG(kills_live + COALESCE(kills_sb, 0)) AS avg_total_kills
            FROM (
                SELECT 
                    live.kills_live,
                    sb.kills_sb
                FROM 
                    aggregated_live_stats live
                FULL OUTER JOIN
                    aggregated_sb_stats sb ON live.username = sb.username
                WHERE 
                    COALESCE(live.kills_live, 0) > 0 OR COALESCE(sb.kills_sb, 0) > 0
            ) subq
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
            -- KDR for Live mode with adjusted calculation (KD * kills/avg_kills)
            CASE 
                WHEN COALESCE(live.deaths_live, 0) = 0 THEN 
                    CASE 
                        WHEN avg.avg_kills_live > 0 THEN 
                            ROUND(COALESCE(live.kills_live, 0) * (COALESCE(live.kills_live, 0) / NULLIF(avg.avg_kills_live, 0)), 2)
                        ELSE COALESCE(live.kills_live, 0)
                    END
                ELSE 
                    CASE 
                        WHEN avg.avg_kills_live > 0 THEN 
                            ROUND(
                                (CAST(COALESCE(live.kills_live, 0) AS NUMERIC) / NULLIF(COALESCE(live.deaths_live, 0), 0)) * 
                                (COALESCE(live.kills_live, 0) / NULLIF(avg.avg_kills_live, 0)), 
                                2
                            )
                        ELSE 
                            ROUND(CAST(COALESCE(live.kills_live, 0) AS NUMERIC) / NULLIF(COALESCE(live.deaths_live, 0), 0), 2)
                    END
            END AS kdr_live,
            -- KDR for Squadron Battle mode with adjusted calculation (KD * kills/avg_kills)
            CASE 
                WHEN COALESCE(sb.deaths_sb, 0) = 0 THEN 
                    CASE 
                        WHEN avg.avg_kills_sb > 0 THEN 
                            ROUND(COALESCE(sb.kills_sb, 0) * (COALESCE(sb.kills_sb, 0) / NULLIF(avg.avg_kills_sb, 0)), 2)
                        ELSE COALESCE(sb.kills_sb, 0)
                    END
                ELSE 
                    CASE 
                        WHEN avg.avg_kills_sb > 0 THEN 
                            ROUND(
                                (CAST(COALESCE(sb.kills_sb, 0) AS NUMERIC) / NULLIF(COALESCE(sb.deaths_sb, 0), 0)) * 
                                (COALESCE(sb.kills_sb, 0) / NULLIF(avg.avg_kills_sb, 0)), 
                                2
                            )
                        ELSE 
                            ROUND(CAST(COALESCE(sb.kills_sb, 0) AS NUMERIC) / NULLIF(COALESCE(sb.deaths_sb, 0), 0), 2)
                    END
            END AS kdr_sb,
            -- Overall KDR across both modes with adjusted calculation (KD * kills/avg_kills)
            CASE 
                WHEN (COALESCE(live.deaths_live, 0) + COALESCE(sb.deaths_sb, 0)) = 0 THEN 
                    CASE 
                        WHEN avg.avg_total_kills > 0 THEN 
                            ROUND(
                                (COALESCE(live.kills_live, 0) + COALESCE(sb.kills_sb, 0)) * 
                                ((COALESCE(live.kills_live, 0) + COALESCE(sb.kills_sb, 0)) / NULLIF(avg.avg_total_kills, 0)),
                                2
                            )
                        ELSE (COALESCE(live.kills_live, 0) + COALESCE(sb.kills_sb, 0))
                    END
                ELSE 
                    CASE 
                        WHEN avg.avg_total_kills > 0 THEN 
                            ROUND(
                                (CAST((COALESCE(live.kills_live, 0) + COALESCE(sb.kills_sb, 0)) AS NUMERIC) / 
                                NULLIF((COALESCE(live.deaths_live, 0) + COALESCE(sb.deaths_sb, 0)), 0)) * 
                                ((COALESCE(live.kills_live, 0) + COALESCE(sb.kills_sb, 0)) / NULLIF(avg.avg_total_kills, 0)),
                                2
                            )
                        ELSE 
                            ROUND(
                                CAST((COALESCE(live.kills_live, 0) + COALESCE(sb.kills_sb, 0)) AS NUMERIC) / 
                                NULLIF((COALESCE(live.deaths_live, 0) + COALESCE(sb.deaths_sb, 0)), 0), 
                                2
                            )
                    END
            END AS kdr_total
        FROM 
            aggregated_live_stats live
        FULL OUTER JOIN
            aggregated_sb_stats sb ON live.username = sb.username
        CROSS JOIN
            avg_stats avg
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
        
        # Use sanitized table name for config table
        config_table = supabase_manager._sanitize_table_name("Config")
        
        # Check if the config table exists
        if not supabase_manager._table_exists(config_table):
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
                      
            # Use the enhanced _create_table method with RLS support
            if not supabase_manager._create_table(
                config_table, 
                sample_data
            ):
                message_bus.publish(
                    content=f"Failed to create config table",
                    level=MessageLevel.ERROR,
                    metadata={"source": self.SOURCE}
                )
                return {}
        
        # Query the config table
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                result = supabase_manager.supabase.table(config_table).select('*').execute()
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

    def purge(self, table_name: str, username: Optional[str] = None) -> bool:
        """
        Delete data from the specified table in Supabase.
        
        Args:
            table_name: The name of the table to purge
            username: Optional username filter. If provided, only data for this username will be deleted.
            
        Returns:
            bool: True if purge was successful, False otherwise
        """
        if not supabase_manager.is_connected():
            message_bus.publish(
                content="Supabase is not connected",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return False
        
        # Call the new purge_table method from supabase_manager that uses SQL via run_sql RPC
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                # Use the new purge_table method that executes SQL via RPC
                success = supabase_manager.purge_table(table_name, username)
                
                if success:
                    return True
                else:
                    last_error = "Purge operation failed"
            except Exception as e:
                last_error = str(e)
                message_bus.publish(
                    content=f"Exception during purge of table '{table_name}' (attempt {attempt+1}/{self.max_retries}): {e}",
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
            content=f"Failed to purge data from table '{table_name}' after {self.max_retries} attempts: {last_error}",
            level=MessageLevel.ERROR,
            metadata={"source": self.SOURCE}
        )
        return False

    def fetch_record_hashes(self, table_name: str) -> List[str]:
        """
        Fetch only MD5 hashes of records in the table for efficient duplicate detection.
        Uses a dedicated RPC function in Supabase.
        
        Args:
            table_name: The table name to fetch hashes from
            
        Returns:
            List of MD5 hash strings for existing records
        """
        if not supabase_manager.is_connected():
            message_bus.publish(
                content="Supabase is not connected",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return []

        # Sanitize the table name
        sanitized_table = supabase_manager._sanitize_table_name(table_name)
        
        # Check if the table exists
        if not supabase_manager._table_exists(sanitized_table):
            message_bus.publish(
                content=f"Table '{sanitized_table}' does not exist in Supabase",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
            return []
        
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                # Call the RPC function to get hashes directly from Supabase
                result = supabase_manager.supabase.rpc(
                    'get_table_record_hashes',
                    {'table_name': sanitized_table}
                ).execute()
                
                if hasattr(result, 'error') and result.error:
                    message_bus.publish(
                        content=f"Error fetching hashes via RPC: {result.error}",
                        level=MessageLevel.ERROR,
                        metadata={"source": self.SOURCE}
                    )
                    attempt += 1
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                    continue
                
                # Extract hashes from the result
                hashes = []
                if hasattr(result, 'data') and result.data:
                    for row in result.data:
                        if isinstance(row, dict) and 'hash_value' in row:
                            hashes.append(row['hash_value'])
                
                message_bus.publish(
                    content=f"Retrieved {len(hashes)} record hashes from table '{sanitized_table}' via RPC",
                    level=MessageLevel.DEBUG,
                    metadata={"source": self.SOURCE}
                )
                return hashes
                
            except Exception as e:
                last_error = str(e)
                message_bus.publish(
                    content=f"Error calling get_table_record_hashes RPC for table '{sanitized_table}' (attempt {attempt+1}/{self.max_retries}): {e}",
                    level=MessageLevel.WARNING,
                    metadata={"source": self.SOURCE}
                )
                message_bus.publish(
                    content=traceback.format_exc(),
                    level=MessageLevel.DEBUG,
                    metadata={"source": self.SOURCE}
                )
                
                # If RPC function might not exist, try the fallback direct SQL approach
                if "function get_table_record_hashes() does not exist" in str(e).lower():
                    message_bus.publish(
                        content="RPC function get_table_record_hashes not found, using fallback SQL approach",
                        level=MessageLevel.WARNING,
                        metadata={"source": self.SOURCE}
                    )
                    return self._fetch_record_hashes_fallback(sanitized_table)
            
            # Increment attempt counter and delay before retry
            attempt += 1
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        
        # All attempts failed
        message_bus.publish(
            content=f"All {self.max_retries} attempts failed to fetch hashes from '{sanitized_table}': {last_error}",
            level=MessageLevel.ERROR,
            metadata={"source": self.SOURCE}
        )
        
        # Try fallback method as last resort
        return []
        
def get_data_provider(config_manager) -> DataProvider:
    """
    Factory function to get the appropriate data provider based on configuration.
    Returns a single data provider based on the datasource configuration.
    
    Args:
        config_manager: The configuration manager instance
        
    Returns:
        A DataProvider instance (either Supabase or Google Sheets)
    """
    # Get the configured datasource (default to googlesheets)
    datasource = config_manager.datasource or 'googlesheets'
    
    # Return the appropriate data provider based on the datasource value
    if datasource == 'supabase':
        # Try to connect to Supabase if not already connected
        if not supabase_manager.is_connected():
            if not supabase_manager.connect():
                message_bus.publish(
                    content="Failed to connect to Supabase. Please check your Supabase settings.",
                    level=MessageLevel.WARNING
                )
                # If Supabase connection fails, fall back to Google Sheets
                datasource = 'googlesheets'
                config_manager.set('datasource', 'googlesheets')
            else:
                return SupabaseDataProvider(
                    max_retries=config_manager.data_provider_max_retries or 3,
                    retry_delay=config_manager.data_provider_retry_delay or 1.0
                )
        else:
            return SupabaseDataProvider(
                max_retries=config_manager.data_provider_max_retries or 3,
                retry_delay=config_manager.data_provider_retry_delay or 1.0
            )
    
    # Use Google Sheets if that's the selected datasource or if Supabase failed
    if datasource == 'googlesheets':
        google_sheets_webhook = config_manager.google_sheets_webhook or ''
        if google_sheets_webhook:
            return GoogleSheetsDataProvider(
                webhook_url=google_sheets_webhook,
                max_retries=config_manager.data_provider_max_retries or 3,
                retry_delay=config_manager.data_provider_retry_delay or 1.0
            )
    
    # Fallback message if nothing is configured
    message_bus.publish(
        content="No data provider is properly configured. Please check your settings.",
        level=MessageLevel.WARNING
    )
    
    # Return a non-functional Google Sheets provider if nothing is configured
    return GoogleSheetsDataProvider('')