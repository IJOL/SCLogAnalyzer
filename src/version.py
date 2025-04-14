"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 6
RELEASE = 0
MATURITY = "alpha"  # "alpha", "beta", or "final"
PATCH = "a1d4287"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "a1d4287: Refactor update process: move update logic to updater module and simplify check for updates",
    "7dd8a9c: Enhance LogAnalyzerFrame: add asynchronous tab initialization and debug mode toggle functionality",
    "11dd869: Refactor ConfigManager: update configuration renewal logic to use versioning instead of renew flag",
    "7e9fe78: Enhance LogAnalyzerFrame: reload configuration only if changes were saved in the config dialog",
    "c4cf543: Enhance ConfigDialog: add config_saved flag to track configuration save status",
    "7e63cb6: Enhance ConfigManager: implement configuration renewal logic based on versioning and preserve specific keys",
    "870a474: Refactor startup function: remove unnecessary kwargs from log file path handling",
    "8123f3f: Refactor ConfigManager: add filtering method to exclude unwanted configuration values during save and retrieval",
    "bb1911b: Update color scheme in config: change \"red,white\" to \"white,gray\" for player_death",
    "f6e5be2: Enhance LogAnalyzerFrame: streamline configuration handling and remove deprecated renew_config method",
    "0109b38: Refactor ConfigDialog: integrate ConfigManager for configuration handling and streamline save process",
    "af0b936: Refactor ConfigManager: remove renew_config method and streamline configuration renewal process",
    "56ea772: Remove merge_configs function: eliminate unused deep merge logic from config handling",
    "e8d2d20: Enhance ConfigManager: validate webhook URL before fetching dynamic config",
    "5185349: Enhance LogAnalyzerFrame and LogFileHandler: add username change handling, initialize state properties, and streamline tab management",
    "62cf7a2: Refactor LogFileHandler to retrieve config manager internally and streamline initialization",
    "69764c1: Refactor configuration handling in LogAnalyzerFrame: consolidate loading, validation, and renewal into initialize_config method",
    "e03248a: Enhance ConfigManager integration in GUI: pass in_gui flag and streamline config loading",
    "255d58c: Refactor LogFileHandler to use get_config_manager for configuration management",
    "b3422b1: Implement singleton pattern for ConfigManager with thread safety",
    "a71c606: Refactor LogFileHandler to use ConfigManager for configuration management and streamline initialization",
    "77067ba: Add URL validation and config override method to ConfigManager",
    "2865977: Implement ConfigManager class for enhanced configuration management and dynamic updates",
    "2879227: Refactor dynamic config loading and merging",
    "1417326: Enhance update process with progress dialog and error handling for downloads and installations",
    "7019bc1: Refactor leaderboard message handling to use a combined embed format and improve initialization logic",
    "ecaa518: Enhance leaderboard message handling and update logic with improved logging and configurable update intervals",
    "cb361ce: Refactor alert message handling for important players in Discord notifications",
    "05f7d85: Add leaderboard embed initialization and update functionality",
    "ac1fa93: Refactor stats message initialization to search for existing embed before creating a new one",
    "8f4e54d: Refactor update interval for stats task to be configurable",
    "10b71ad: Refactor configuration merging to support deep merging of static and dynamic configurations",
    "3e049f4: Enhance player death message formatting in config.json.template",
    "256c2b6: Add dynamic configuration fetching and merging for Discord webhooks",
    "e37b9c4: Refactor startup message handling for Discord integration in log_analyzer.py",
    "6c0f925: Fix regex pattern for player death event in config.json.template",
    "1980012: Enhance Docker image loading and running process with output capture and error handling",
]
