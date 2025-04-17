import os
import json
import re
import time
from supabase import create_client, Client

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
        self.existing_tables = set()  # Cache for existing table names
        self.table_cache_time = 0  # Last time the table cache was updated
        self.table_cache_ttl = 300  # Cache TTL in seconds (5 minutes)
        self.connection_attempted = False  # Track if connection has been attempted
        
    def connect(self):
        """
        Connect to Supabase using values from config.
        
        Returns:
            bool: True if connection is successful, False otherwise.
        """
        # If we've already tried connecting, don't try again unless explicitly asked to reconnect
        if self.connection_attempted and self.is_initialized:
            return True
            
        self.connection_attempted = True
        
        try:
            # Get the config manager
            config_manager = get_config_manager()
            
            # Get Supabase credentials from config
            self.supabase_url = config_manager.get('supabase_url')
            self.supabase_key = config_manager.get('supabase_key')
            
            if not self.supabase_url or not self.supabase_key:
                log_message("Supabase URL or key not found in config.", "ERROR")
                return False
                
            # Create client without any additional parameters that might cause issues
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            self.is_initialized = True
            
            # Report success through message bus
            if message_bus:
                message_bus.publish(
                    content="Connected to Supabase successfully.",
                    level=MessageLevel.INFO
                )
            else:
                print("Connected to Supabase successfully.")
            
            # Initialize table cache
            self._refresh_table_cache()
            
            return True
        except Exception as e:
            log_message(f"Error connecting to Supabase: {e}", "ERROR")
            self.is_initialized = False
            return False
            
    def reconnect(self):
        """Force a reconnection to Supabase even if already connected."""
        self.is_initialized = False
        self.connection_attempted = False
        return self.connect()
            
    def is_connected(self):
        """
        Check if Supabase is connected.
        
        Returns:
            bool: True if connected, False otherwise.
        """
        return self.is_initialized
    
    def _refresh_table_cache(self):
        """
        Refresh the cache of existing tables using PostgreSQL metadata.
        """
        if not self.is_connected():
            return
            
        try:
            # Try a direct method that works with Supabase PostgREST API
            # This uses the special PostgREST metadata format to get a schema listing
            # Reference: https://postgrest.org/en/stable/api.html#schema-discovery
            
            # Since we're using the Supabase client, we need to adapt the approach
            try:
                # Try the special PostgREST approach by directly querying public schema tables
                # Get the base URL from supabase client
                base_url = self.supabase.rest_url
                
                # Add the metadata query directly to the base URL
                import requests
                
                # Get the headers from the supabase client
                headers = {
                    'apikey': self.supabase_key,
                    'Authorization': f'Bearer {self.supabase_key}'
                }
                
                # Direct REST API call to get schema metadata
                response = requests.get(
                    f"{base_url}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    # Extract table names from the response
                    schema_data = response.json()
                    
                    # The response contains all tables in the public schema
                    self.existing_tables = set(table for table in schema_data.keys() 
                                           if not table.startswith('_'))
                    self.table_cache_time = time.time()
                    
                    log_message(f"Table cache refreshed using PostgREST schema discovery. Found {len(self.existing_tables)} tables.", "DEBUG")
                    return
            except Exception as e:
                log_message(f"PostgREST failed: {e}", "WARNING")
                           
        except Exception as e:
            log_message(f"Error refreshing table cache: {e}", "ERROR")
            # Don't clear the cache on error - conservative approach
            
    
    def _sanitize_table_name(self, name):
        """
        Sanitize a string to be used as a table name.
        
        Args:
            name (str): Original name
            
        Returns:
            str: Sanitized name valid for SQL tables
        """
        if not name:
            return "default_logs"
            
        # Convert to lowercase
        name = name.lower()
        
        # Replace spaces and special characters with underscores
        name = re.sub(r'[^a-z0-9]', '_', name)
        
        # Ensure it starts with a letter
        if not name[0].isalpha():
            name = "t_" + name
            
        # Truncate if too long (PostgreSQL limit is typically 63 characters)
        if len(name) > 60:
            name = name[:60]
            
        return name
    
    def _table_exists(self, table_name):
        """
        Check if a table exists in Supabase.
        
        Args:
            table_name (str): The table name to check
            
        Returns:
            bool: True if the table exists, False otherwise
        """
        # Check if we need to refresh the cache
        if time.time() - self.table_cache_time > self.table_cache_ttl:
            self._refresh_table_cache()
            
        return table_name in self.existing_tables
    
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
    
    def _create_table(self, table_name, data, enable_rls=False, rls_policies=None):
        """
        Create a new table based on the data structure using raw SQL.
        
        Args:
            table_name (str): The name of the table to create
            data (dict): Sample data to determine column structure
            enable_rls (bool): Whether to enable Row Level Security on the table
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
            columns.append("created_at TIMESTAMPTZ DEFAULT NOW()")
            
            # Process other fields in the data
            for key, value in data.items():
                # Skip id and created_at which we've already handled
                if key in ('id', 'created_at'):
                    continue
                    
                # Determine column type based on value type
                if isinstance(value, int):
                    columns.append(f"{key} INTEGER")
                elif isinstance(value, float):
                    columns.append(f"{key} NUMERIC")
                elif isinstance(value, bool):
                    columns.append(f"{key} BOOLEAN")
                elif isinstance(value, dict) or isinstance(value, list):
                    columns.append(f"{key} JSONB")
                else:
                    # Default to text for strings and other types
                    columns.append(f"{key} TEXT")
            
            # Create the full SQL statement
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                {','.join(columns)}
            );
            """
            
            # Add RLS if requested
            if enable_rls:
                create_table_sql += f"""
                -- Enable Row Level Security
                ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY;
                """
                
                # Add RLS policies if provided
                if rls_policies:
                    for policy in rls_policies:
                        policy_name = policy.get('name', f"policy_{table_name}_{policy.get('action', 'all')}")
                        action = policy.get('action', 'ALL')
                        using_expr = policy.get('using', 'true')
                        check_expr = policy.get('check', 'true')
                        
                        # Create appropriate policy based on action type
                        if action.upper() in ('INSERT', 'UPDATE'):
                            create_table_sql += f"""
                            -- Create {action} policy
                            CREATE POLICY "{policy_name}" ON "{table_name}"
                                FOR {action} WITH CHECK ({check_expr});
                            """
                        elif action.upper() in ('SELECT', 'DELETE'):
                            create_table_sql += f"""
                            -- Create {action} policy
                            CREATE POLICY "{policy_name}" ON "{table_name}"
                                FOR {action} USING ({using_expr});
                            """
                        else:  # ALL
                            create_table_sql += f"""
                            -- Create general policy
                            CREATE POLICY "{policy_name}" ON "{table_name}"
                                USING ({using_expr})
                                WITH CHECK ({check_expr});
                            """
            
            # Execute the SQL
            success, result = self._execute_sql(create_table_sql)
            
            if success:
                # Add to our cache of existing tables
                self.existing_tables.add(table_name)
                log_message(f"Created table {table_name} in Supabase using SQL", "INFO")
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
            
            # Check if the table exists, create it if it doesn't
            if not self._table_exists(table_name):
                if not self._create_table(table_name, data):
                    log_message("Failed to create table. Aborting insert.", "ERROR")
                    return False
            
            # Insert the data into the table with improved error handling
            try:
                result = self.supabase.table(table_name).insert(data).execute()
                
                # Check for errors - more robust error checking
                if hasattr(result, 'error') and result.error is not None:
                    log_message(f"Error inserting log into Supabase table {table_name}: {result.error}", "ERROR")
                    return False
                    
                log_message(f"Successfully inserted data into {table_name}", "DEBUG")
                return True
            except Exception as insert_error:
                # Handle the "Empty Error" exception
                error_message = str(insert_error) if str(insert_error) else "Empty Error received from Supabase API"
                log_message(f"Exception during Supabase insert operation: {error_message}", "ERROR")
                log_message(f"Table: {table_name}, Data keys: {list(data.keys())}", "DEBUG")
                return False
                
        except Exception as e:
            log_message(f"Exception inserting log into Supabase: {e}", "ERROR")
            return False

# Create a singleton instance
supabase_manager = SupabaseManager()