"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 6
RELEASE = 8
MATURITY = "wikelo"  # "alpha", "beta", or "final"
PATCH = "e86e1a9"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "e86e1a9: Refactor SupabaseManager to improve CREATE TABLE statement generation and add SQL functions for hash generation and table listing",
    "45ec5e6: Migrated from Event class to MessageBus event system",
    "cae4973: Fix hash_value column generation to use epoch timestamp for improved accuracy and enable datetime string handling in table creation",
    "3ad1867: Decouple event subscriptions from LogFileHandler initialization",
    "3e578f5: Implement event bus functionality in MessageBus",
    "ba4bb76: Add event emission and subscription methods to MessageBus",
]
