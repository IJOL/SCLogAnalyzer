"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 8
RELEASE = 5
MATURITY = "checkmate"  # "alpha", "beta", or "final"
PATCH = "4ebab35"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.8.x series
    "4e6bda6: Update regex pattern for player death to include additional conditions for killer identification",
    "e99b427: Refactor configuration handling in ConfigDialog and LogAnalyzerFrame to improve change detection and event processing",
    "d6a518d: Add realtime users feature and connection bridge",
    "9100e5b: Add Check DB button and database component verification in Supabase onboarding",
    "bc4a477: Remove active_users table checks and related logic from Supabase onboarding and RealtimeBridge",
    "7d525c3: Refactor RealtimeBridge to use async Supabase client and add error handling for connection failures",
    "cc26ebb: Enhance LogAnalyzerFrame to support debug mode initialization and adjust message logging level accordingly",
    "d01f97f: Enhance RealtimeBridge and SupabaseManager for async client support and improved error handling",
    "6c0f90c: Refactor ConnectedUsersPanel and RealtimeBridge to use 'username' instead of 'user_id' and enhance logging with shard information",
    "da93f5b: Update maturity level in version.py from \"wikelo\" to \"checkmate\"",
    "44c0b3f: Update version.py to reflect new MINOR and RELEASE numbers",

    # Version v0.8.0-44c0b3f-checkmate-docker
    "0fa6f44: Increment version to v0.8.0-44c0b3f-checkmate",

    # Version v0.8.1-0fa6f44-checkmate-docker
    "385ec00: Increment version to v0.8.1-0fa6f44-checkmate",
    "1450824: Refactor RealtimeBridge to simplify broadcast channel usage by replacing manual send with send_broadcast method",

    # Version v0.8.2-1450824-checkmate-docker
    "1b1ebe5: Increment version to v0.8.2-1450824-checkmate",
    "bc8a4f2: Use run_async to handle presence state updates in RealtimeBridge",

    # Version v0.8.3-bc8a4f2-checkmate-docker
    "d2a299d: Increment version to v0.8.3-bc8a4f2-checkmate",
    "e1d0ab3: Enhance SupabaseDataProvider view creation logic and adjust message levels in MessageBus",
    "157edc5: Add anonymous authentication support in SupabaseManager",
    "30cde10: Refactor build process: consolidate increment_version.py and build.bat into a single build.py script",
    "e582e2d: Remove redundant build argument in main function of build.py",
    "99fe424: Update async client retrieval in RealtimeBridge to use username for better context",
    "3f5ec0d: Refactor SupabaseManager: enhance async connection handling and remove unused anonymous sign-in method",
    "42482b1: Increment version to v0.8.4-3f5ec0d-checkmate",

    # Version v0.8.4-3f5ec0d-checkmate-docker
    "9e97466: Add launch configuration for building project in VSCode",
    "83b41d7: Increment version to v0.8.5-9e97466-checkmate",

    # Version v0.8.5-9e97466-checkmate-docker
    "4ebab35: Refactor launch configurations in VSCode and update version increment logic to fetch commits from the first tag of the current major.minor version",
]
