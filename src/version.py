"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 16
RELEASE = 1
MATURITY = "laminas"  # "alpha", "beta", or "final"
PATCH = "4dd7627"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.16.x series,
    "4dd7627: refactor: Enhance auto-sizing mechanism in DarkListCtrl to prevent multiple calls",
    "747ec20: refactor: Improve shard entry validation logic in ShardListWidget"
]
