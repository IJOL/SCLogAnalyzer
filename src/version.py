"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 8
RELEASE = 5
MATURITY = "checkmate"  # "alpha", "beta", or "final"
PATCH = "9e97466"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.8.x series

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
]
