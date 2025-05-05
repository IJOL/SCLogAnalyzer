"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 8
RELEASE = 3
MATURITY = "checkmate"  # "alpha", "beta", or "final"
PATCH = "bc8a4f2"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "bc8a4f2: Use run_async to handle presence state updates in RealtimeBridge",
]
