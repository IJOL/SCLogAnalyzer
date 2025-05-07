"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 8
RELEASE = 4
MATURITY = "checkmate"  # "alpha", "beta", or "final"
PATCH = "3f5ec0d"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.8.x series
    "e1d0ab3: Enhance SupabaseDataProvider view creation logic and adjust message levels in MessageBus",
    "157edc5: Add anonymous authentication support in SupabaseManager",
    "30cde10: Refactor build process: consolidate increment_version.py and build.bat into a single build.py script",
    "e582e2d: Remove redundant build argument in main function of build.py",
    "99fe424: Update async client retrieval in RealtimeBridge to use username for better context",
    "3f5ec0d: Refactor SupabaseManager: enhance async connection handling and remove unused anonymous sign-in method",
]
