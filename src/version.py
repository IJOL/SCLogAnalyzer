"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 4
RELEASE = 0
MATURITY = "alpha"  # "alpha", "beta", or "final"
PATCH = "01afe21"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION
