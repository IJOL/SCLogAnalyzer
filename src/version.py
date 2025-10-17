"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 17
RELEASE = 0
MATURITY = "onyx"  # "alpha", "beta", or "final"
PATCH = "d476f9d"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.16.x series,
    "d476f9d: feat: Update .gitignore to include new directories for rsi_browser_session, specs, specify, spec-workflow, and qwen",
    "1b43959: feat: Enhance LogFileHandler by managing message bus subscriptions for proper cleanup",
    "9e91dda: feat: Enhance chat functionality by adding username handling and improving user list management",
    "d388917: refactor: Update message_bus publish calls to use keyword arguments for clarity",
    "82fbb30: feat: Load current connected users from RealtimeBridge in chat widget",
    "102370c: feat: Load current connected users from RealtimeBridge in tournament creation dialog",
    "cc4234e: feat: Add method to retrieve currently connected users synchronously",
    "5136583: chore: Remove obsolete contract tests for CorpseManager and TournamentManager",
    "eb8840b: feat: Implement tournament abandonment feature with UI button and event handling",
    "1425436: feat: Simplify player details panel and enhance tournament data refresh logic",
    "0608b2f: Refactor import path for TournamentWidget to align with new directory structure",
    "a6b72c9: feat: Enhance ConfigManager with key management for runtime flags and hidden configs",
    "f087e54: feat: Refactor tournament participant handling to use teams structure",
    "f4a21ec: refactor: Simplify _update_active_tournament_panel method calls by removing unnecessary parameters",
    "3eaf0bb: feat: Update admin controls visibility based on user privileges",
    "7bd9208: feat: Remove redundant RLS policies for tournaments and tournament corpses",
    "a617342: feat: Add 'tournament_admins' to config filtering and hide in config dialog",
    "9a64623: feat: Show corpse and combat event management buttons only in debug mode",
    "014721b: feat: Include username in tournament activation process",
    "6f294e2: feat: Add completion timestamp and enhance schema initialization with table existence checks",
    "6903a9a: feat: Enhance tournament activation with metadata and conditional corpse detection",
    "2d2dd62: feat: Implement Row Level Security (RLS) policies for tournaments and tournament corpses",
    "b388d5b: refactor: Update corpse detection event handling to use remote realtime events",
    "ddfc31b: Refactor TournamentWidget layout and functionality",
    "31d1c23: feat: Add chat widget and integrate chat functionality into main frame",
    "a45bd91: refactor: Remove UltimateListCtrl patch and related functionality",
    "08bbd34: feat: Add tournament management features including retrieval and deletion of tournaments, and player combat history",
    "deb6230: Refactor tournament management UI and logic",
    "a3ce31f: Add tournament management system",
    "db4b9bf: refactor: Implement optimal threshold calculation for QR code binarization in LogFileHandler",
    "470f02a: refactor: Update screenshots folder path derivation to use current log file path from config manager",
    "25893fe: refactor: Update .gitignore to include new directories for Claude, planning documents, and RSI browser session",
    "04690d6: refactor: Remove unnecessary comment regarding dynamic tab query normalization in SupabaseDataProvider",
    "6c83810: refactor: Remove legacy view methods in SupabaseDataProvider; update DataDisplayManager and main_frame to use execute_generic_query for dynamic tabs",
    "ebec820: refactor: Update sorting logic in StalledWidget to order by timestamp instead of count",
    "ee93899: refactor: Update import statements to use absolute paths for core modules"
]
