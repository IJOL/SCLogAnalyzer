"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 6
RELEASE = 6
MATURITY = "wikelo"  # "alpha", "beta", or "final"
PATCH = "67cbb03"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "67cbb03: Refactor tab initialization method and update version maturity label",
    "12fdc3f: Implement single-instance check using mutex in main application entry point",
    "d5f4899: Refactor build-on-tag workflow to comment out log_analyzer build and release steps, focusing on SCLogAnalyzer",
    "51399de: Add GUI mode support to LogFileHandler for periodic yielding during log processing",
    "a6a1d91: Refactor tab refresh logic to eliminate unnecessary pre-loading and update refresh button to use an icon",
    "fd19be5: Add event handling for notebook page changes to refresh grid data",
    "ba7cf57: Enhance message bus subscription to support historical message replay and add parameters for filtering",
    "c7f9a0a: Improve save_config method to handle lock contention with background thread support",
]
