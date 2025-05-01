"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 6
RELEASE = 7
MATURITY = "wikelo"  # "alpha", "beta", or "final"
PATCH = "ea69837"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "ea69837: Enhance ConfigManager: Add new keys to preserve and streamline config filtering",
    "282cbe8: Adjust GUI mode log entry yield frequency from 10 to 4",
    "e3f3790: Update player_death regex pattern to exclude Shipjacker_ from victim matching",
    "267b3b4: Skip data processing for PTU versions in LogFileHandler",
    "3121e94: Add server endpoint regex to detect version changes and notify on updates",
    "c772bd2: Add hash_value generated column to table creation in SupabaseManager",
]
