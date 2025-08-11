"""
Utility for transferring data from Google Sheets to Supabase.

This module provides functionality to migrate data between data sources
in the SCLogAnalyzer application. It connects to both Google Sheets
and Supabase, fetches data from one, and imports it to the other.
"""

import sys
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple
import traceback
import hashlib
import json

from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_config_manager
from helpers.core.data_provider import GoogleSheetsDataProvider, SupabaseDataProvider
from helpers.core.supabase_manager import supabase_manager

class DataTransfer:
    """
    Class for handling data transfer between Google Sheets and Supabase.
    """
    SOURCE = "data_transfer"

    def __init__(self, config_manager=None, batch_size=50, max_retries=3, retry_delay=1.0):
        """
        Initialize the data transfer utility.
        
        Args:
            config_manager: Configuration manager instance. If None, one will be created.
            batch_size (int): Number of records to process in a single batch
            max_retries (int): Maximum retry attempts for operations
            retry_delay (float): Delay between retry attempts in seconds
        """
        self.config_manager = config_manager or get_config_manager()
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.gs_provider = None
        self.sb_provider = None

    def setup_providers(self) -> Tuple[bool, bool]:
        """
        Set up both data providers.
        
        Returns:
            Tuple[bool, bool]: (Google Sheets connected, Supabase connected)
        """
        # Set up Google Sheets provider
        google_sheets_webhook = self.config_manager.get('google_sheets_webhook', '')
        self.gs_provider = GoogleSheetsDataProvider(
            webhook_url=google_sheets_webhook,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay
        )

        # Set up Supabase provider
        if not supabase_manager.is_connected():
            if not supabase_manager.connect(config_manager=self.config_manager):
                message_bus.publish(
                    content="Failed to connect to Supabase. Transfer cannot continue.",
                    level=MessageLevel.ERROR,
                    metadata={"source": self.SOURCE}
                )
                return self.gs_provider.is_connected(), False
        
        self.sb_provider = SupabaseDataProvider(
            max_retries=self.max_retries,
            retry_delay=self.retry_delay
        )
        
        # Log connection status
        gs_connected = self.gs_provider.is_connected()
        sb_connected = self.sb_provider.is_connected()
        
        message_bus.publish(
            content=f"Data providers connection status: Google Sheets: {gs_connected}, Supabase: {sb_connected}",
            level=MessageLevel.INFO,
            metadata={"source": self.SOURCE}
        )
        
        return gs_connected, sb_connected

    def get_sheets_list(self) -> List[str]:
        """
        Get list of available sheets from Google Sheets.
        
        Returns:
            List[str]: List of available sheet names
        """
        try:
            # For now, we'll use a hardcoded list of common sheets we expect to find
            # In a future version, we can implement dynamic sheet discovery
            common_sheets = [
                "Config", 
                "SC_Default",
                "EA_SquadronBattle",
                "Materials"
            ]
            
            # Add additional sheets from config if available
            additional_sheets = self.config_manager.get('sheets', [])
            if isinstance(additional_sheets, list):
                sheets = list(set(common_sheets + additional_sheets))
            else:
                sheets = common_sheets
            
            message_bus.publish(
                content=f"Found {len(sheets)} sheets to transfer: {', '.join(sheets)}",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
            
            return sheets
        except Exception as e:
            message_bus.publish(
                content=f"Error getting sheet list: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return []

    def transfer_sheet(self, sheet_name: str, purge_first: bool = True) -> Tuple[int, int]:
        """
        Transfer data from a specific Google Sheet to Supabase.
        
        Args:
            sheet_name (str): Name of the sheet to transfer
            purge_first (bool): Whether to purge existing data before transfer (default: True)
            
        Returns:
            Tuple[int, int]: (Number of records processed, number of successful transfers)
        """
        message_bus.publish(
            content=f"Starting transfer of sheet: {sheet_name}",
            level=MessageLevel.INFO,
            metadata={"source": self.SOURCE}
        )

        # First, purge the existing data in the table if it exists and purge_first is True
        if purge_first and self.sb_provider and self.sb_provider.is_connected():
            message_bus.publish(
                content=f"Purging existing data for sheet: {sheet_name}",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
            # Use the purge method from the data provider
            self.sb_provider.purge(sheet_name)
        elif not purge_first and self.sb_provider and self.sb_provider.is_connected():
            message_bus.publish(
                content=f"Skipping purge for sheet: {sheet_name} - will check for duplicates",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )

        # Fetch data from Google Sheets
        gs_data = self.gs_provider.fetch_data(sheet_name)
        
        if not gs_data:
            message_bus.publish(
                content=f"No data found in Google Sheets for sheet: {sheet_name}",
                level=MessageLevel.WARNING,
                metadata={"source": self.SOURCE}
            )
            return 0, 0
            
        message_bus.publish(
            content=f"Retrieved {len(gs_data)} records from Google Sheets for sheet: {sheet_name}",
            level=MessageLevel.INFO,
            metadata={"source": self.SOURCE}
        )
        
        # If we're not purging first, we need to filter out duplicates
        filtered_gs_data = gs_data
        if not purge_first and self.sb_provider and self.sb_provider.is_connected():
            # Fetch only hashes from Supabase for efficient duplicate detection
            message_bus.publish(
                content=f"Fetching record hashes from Supabase for duplicate detection",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
            # Use the dedicated RPC function to get hashes
            supabase_hashes = set(self.sb_provider.fetch_record_hashes(sheet_name))
            
            if supabase_hashes:
                # Filter out records that already exist in Supabase
                filtered_gs_data = []
                
                for record in gs_data:
                    # Calculate hash in the same way as in PostgreSQL
                    # This has to match the MD5 calculation in the get_table_record_hashes function
                    hash_input = (
                        str(record.get('username', '')) +
                        str(record.get('killer', '')) +
                        str(record.get('victim', '')) +
                        str(record.get('timestamp', '')) 
                    )
                    record_hash = hashlib.md5(hash_input.encode()).hexdigest()
                    
                    if record_hash not in supabase_hashes:
                        filtered_gs_data.append(record)
                
                duplicate_count = len(gs_data) - len(filtered_gs_data)
                message_bus.publish(
                    content=f"Found {duplicate_count} duplicate records to skip ({duplicate_count * 100.0 / len(gs_data):.1f}%)",
                    level=MessageLevel.INFO,
                    metadata={"source": self.SOURCE}
                )
            else:
                message_bus.publish(
                    content=f"No existing data found in Supabase, will insert all records",
                    level=MessageLevel.INFO,
                    metadata={"source": self.SOURCE}
                )
        
        # If no records to insert after filtering, return early
        if not filtered_gs_data:
            message_bus.publish(
                content=f"No new records to insert for sheet: {sheet_name}",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
            return len(gs_data), 0
        
        # Process in batches to avoid overloading the database
        batches = [filtered_gs_data[i:i + self.batch_size] for i in range(0, len(filtered_gs_data), self.batch_size)]
        
        total_processed = len(gs_data)  # Total includes duplicates we skipped
        total_success = 0
        
        for batch_idx, batch in enumerate(batches):
            message_bus.publish(
                content=f"Processing batch {batch_idx + 1}/{len(batches)} for sheet: {sheet_name}",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
            
            # Format data in the expected batch format for the provider
            supabase_batch = []
            for item in batch:
                supabase_batch.append({
                    'data': item,
                    'sheet': sheet_name
                })
            
            # Submit the batch to Supabase
            success = self.sb_provider.process_data(supabase_batch)
            
            # Update success counter
            if success:
                total_success += len(batch)  # This is approximate since we don't have item-level status
            
            # Add a small delay between batches to avoid rate limiting
            if batch_idx < len(batches) - 1:  # Don't delay after the last batch
                time.sleep(0.5)
                
        return total_processed, total_success

    def transfer_all_data(self, purge_first: bool = True) -> Dict[str, Tuple[int, int]]:
        """
        Transfer all data from Google Sheets to Supabase.
        
        Args:
            purge_first (bool): Whether to check for duplicates on tables with "_" in name
            This will be overridden for:
            - Tables WITHOUT "_" in name: Always purged before transfer
            - Tables WITH "_" in name: Will respect purge_first parameter
            
        Returns:
            Dict[str, Tuple[int, int]]: Results for each sheet (processed, successful)
        """
        # Set up data providers
        gs_connected, sb_connected = self.setup_providers()
        
        if not gs_connected:
            message_bus.publish(
                content="Google Sheets provider is not connected. Cannot transfer data.",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return {}
            
        if not sb_connected:
            message_bus.publish(
                content="Supabase provider is not connected. Cannot transfer data.",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return {}
        
        # Get list of sheets to transfer
        sheets = [
                "SC_Default",
                "EA_SquadronBattle",
                "Materials"
            ]        
        # Transfer each sheet
        results = {}
        for sheet in sheets:
            try:
                # Determine whether to purge based on sheet name:
                # - Tables WITH "_": Follow the purge_first parameter (for duplicate checking)
                # - Tables WITHOUT "_": Always purge before transfer
                if "_" in sheet:
                    sheet_purge_first = purge_first
                    message_bus.publish(
                        content=f"Table {sheet} contains an underscore - {'checking for duplicates' if not purge_first else 'will be purged as requested'}",
                        level=MessageLevel.INFO,
                        metadata={"source": self.SOURCE}
                    )
                else:
                    sheet_purge_first = True  # Always purge tables without underscore
                    message_bus.publish(
                        content=f"Table {sheet} does not contain an underscore - will be purged before transfer (forced)",
                        level=MessageLevel.INFO,
                        metadata={"source": self.SOURCE}
                    )
                
                processed, success = self.transfer_sheet(sheet, sheet_purge_first)
                results[sheet] = (processed, success)
            except Exception as e:
                message_bus.publish(
                    content=f"Error transferring sheet '{sheet}': {e}",
                    level=MessageLevel.ERROR,
                    metadata={"source": self.SOURCE}
                )
                message_bus.publish(
                    content=traceback.format_exc(),
                    level=MessageLevel.DEBUG,
                    metadata={"source": self.SOURCE}
                )
                results[sheet] = (0, 0)
        
        # Summarize results
        total_processed = sum(processed for processed, _ in results.values())
        total_success = sum(success for _, success in results.values())
        message_bus.publish(
            content=f"Transfer complete. Processed {total_processed} records, successfully transferred {total_success} records.",
            level=MessageLevel.INFO,
            metadata={"source": self.SOURCE}
        )
        
        return results
        
    def transfer_config(self) -> bool:
        """
        Transfer configuration data from Google Sheets to Supabase.
        
        Returns:
            bool: True if successful, False otherwise
        """
        message_bus.publish(
            content="Starting configuration transfer from Google Sheets to Supabase",
            level=MessageLevel.INFO,
            metadata={"source": self.SOURCE}
        )
        
        # Set up data providers
        gs_connected, sb_connected = self.setup_providers()
        
        if not gs_connected or not sb_connected:
            message_bus.publish(
                content="One or both data providers are not connected. Cannot transfer config.",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
            return False
        
        # Fetch configuration from Google Sheets
        gs_config = self.gs_provider.fetch_config()
        
        if not gs_config:
            message_bus.publish(
                content="No configuration data found in Google Sheets.",
                level=MessageLevel.WARNING,
                metadata={"source": self.SOURCE}
            )
            return False
        
        message_bus.publish(
            content=f"Retrieved {len(gs_config)} configuration items from Google Sheets",
            level=MessageLevel.INFO,
            metadata={"source": self.SOURCE}
        )
        
        # Format config data for Supabase
        supabase_batch = []
        for key, value in gs_config.items():
            supabase_batch.append({
                'data': {'key': key, 'value': value},
                'sheet': 'Config'
            })
        
        # Submit the batch to Supabase
        success = self.sb_provider.process_data(supabase_batch)
        
        if success:
            message_bus.publish(
                content=f"Successfully transferred {len(gs_config)} configuration items to Supabase",
                level=MessageLevel.INFO,
                metadata={"source": self.SOURCE}
            )
        else:
            message_bus.publish(
                content="Failed to transfer configuration to Supabase",
                level=MessageLevel.ERROR,
                metadata={"source": self.SOURCE}
            )
        
        return success


def transfer_all_data_to_supabase(config_manager=None, batch_size=50, purge_first=True):
    """
    Helper function to transfer all data from Google Sheets to Supabase.
    
    Args:
        config_manager: Configuration manager instance
        batch_size (int): Records per batch to process
        purge_first (bool): Whether to purge existing data before transfer (default: True)
        
    Returns:
        bool: True if transfer was successful (includes when all records were filtered as duplicates)
    """
    transfer = DataTransfer(
        config_manager=config_manager,
        batch_size=batch_size
    )
    
    results = transfer.transfer_all_data(purge_first=purge_first)
    
    if not results:
        message_bus.publish(
            content="No data transferred to Supabase.",
            level=MessageLevel.WARNING,
            metadata={"source": DataTransfer.SOURCE}
        )
        return False    
    return True


def transfer_config_to_supabase(config_manager=None):
    """
    Helper function to transfer just configuration from Google Sheets to Supabase.
    
    Args:
        config_manager: Configuration manager instance
        
    Returns:
        bool: True if successful
    """
    transfer = DataTransfer(config_manager=config_manager)
    return transfer.transfer_config()


async def async_transfer_all(config_manager=None, batch_size=50):
    """
    Async helper function to transfer all data from Google Sheets to Supabase.
    
    Args:
        config_manager: Configuration manager instance
        batch_size (int): Records per batch to process
        
    Returns:
        bool: True if transfer was mostly successful
    """
    # Run the transfer in a thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        transfer_all_data_to_supabase,
        config_manager,
        batch_size
    )


if __name__ == "__main__":
    # Run the transfer if this script is executed directly
    from helpers.core.message_bus import setup_console_handler
    
    # Set up console output for message bus
    setup_console_handler()
    
    # Get config manager and run transfer
    config = get_config_manager()
    success = transfer_all_data_to_supabase(config)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)