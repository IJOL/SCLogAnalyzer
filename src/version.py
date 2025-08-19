"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 16
RELEASE = 3
MATURITY = "laminas"  # "alpha", "beta", or "final"
PATCH = "afaaa19"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.16.x series,
    "afaaa19: feat: Implement generic query function for dynamic query execution in SupabaseDataProvider",
    "e4c01e8: refactor: Add 'live' parameter to on_mode_change method for enhanced event handling",
    "9d35322: refactor: Add 'live' parameter to mode_change events for improved event handling",
    "61a714c: feature: Daily kills view"
]
