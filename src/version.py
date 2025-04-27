"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 6
RELEASE = 3
MATURITY = "alpha"  # "alpha", "beta", or "final"
PATCH = "cc5465a"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "cc5465a: Add Supabase dependency for integration",
]
