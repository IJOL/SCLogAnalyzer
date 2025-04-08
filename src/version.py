"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 5
RELEASE = 2
MATURITY = "alpha"  # "alpha", "beta", or "final"
PATCH = "25f8774"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "25f8774: Update regex pattern for player death log to exclude specific prefixes",
    "5a8777a: Add dynamic mode label to GUI and update related methods",
    "537f880: Add color-coded log messages and new Test Google Sheets button",
]
