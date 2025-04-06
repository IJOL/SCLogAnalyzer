"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 5
RELEASE = 1
MATURITY = "alpha"  # "alpha", "beta", or "final"
PATCH = "a2e5ef2"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "a2e5ef2: Add functionality to fetch and update recent commit messages in version.py",
    "651ce04: Add recent commits section to About dialog and improve layout",
    "bc01c2c: Improve error handling in data fetching by logging errors to the text area instead of displaying message boxes",
    "4adf094: Increase message rate limiting timeout to 5 minutes and reduce max duplicates to 1",
    "3a7fba1: Remove default console key value for improved configuration flexibility",
    "6297d46: Update logging configuration to use application path and executable name for error log",
    "bf6f7c4: Update connection flow regex to exclude 'Unavailable' partner entities",
    "6b4f2ba: Implement message rate limiting to control repeated message outputs",
    "d2ebddf: Refine icon text rendering for better visibility and fit in smaller sizes",
    "c022275: Enhance icon generation to support multiple standard sizes and improve missing size handling",
    "c0a6625: Implement taskbar icon functionality with tooltip support in LogAnalyzerFrame",
    "f93a876: Add icon to SCLogAnalyzer executable in build workflow",
    "a766db8: Add icon creation and integration for SCLogAnalyzer",
    "f4adec7: Add connection flow logging and update vehicle destruction message format",
    "5a92bd9: Update regex pattern for player death to exclude 'Hazard' damage type",
    "0c2b8ff: Improve config dialog positioning and update behavior after closing",
    "7a1881e: Update startup button labels for clarity",
    "5fcd618: Remove message for latest version confirmation when up to date",
]
