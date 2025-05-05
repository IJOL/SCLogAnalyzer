"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 8
RELEASE = 1
MATURITY = "checkmate"  # "alpha", "beta", or "final"
PATCH = "0fa6f44"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "44c0b3f: Update version.py to reflect new MINOR and RELEASE numbers",
    "da93f5b: Update maturity level in version.py from \"wikelo\" to \"checkmate\"",
    "6c0f90c: Refactor ConnectedUsersPanel and RealtimeBridge to use 'username' instead of 'user_id' and enhance logging with shard information",
    "d01f97f: Enhance RealtimeBridge and SupabaseManager for async client support and improved error handling",
    "cc26ebb: Enhance LogAnalyzerFrame to support debug mode initialization and adjust message logging level accordingly",
    "7d525c3: Refactor RealtimeBridge to use async Supabase client and add error handling for connection failures",
    "bc4a477: Remove active_users table checks and related logic from Supabase onboarding and RealtimeBridge",
    "9100e5b: Add Check DB button and database component verification in Supabase onboarding",
    "d6a518d: Add realtime users feature and connection bridge",
    "e99b427: Refactor configuration handling in ConfigDialog and LogAnalyzerFrame to improve change detection and event processing",
    "4e6bda6: Update regex pattern for player death to include additional conditions for killer identification",
]
