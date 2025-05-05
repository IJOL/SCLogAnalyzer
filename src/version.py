"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 8
RELEASE = 2
MATURITY = "checkmate"  # "alpha", "beta", or "final"
PATCH = "1450824"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "1450824: Refactor RealtimeBridge to simplify broadcast channel usage by replacing manual send with send_broadcast method",
]
