"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 4
RELEASE = 1
MATURITY = "alpha"  # "alpha", "beta", or "final"
PATCH = "54a8a49"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION
