"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 6
RELEASE = 5
MATURITY = "wikelo"  # "alpha", "beta", or "final"
PATCH = "9bf5300"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "9bf5300: Refactor Supabase connection logic to prevent deadlock during datasource switching",
]
