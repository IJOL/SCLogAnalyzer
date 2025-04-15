import os
import json
import re
import time
from supabase import create_client, Client

# Load environment variables from config.json instead of .env
from config_utils import get_config_manager

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
        
    def connect(self):
        """
        Connect to Supabase using values from config.
        
        Returns:
            bool: True if connection is successful, False otherwise.
        """
        try:
            # Get the config manager
            config_manager = get_config_manager()
            
            # Get Supabase credentials from config
            self.supabase_url = config_manager.get('supabase_url')
            self.supabase_key = config_manager.get('supabase_key')
            
            if not self.supabase_url or not self.supabase_key:
                print("Supabase URL or key not found in config.")
                return False
                
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            self.is_initialized = True
            print("Connected to Supabase successfully.")
            
            # Initialize table cache
            self._refresh_table_cache()
            
            return True
        except Exception as e:
            print(f"Error connecting to Supabase: {e}")
            self.is_initialized = False
            return False
            
    def is_connected(self):
        """
        Check if Supabase is connected.
        
        Returns:
            bool: True if connected, False otherwise.
        """
        return self.is_initialized
    
    def _refresh_table_cache(self):
        """
        Refresh the cache of existing tables.
        """
        if not self.is_connected():
            return
            
        try:
            # Query to get all table names
            response = self.supabase.rpc('get_tables').execute()
            
            if hasattr(response, 'data') and response.data:
                # Extract table names
                self.existing_tables = set(item['name'] for item in response.data)
                self.table_cache_time = time.time()
            else:
                # Alternative method if RPC is not available
                # This is a fallback that uses the REST API
                # The actual query might differ based on your Supabase setup
                response = self.supabase.table('pg_tables').select('tablename').eq('schemaname', 'public').execute()
                if hasattr(response, 'data') and response.data:
                    self.existing_tables = set(item['tablename'] for item in response.data)
                    self.table_cache_time = time.time()
        except Exception as e:
            print(f"Error refreshing table cache: {e}")
    
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
    
    def _create_table(self, table_name, data):
        """
        Create a new table based on the data structure.
        
        Args:
            table_name (str): The name of the table to create
            data (dict): Sample data to determine column structure
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_connected():
            return False
            
        try:
            # Determine column types based on data values
            columns = []
            
            # Standard columns that should always be present
            columns.append("id serial primary key")
            columns.append("created_at timestamp with time zone default now()")
            
            # Add columns based on data fields
            for key, value in data.items():
                # Skip id field as it's already defined
                if key == 'id':
                    continue
                    
                # Skip created_at field as it's already defined
                if key == 'created_at':
                    continue
                    
                # Determine column type based on value type
                if isinstance(value, int):
                    columns.append(f"\"{key}\" integer")
                elif isinstance(value, float):
                    columns.append(f"\"{key}\" double precision")
                elif isinstance(value, bool):
                    columns.append(f"\"{key}\" boolean")
                elif isinstance(value, dict) or isinstance(value, list):
                    columns.append(f"\"{key}\" jsonb")
                else:
                    # Default to text for strings and other types
                    columns.append(f"\"{key}\" text")
            
            # Create the table
            create_table_sql = f"CREATE TABLE {table_name} ({', '.join(columns)});"
            
            # Execute the SQL (this depends on how your Supabase client handles raw SQL)
            # The implementation may vary based on your Supabase setup
            response = self.supabase.rpc('run_sql', {"sql": create_table_sql}).execute()
            
            # Update table cache
            self.existing_tables.add(table_name)
            
            print(f"Created new table {table_name} in Supabase")
            return True
        except Exception as e:
            print(f"Error creating table {table_name}: {e}")
            return False
        
    def insert_log(self, data):
        """
        Insert game log data into Supabase.
        
        Args:
            data (dict): The log data to insert.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.is_connected():
            return False
            
        try:
            # Determine the table name based on the sheet parameter
            sheet_name = data.get('sheet')
            mode_name = data.get('mode')
            
            # Priority: 1. sheet parameter, 2. mode value, 3. default
            table_base_name = sheet_name or mode_name or "game_logs"
            
            # Sanitize the table name to be SQL-safe
            table_name = self._sanitize_table_name(table_base_name)
            
            # Check if the table exists, create it if it doesn't
            if not self._table_exists(table_name):
                if not self._create_table(table_name, data):
                    # Fallback to default table if creation fails
                    table_name = "game_logs"
                    
                    # Create default table if it doesn't exist
                    if not self._table_exists(table_name):
                        if not self._create_table(table_name, data):
                            print("Failed to create even the default table. Aborting insert.")
                            return False
            
            # Insert the data into the table
            result = self.supabase.table(table_name).insert(data).execute()
            
            # Check for errors
            if hasattr(result, 'error') and result.error:
                print(f"Error inserting log into Supabase table {table_name}: {result.error}")
                return False
                
            return True
        except Exception as e:
            print(f"Exception inserting log into Supabase: {e}")
            return False

# Create a singleton instance
supabase_manager = SupabaseManager()