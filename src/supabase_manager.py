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
                
            # Create client without any additional parameters that might cause issues
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
                    
                    print(f"Table cache refreshed using PostgREST schema discovery. Found {len(self.existing_tables)} tables.")
                    return
            except Exception as e:
                print(f"PostgREST schema discovery approach failed: {e}")
                
            # Fall back to direct querying of tables
            self._refresh_table_cache_fallback()
            
        except Exception as e:
            print(f"Error refreshing table cache: {e}")
            # Don't clear the cache on error - conservative approach
            
    def _refresh_table_cache_fallback(self):
        """
        Robust method to refresh the table cache when direct metadata queries aren't possible.
        Detects tables by probing for their existence and builds a cache over time.
        """
        # Reset the table cache time to indicate a refresh was attempted
        self.table_cache_time = time.time()
        
        # Standard tables to check - expand this list based on your application's needs
        standard_tables = [
            "game_logs", 
            "default_logs",
            # Add other known table names your application might use
        ]
        
        # Add any tables we've successfully used before to the check list
        all_tables_to_check = list(standard_tables)
        
        # If we've previously detected tables, add them to our check list
        # but avoid duplicates
        for existing_table in self.existing_tables:
            if existing_table not in all_tables_to_check:
                all_tables_to_check.append(existing_table)
        
        # Track newly confirmed tables
        confirmed_tables = set()
        
        # Track tables confirmed to not exist
        nonexistent_tables = set()
        
        # Check each table
        for table in all_tables_to_check:
            try:
                # Just fetch the count which is minimal data
                response = self.supabase.table(table).select('*', count='exact').limit(0).execute()
                
                # If we get here without error, the table exists
                confirmed_tables.add(table)
                print(f"Confirmed table exists: {table}")
            except Exception as e:
                error_str = str(e).lower()
                # Check if the error indicates table doesn't exist
                if ("relation" in error_str and "does not exist" in error_str) or "not found" in error_str:
                    nonexistent_tables.add(table)
                    print(f"Confirmed table does not exist: {table}")
                else:
                    # For other errors, we're uncertain - be conservative and assume it might exist
                    print(f"Uncertain about table {table}: {e}")
        
        # Update our cache:
        # 1. Remove tables confirmed to not exist
        self.existing_tables -= nonexistent_tables
        
        # 2. Add tables confirmed to exist
        self.existing_tables.update(confirmed_tables)
        
        # Log the results
        print(f"Table cache refreshed. Known tables: {', '.join(sorted(self.existing_tables)) if self.existing_tables else 'none'}")
    
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
            # Since we can't use raw SQL in this Supabase instance,
            # we'll attempt to create the table by inserting data
            # and letting Supabase auto-create the table with appropriate types
            
            # First, ensure we have the minimum fields needed
            insert_data = data.copy()
            
            # Strip any fields that might cause issues
            if 'id' in insert_data:
                del insert_data['id']  # Don't specify ID for new records
                
            if 'created_at' in insert_data:
                del insert_data['created_at']  # Let Supabase handle this
                
            # Try to insert the data, which may auto-create the table
            # Note: This depends on your Supabase configuration allowing table creation
            # If table auto-creation isn't enabled, this will fail
            try:
                result = self.supabase.table(table_name).insert(insert_data).execute()
                
                # If we get here without error, table was created or already existed
                self.existing_tables.add(table_name)
                print(f"Created or verified table {table_name} in Supabase")
                return True
            except Exception as e:
                error_msg = str(e)
                
                # If table creation is not enabled, or another error occurred
                print(f"Error creating table through insert: {error_msg}")
                return False
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