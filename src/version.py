"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 6
RELEASE = 4
MATURITY = "alpha"  # "alpha", "beta", or "final"
PATCH = "dad101b"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "dad101b: Enhance add_state_data method to preserve original order of data dict",
    "2140b4e: Fix debug log to display original data keys on insert failure",
]
