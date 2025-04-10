"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 5
RELEASE = 3
MATURITY = "alpha"  # "alpha", "beta", or "final"
PATCH = "819e820"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "819e820: Update color configuration in config.json.template for additional states",
    "b623742: Add color handling and configuration management to GUI",
    "a3f72c1: Add webcolors to requirements for color handling",
    "0f8c0ed: Add message type to mode change output in LogFileHandler",
    "93f3830: Add openai-api-key.txt to .gitignore",
    "a27a089: Fix truncation of long values in status board table rows",
    "aa1e911: Abbreviate column names in stats embed and truncate long values in table rows",
    "b499fe8: Add scripts to fetch and run the latest Docker image for SCLogAnalyzer bot",
    "6c81ef4: Fix log message visibility check in LogAnalyzerFrame",
]
