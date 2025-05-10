import os
import json
import re
import time
import asyncio
from supabase import create_client, Client
# Import async client support
from supabase.lib.client_options import ClientOptions
from supabase import AsyncClientOptions
from supabase import create_async_client

import httpx
from typing import Optional, Tuple, Dict, Any, Union

# Load environment variables from config.json instead of .env
from .config_utils import get_config_manager

# Import message bus for standardized output
try:
    from .message_bus import message_bus, MessageLevel
except ImportError:
    # Fallback for when message_bus is not available
    message_bus = None
    MessageLevel = None

def log_message(content, level="INFO", pattern_name=None, metadata=None):
    """
    Send a message through the message bus or fallback to print if not available.
    
    Args:
        content: The message content
        level: Message level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        pattern_name: Optional regex pattern name
        metadata: Additional metadata
    """
    if message_bus:
        # Map string level to MessageLevel enum
        level_map = {
            "DEBUG": MessageLevel.DEBUG,
            "INFO": MessageLevel.INFO,
            "WARNING": MessageLevel.WARNING,
            "ERROR": MessageLevel.ERROR,
            "CRITICAL": MessageLevel.CRITICAL
        }
        msg_level = level_map.get(level.upper(), MessageLevel.INFO)
        
        # Send message to bus
        message_bus.publish(
            content=content,
            level=msg_level,
            pattern_name=pattern_name,
            metadata=metadata or {"source": "supabase_manager"}
        )
    else:
        # Fallback to print if message bus not available
        print(content)

class SupabaseManager:
    """
    Class to manage Supabase connection and operations.
    """
    def __init__(self):
        self.supabase_url = None
        self.supabase_key = None
        self.supabase: Client = None
        self.is_initialized = False
        self.connection_attempted = False  # Track if connection has been attempted
        self.metadata_cache = None  # Cache for metadata results
        
        # Async client attributes
        self.async_supabase = None
        self.async_is_initialized = False
        
        # Subscribe to schema change events to invalidate cache when needed
        if message_bus:
            message_bus.on("schema_change", self._invalidate_metadata_cache)
    
    def _extract_url_from_key(self, api_key):
        """
        Extract the Supabase URL from the API key.
        
        Args:
            api_key (str): The Supabase API key
            
        Returns:
            str: The extracted Supabase URL or None if extraction fails
        """
        if not api_key:
            return None
            
        # Supabase API keys typically have this format: 
        # eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhtaXd2a3BteWF0aXR6dHZ0ZnFidiIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjkyNjMyODg5LCJleHAiOjIwMDgyMDg4ODl9.M0Q_xmXwwSnQ8walRV0epTh3P0lSBzLxCZQDliZ64N4
        
        try:
            # Split the JWT token into its parts
            parts = api_key.split('.')
            if len(parts) != 3:
                log_message("Invalid API key format: does not consist of three parts", "ERROR")
                return None
                
            # Decode the payload (middle part)
            import base64
            # Fix padding if needed
            payload = parts[1]
            payload += '=' * ((4 - len(payload) % 4) % 4)
            
            # Decode the payload
            decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
            payload_data = json.loads(decoded)
            
            # Extract the reference (ref) from the payload
            project_ref = payload_data.get('ref')
            if not project_ref:
                log_message("Could not extract project reference from API key", "ERROR")
                return None
                
            # Construct the Supabase URL
            supabase_url = f"https://{project_ref}.supabase.co"
            log_message(f"Generated Supabase URL: {supabase_url}", "DEBUG")
            return supabase_url
            
        except Exception as e:
            log_message(f"Error extracting URL from API key: {e}", "ERROR")
            return None
        
    def connect(self, config_manager=None, force=False):
        """
        Connect to Supabase using values from config.
        
        Args:
            config_manager (ConfigManager, optional): If provided, use this config manager
                instance instead of getting a new one from get_config_manager().
            force (bool, optional): If True, force reconnection even if already connected.
                Use this when the API key has changed.
        
        Returns:
            bool: True if connection is successful, False otherwise.
        """
        # If force=True, reset connection state to enable reconnection
        if force:
            self.is_initialized = False
            self.connection_attempted = False
            self.supabase = None
            log_message("Forcing reconnection to Supabase", "INFO")
            
        # If we've already tried connecting, don't try again unless explicitly asked to reconnect
        if self.connection_attempted and self.is_initialized and not force:
            return True
            
        self.connection_attempted = True
        
        try:
            # Use the provided config_manager if available
            # Otherwise get a new one (which could cause circular dependency)
            if config_manager is None:
                from .config_utils import get_config_manager
                config_manager = get_config_manager()
            
            # Get Supabase key from config
            self.supabase_key = config_manager.get('supabase_key')
            
            if not self.supabase_key:
                log_message("Supabase key not found in config.", "ERROR")
                return False
            
            # Always generate the URL from the API key
            self.supabase_url = self._extract_url_from_key(self.supabase_key)
            
            if not self.supabase_url:
                log_message("Could not extract Supabase URL from API key.", "ERROR")
                return False
            
            # Create client without any additional parameters that might cause issues
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            self.is_initialized = True
            
            # Report success through message bus
            if message_bus:
                message_bus.publish(
                    content="Connected to Supabase successfully.",
                    level=MessageLevel.DEBUG
                )
            else:
                print("Connected to Supabase successfully.")
                
            return True
        except Exception as e:
            log_message(f"Error connecting to Supabase: {e}", "ERROR")
            self.is_initialized = False
            return False
    
    def connect_async(self, config_manager=None, force=False, username=None):
        """
        Connect to Supabase using the async client.
        
        Args:
            config_manager (ConfigManager, optional): If provided, use this config manager
                instance instead of getting a new one from get_config_manager().
            force (bool, optional): If True, force reconnection even if already connected.
            username (str, optional): Username to use for anonymous auth
        
        Returns:
            object: The async Supabase client object if successful, None otherwise.
        """
        # If we're already connected and not forcing reconnection, return the existing client
        if self.async_is_initialized and not force:
            log_message("Using existing async Supabase client (already initialized)", "DEBUG")
            return self.async_supabase
            
        log_message("Initializing async Supabase client", "DEBUG")
        
        try:
            # Make sure we have a valid URL and key
            if not self.is_connected():
                if not self.connect(config_manager, force):
                    return None
            if not username:
                return None
                
            try:
                # Try to authenticate anonymously
                log_message(f"Authenticating anonymously with username: {username} before async connection", "INFO")
                jwt = self.supabase.auth.sign_in_anonymously(
                    {"options": {"data": {"username": username}}}
                )
                self.auth_token = jwt.session.access_token 
                log_message(f"Anonymous authentication successful for user: {username}", "DEBUG")
            except Exception as auth_error:
                log_message(f"Warning: Anonymous authentication failed: {auth_error}. Will continue with async connection.", "WARNING")
                # Continue with async connection even if auth fails
            
            # Create async client - without using realtime_multiplexed which is not supported
            options = AsyncClientOptions(
                schema="public"
            )
            
            # Importación tardía para evitar dependencia circular
            from .realtime_bridge import run_coroutine
            
            # Usar la función run_coroutine que aprovecha el singleton de RealtimeBridge
            # sin necesidad de crear nuevas instancias o bucles de eventos redundantes
            self.async_supabase = run_coroutine(create_async_client(
                self.supabase_url, 
                self.supabase_key, 
                options=options
            ))
            
            # Conectar el cliente y establecer el token de autenticación
            run_coroutine(self.async_supabase.realtime.connect())
            run_coroutine(self.async_supabase.realtime.set_auth(self.auth_token))
            
            if self.async_supabase:
                log_message("Async Supabase client created successfully", "INFO")
                self.async_is_initialized = True
            else:
                log_message("Async Supabase client creation returned None", "ERROR")
                self.async_is_initialized = False
            
            return self.async_supabase
            
        except Exception as e:
            log_message(f"Error connecting to Supabase async client: {e}", "ERROR")
            import traceback
            log_message(f"Traceback: {traceback.format_exc()}", "ERROR")
            self.async_is_initialized = False
            return None
    
    def get_async_client(self, username=None):
        """
        Get the async Supabase client, initializing it if needed.
        
        Returns:
            object: The async Supabase client
        """
        if not self.async_is_initialized:
            return self.connect_async(username=username)
        return self.async_supabase
            
    def reconnect(self):
        """Force a reconnection to Supabase even if already connected."""
        self.is_initialized = False
        self.connection_attempted = False
        self.async_is_initialized = False
        return self.connect()
            
    def is_connected(self):
        """
        Check if Supabase is connected.
        
        Returns:
            bool: True if connected, False otherwise.
        """
        return self.is_initialized
    
    def _sanitize_table_name(self, name):
        """
        DEPRECATED: Use _normalize_db_object_name instead.
        Keeping for backward compatibility.
        """
        return self._normalize_db_object_name(name, "table")
        
    def _normalize_db_object_name(self, name, object_type="table"):
        """
        Normalize a database object name to ensure it's compatible with SQL naming conventions.
        
        Args:
            name (str): Original name
            object_type (str): Type of database object ('table' or 'view')
            
        Returns:
            str: Normalized name valid for SQL database objects
        """
        if not name:
            return "default_logs" if object_type == "table" else "default_view"
            
        # Convert to lowercase
        name = name.lower()
        
        # Replace spaces and special characters with underscores
        name = re.sub(r'[^a-z0-9]', '_', name)
        
        # Ensure it starts with a letter
        if not name[0].isalpha():
            prefix = "t_" if object_type == "table" else "v_"
            name = prefix + name
            
        # Add view suffix if it's a view and doesn't already have it
        if object_type == "view" and not name.endswith('_view'):
            name = name + "_view"
            
        # Truncate if too long (PostgreSQL limit is typically 63 characters)
        max_length = 60
        if object_type == "view" and not name.endswith('_view'):
            max_length = 55  # Leave room for _view suffix
        
        if len(name) > max_length:
            name = name[:max_length]
            
        # Make sure view suffix is added after truncation
        if object_type == "view" and not name.endswith('_view'):
            name = name + "_view"
            
        return name
    
    def _table_exists(self, table_name):
        """
        Check if a table exists using the metadata cache when possible
        
        Args:
            table_name (str): The table name to check
            
        Returns:
            bool: True if the table exists, False otherwise
        """
        if not self.is_connected():
            return False
            
        try:
            # Get metadata (from cache if available)
            metadata = self.get_metadata()
            
            # Check if the table exists in metadata
            return table_name in metadata
            
        except Exception as e:
            log_message(f"Error checking table existence: {e}", "ERROR")
            return False
    
    def _execute_sql(self, sql):
        """
        Execute raw SQL commands via the run_sql RPC function in Supabase.
        
        Args:
            sql (str): SQL command to execute
            
        Returns:
            tuple: (success, result) where success is a boolean and result contains data or error info
        """
        if not self.is_connected():
            return False, "Not connected to Supabase"
            
        try:
            # Call the run_sql RPC function
            result = self.supabase.rpc(
                'run_sql', 
                {'query': sql}
            ).execute()
            
            # Check for errors
            if hasattr(result, 'error') and result.error:
                return False, result.error
                
            return True, result.data
        except Exception as e:
            log_message(f"Error executing SQL via RPC: {e}", "ERROR")
            return False, str(e)
    
    def _create_table(self, table_name, data, enable_rls=True, rls_policies=None):
        """
        Create a new table based on the data structure using raw SQL.
        
        Args:
            table_name (str): The name of the table to create
            data (dict): Sample data to determine column structure
            enable_rls (bool): Whether to enable Row Level Security on the table (default: True)
            rls_policies (list): List of RLS policy dictionaries, each containing:
                - name: Policy name
                - action: SELECT, INSERT, UPDATE, DELETE, ALL
                - using: USING expression (for SELECT, UPDATE, DELETE)
                - check: WITH CHECK expression (for INSERT, UPDATE)
                
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_connected():
            return False
            
        try:
            # Generate a CREATE TABLE statement based on the data structure
            columns = []
            
            # Add id as primary key if not in data
            columns.append("id UUID PRIMARY KEY DEFAULT gen_random_uuid()")
            
            # Add created_at timestamp if not in data
            columns.append("created_at TIMESTAMP DEFAULT NOW()")
            
            # Check if sample data has all fields needed for hash_value computation
            hash_fields_present = all(field in data for field in ['username', 'killer', 'victim', 'timestamp'])
            
            # Add hash_value generated column only if all required fields are present
            if hash_fields_present:
                columns.append("hash_value TEXT GENERATED ALWAYS AS"
                " (MD5(COALESCE(username, '') || COALESCE(killer, '') || COALESCE(victim, '') || COALESCE(extract(epoch from \"timestamp\")::TEXT, '')))  STORED")
                log_message(f"Added hash_value computed column to {table_name} as all required fields are present", "DEBUG")
            else:
                log_message(f"Skipped hash_value column for {table_name} as some required fields are missing", "DEBUG")
            
            # ISO 8601 format with timezone and milliseconds: 2025-04-15T18:30:26.650Z
            datetime_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$'
            
            def is_datetime_string(value):
                """Check if a string matches ISO 8601 datetime format"""
                if not isinstance(value, str):
                    return False
                return bool(re.match(datetime_pattern, value))
            
            # Process other fields in the data
            for key, value in data.items():
                # Skip id, created_at and hash_value which we've already handled
                if key in ('id', 'created_at', 'hash_value'):
                    continue
                    
                # Determine column type based on value type
                if isinstance(value, bool):
                    columns.append(f"{key} BOOLEAN")
                elif isinstance(value, int):
                    # Use BIGINT instead of INTEGER to support larger numbers
                    columns.append(f"{key} BIGINT")
                elif isinstance(value, float):
                    columns.append(f"{key} NUMERIC")
                elif isinstance(value, dict) or isinstance(value, list):
                    columns.append(f"{key} JSONB")
#                elif is_datetime_string(value):
                    # If string matches ISO 8601 datetime pattern, use TIMESTAMP
#                    columns.append(f"{key} TIMESTAMP")
                else:
                    # Default to text for strings and other types
                    columns.append(f"{key} TEXT")
            
            # Create the full SQL statement with all columns including hash_value if present
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                {','.join(columns)}
            );
            """
            
            # Enable RLS if specified
            if enable_rls:
                create_table_sql += f"""
                -- Enable Row Level Security
                ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY;
                """
                
                # If no custom policies are provided, use the default policies from sc_default table
                if not rls_policies:
                    # Default policies from the sc_default table
                    rls_policies = [
                        {
                            'name': 'Public SELECT',
                            'action': 'SELECT',
                            'using': 'true'
                        },
                        {
                            'name': 'Public INSERT',
                            'action': 'INSERT',
                            'check': 'true'
                        },
                        {
                            'name': 'Admin UPDATE only',
                            'action': 'UPDATE',
                            'using': "CURRENT_USER = 'postgres'"
                        },
                        {
                            'name': 'Admin DELETE only',
                            'action': 'DELETE',
                            'using': "CURRENT_USER = 'postgres'"
                        }
                    ]
                
                # Add all RLS policies
                for policy in rls_policies:
                    policy_name = policy.get('name', f"policy_{table_name}_{policy.get('action', 'all')}")
                    action = policy.get('action', 'ALL')
                    
                    # Create appropriate policy based on action type
                    if action.upper() == 'INSERT':
                        # INSERT policies only use WITH CHECK
                        check_expr = policy.get('check', 'true')
                        create_table_sql += f"""
                        -- Create {action} policy
                        CREATE POLICY "{policy_name}" ON "{table_name}"
                            FOR {action} WITH CHECK ({check_expr});
                        """
                    elif action.upper() == 'UPDATE':
                        # UPDATE policies can use both USING and WITH CHECK
                        using_expr = policy.get('using', 'true')
                        
                        if 'check' in policy:
                            check_expr = policy.get('check')
                            create_table_sql += f"""
                            -- Create {action} policy
                            CREATE POLICY "{policy_name}" ON "{table_name}"
                                FOR {action} USING ({using_expr}) WITH CHECK ({check_expr});
                            """
                        else:
                            create_table_sql += f"""
                            -- Create {action} policy
                            CREATE POLICY "{policy_name}" ON "{table_name}"
                                FOR {action} USING ({using_expr});
                            """
                    elif action.upper() == 'SELECT' or action.upper() == 'DELETE':
                        # SELECT and DELETE policies only use USING
                        using_expr = policy.get('using', 'true')
                        create_table_sql += f"""
                        -- Create {action} policy
                        CREATE POLICY "{policy_name}" ON "{table_name}"
                            FOR {action} USING ({using_expr});
                        """
                    else:  # ALL
                        # ALL policies can use both USING and WITH CHECK
                        using_expr = policy.get('using', 'true')
                        check_expr = policy.get('check', 'true')
                        create_table_sql += f"""
                        -- Create general policy
                        CREATE POLICY "{policy_name}" ON "{table_name}"
                            USING ({using_expr})
                            WITH CHECK ({check_expr});
                        """
            
            # Execute the SQL
            success, result = self._execute_sql(create_table_sql)
            
            if success:
                log_message(f"Created table {table_name} in Supabase using SQL", "DEBUG")
                
                # Emit schema change event to invalidate cache
                if message_bus:
                    message_bus.emit("schema_change")
                
                return True
            else:
                # Log the error but don't use fallback
                log_message(f"Error creating table via SQL: {result}", "ERROR")
                return False
        except Exception as e:
            log_message(f"Error creating table {table_name}: {e}", "ERROR")
            return False
      
    def insert_data(self, sheet, data):
        """
        Insert game log data into Supabase.
        
        Args:
            sheet (str): The sheet name to use for the table.
            data (dict): The log data to insert.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.is_connected():
            return False
            
        try:
            # Priority: 1. sheet parameter, 2. mode value, 3. default
            table_base_name = sheet or "game_logs"
            
            # Sanitize the table name to be SQL-safe
            table_name = self._sanitize_table_name(table_base_name)
            
            # Flag to track if we just created a new table
            table_newly_created = False
            
            # Check if the table exists, create it if it doesn't
            if not self._table_exists(table_name):
                if not self._create_table(table_name, data):
                    log_message("Failed to create table. Aborting insert.", "ERROR")
                    return False
                table_newly_created = True
                log_message(f"New table {table_name} created, will use retry mechanism for first insert", "DEBUG")
            
            # Determine how many retry attempts to use
            max_retries = 3 if table_newly_created else 1
            retry_count = 0
            delay_seconds = 1  # Start with 1 second delay
            
            # Try insertion with retries
            while retry_count < max_retries:
                try:
                    # If this isn't our first attempt, add a delay
                    if retry_count > 0:
                        log_message(f"Retry attempt {retry_count} for inserting into {table_name}, waiting {delay_seconds} seconds...", "DEBUG")
                        time.sleep(delay_seconds)
                        delay_seconds *= 2  # Exponential backoff
                    
                    
                    result = self.supabase.table(table_name).insert(data).execute()
                    
                    # Check for errors - more robust error checking
                    if hasattr(result, 'error') and result.error is not None:
                        error_msg = str(result.error)
                        log_message(f"Error inserting log into Supabase table {table_name}: {error_msg}", "ERROR")
                        
                        # If this is the last retry, return failure
                        if retry_count >= max_retries - 1:
                            return False
                            
                        # Otherwise, increment retry counter and continue the loop
                        retry_count += 1
                        continue
                    
                    # If we get here, the insert was successful
                    log_message(f"Successfully inserted data into {table_name}{' after ' + str(retry_count) + ' retries' if retry_count > 0 else ''}", "DEBUG")
                    return True
                    
                except Exception as insert_error:
                    # Handle the exception
                    error_message = str(insert_error) if str(insert_error) else "Empty Error received from Supabase API"
                    log_message(f"Exception during Supabase insert operation: {error_message}", "ERROR")
                    
                    # If this is the last retry, return failure
                    if retry_count >= max_retries - 1:
                        log_message(f"Failed to insert after {retry_count + 1} attempts", "ERROR")
                        log_message(f"Table: {table_name}, Data keys: {list(data.keys())}", "DEBUG")
                        return False
                    
                    # Otherwise, increment retry counter and continue the loop
                    retry_count += 1
            
            # This point should not be reached due to the logic above, 
            # but including as a safeguard
            return False
                
        except Exception as e:
            log_message(f"Exception inserting log into Supabase: {e}", "ERROR")
            return False

    def purge_table(self, table_name: str, username: Optional[str] = None) -> bool:
        """
        Purge data from a table using raw SQL via the run_sql RPC function instead of the API.
        
        Args:
            table_name (str): Name of the table to purge
            username (Optional[str]): If provided, only purge records for this username
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_connected():
            log_message("Supabase is not connected. Cannot purge table.", "ERROR")
            return False
            
        try:
            # Sanitize the table name
            sanitized_table = self._sanitize_table_name(table_name)
            
            # Check if the table exists
            if not self._table_exists(sanitized_table):
                log_message(f"Table '{sanitized_table}' does not exist in Supabase. Nothing to purge.", "INFO")
                return True  # Not an error if the table doesn't exist
            
            # Construct the DELETE SQL statement
            if username:
                log_message(f"Purging data for username '{username}' from table: {sanitized_table}", "INFO")
                delete_sql = f"""
                DELETE FROM "{sanitized_table}" 
                WHERE username = '{username.replace("'", "''")}';
                """
            else:
                log_message(f"Purging all data from table: {sanitized_table}", "INFO")
                delete_sql = f"""
                DELETE FROM "{sanitized_table}" WHERE TRUE;
                """
            
            # Execute the SQL using the run_sql RPC function
            success, result = self._execute_sql(delete_sql)
            
            if success:
                if username:
                    log_message(f"Successfully purged data for username '{username}' from table: {sanitized_table}", "INFO")
                else:
                    log_message(f"Successfully purged all data from table: {sanitized_table}", "INFO")
                return True
            else:
                log_message(f"Failed to purge data from table '{sanitized_table}': {result}", "ERROR")
                return False
                
        except Exception as e:
            log_message(f"Exception during purge of table '{table_name}': {e}", "ERROR")
            return False

    def get_metadata(self, force_refresh=False):
        """
        Get database metadata (tables, columns, types), using cache if available
        
        Args:
            force_refresh (bool): Force a refresh of the cache
            
        Returns:
            dict: Processed metadata with tables and their columns
        """
        # If cache exists and no forced refresh, use the cache
        if not force_refresh and self.metadata_cache is not None:
            return self.metadata_cache
        
        # Otherwise, refresh the cache
        try:
            result = self.supabase.rpc('get_metadata').execute()
            
            if hasattr(result, 'error') and result.error:
                log_message(f"Error fetching metadata: {result.error}", "ERROR")
                return {} if self.metadata_cache is None else self.metadata_cache
            
            # Process and organize the results into a structured format
            processed_metadata = self._process_metadata_results(result.data)
            
            # Update cache
            self.metadata_cache = processed_metadata
            return processed_metadata
            
        except Exception as e:
            log_message(f"Exception getting metadata: {e}", "ERROR")
            return {} if self.metadata_cache is None else self.metadata_cache
    
    def _process_metadata_results(self, raw_metadata):
        """
        Process raw metadata results into a structured format
        
        Args:
            raw_metadata (list): List of dicts with table_name, column_name, data_type
            
        Returns:
            dict: Structured metadata by table and column
        """
        structured_metadata = {}
        
        # Group by table name
        for item in raw_metadata:
            table_name = item['table_name']
            column_name = item['column_name']
            data_type = item['data_type']
            
            if table_name not in structured_metadata:
                structured_metadata[table_name] = {'columns': {}}
                
            structured_metadata[table_name]['columns'][column_name] = data_type
        
        return structured_metadata
    
    def _invalidate_metadata_cache(self):
        """
        Invalidate the metadata cache when schema changes
        """
        self.metadata_cache = None
        log_message("Metadata cache invalidated due to schema change", "DEBUG")

# Create a singleton instance
supabase_manager = SupabaseManager()