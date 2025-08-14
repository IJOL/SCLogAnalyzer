"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 16
RELEASE = 2
MATURITY = "laminas"  # "alpha", "beta", or "final"
PATCH = "367cdfa"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.16.x series,
    "367cdfa: refactor: Invalidate metadata cache in SupabaseDataProvider and DataDisplayManager to ensure new views are recognized",
    "680b52a: refactor: Remove stdout redirection from MessageBus to resolve infinite loop in debug mode",
    "224b831: refactor: Remove unused import of ThreadPoolExecutor in RealtimeBridge"
]
