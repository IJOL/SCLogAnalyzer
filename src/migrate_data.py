#!/usr/bin/env python
"""
Google Sheets to Supabase Data Migration Tool

This script provides a command-line interface for transferring data from 
Google Sheets to Supabase in the SCLogAnalyzer application.
"""

import sys
import argparse
import time
from typing import Dict, Tuple

from helpers.message_bus import message_bus, MessageLevel, setup_console_handler
from helpers.config_utils import get_config_manager
from helpers.data_transfer import transfer_all_data_to_supabase, transfer_config_to_supabase

def setup_argument_parser() -> argparse.ArgumentParser:
    """Set up and return the argument parser for the command-line interface."""
    parser = argparse.ArgumentParser(
        description="Transfer data from Google Sheets to Supabase for SCLogAnalyzer",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--config-only', 
        action='store_true',
        help='Transfer only configuration data (Config sheet)'
    )
    
    parser.add_argument(
        '--batch-size', 
        type=int, 
        default=50,
        help='Number of records to process in a single batch'
    )
    
    parser.add_argument(
        '--verbose', 
        '-v',
        action='store_true',
        help='Enable verbose output with detailed logs'
    )
    
    parser.add_argument(
        '--max-retries', 
        type=int, 
        default=3,
        help='Maximum number of retry attempts for operations'
    )
    
    parser.add_argument(
        '--retry-delay', 
        type=float, 
        default=1.0,
        help='Delay in seconds between retry attempts'
    )
    
    parser.add_argument(
        '--check-connections-only', 
        action='store_true',
        help='Only check connections to both services and exit'
    )
    
    parser.add_argument(
        '--config-path',
        type=str,
        help='Optional path to a specific config.json file'
    )
    
    return parser

def check_connections() -> Tuple[bool, bool]:
    """
    Check connections to both Google Sheets and Supabase.
    
    Returns:
        Tuple[bool, bool]: (Google Sheets connected, Supabase connected)
    """
    from helpers.data_transfer import DataTransfer
    
    # Create DataTransfer instance and check connections
    transfer = DataTransfer()
    return transfer.setup_providers()

def main():
    """Main entry point for the data transfer script."""
    # Set up argument parser and parse arguments
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Set up console handler for message bus with appropriate verbosity
    setup_console_handler(debug=args.verbose)
    
    # Get configuration manager
    config_manager = get_config_manager(args.config_path) if args.config_path else get_config_manager()
    
    # Check if we're only checking connections
    if args.check_connections_only:
        gs_connected, sb_connected = check_connections()
        
        print(f"Google Sheets connection: {'SUCCESSFUL' if gs_connected else 'FAILED'}")
        print(f"Supabase connection: {'SUCCESSFUL' if sb_connected else 'FAILED'}")
        
        # Set exit code based on connections
        return 0 if gs_connected and sb_connected else 1
    
    # Start the transfer process
    start_time = time.time()
    message_bus.publish(
        content="Starting Google Sheets to Supabase data transfer",
        level=MessageLevel.INFO
    )
    
    # Perform the transfer based on arguments
    if args.config_only:
        success = transfer_config_to_supabase(config_manager)
    else:
        success = transfer_all_data_to_supabase(
            config_manager=config_manager,
            batch_size=args.batch_size
        )
    
    # Report overall completion
    elapsed_time = time.time() - start_time
    message_bus.publish(
        content=f"Transfer {'completed successfully' if success else 'failed'} in {elapsed_time:.2f} seconds",
        level=MessageLevel.INFO if success else MessageLevel.ERROR
    )
    
    # Update the datasource setting in config to Supabase if transfer was successful
    if success:
        config_manager.set('datasource', 'supabase')
        config_manager.save_config()
        message_bus.publish(
            content="Default data source has been set to 'supabase' in configuration",
            level=MessageLevel.INFO
        )
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)