"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 17
RELEASE = 3
MATURITY = "onyx"  # "alpha", "beta", or "final"
PATCH = "e34d102"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.17.x series,
    "e34d102: feat: Refactor context menu actions for timers and alarms in AlarmsTimersWidget",
    "a667494: feat: Add sharing functionality for alarms and handle remote alarm events",
    "6634ee9: feat: Integrate Alarms and Timers widget into Connected Users Panel",
    "f767455: feat: Add requirements.in and update requirements.txt with complete dependency list",

    # Version v0.17.2-79946b4-onyx-docker,
    "7ba8054: [chore] Increment version to v0.17.2-79946b4-onyx",
    "79946b4: feat: Add hidden imports for wxPython in build scripts and update requirements",

    # Version v0.17.1-da462c8-onyx-docker,
    "5b991b7: [chore] Increment version to v0.17.1-da462c8-onyx",
    "da462c8: Add hidden imports for wxPython and clean up build.py",

    # Version v0.17.0-d476f9d-onyx-docker,
    "9f5ef26: [chore] Increment version to v0.17.0-d476f9d-onyx",
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
    "ee93899: refactor: Update import statements to use absolute paths for core modules",

    # Version v0.16.3-afaaa19-laminas-docker,
    "0631f08: [chore] Increment version to v0.16.3-afaaa19-laminas",
    "afaaa19: feat: Implement generic query function for dynamic query execution in SupabaseDataProvider",
    "e4c01e8: refactor: Add 'live' parameter to on_mode_change method for enhanced event handling",
    "9d35322: refactor: Add 'live' parameter to mode_change events for improved event handling",
    "61a714c: feature: Daily kills view",

    # Version v0.16.2-367cdfa-laminas-docker,
    "0750c8a: [chore] Increment version to v0.16.2-367cdfa-laminas",
    "367cdfa: refactor: Invalidate metadata cache in SupabaseDataProvider and DataDisplayManager to ensure new views are recognized",
    "680b52a: refactor: Remove stdout redirection from MessageBus to resolve infinite loop in debug mode",
    "224b831: refactor: Remove unused import of ThreadPoolExecutor in RealtimeBridge",

    # Version v0.16.1-4dd7627-laminas-docker,
    "4962ae2: [chore] Increment version to v0.16.1-4dd7627-laminas",
    "4dd7627: refactor: Enhance auto-sizing mechanism in DarkListCtrl to prevent multiple calls",
    "747ec20: refactor: Improve shard entry validation logic in ShardListWidget",

    # Version v0.16.0-2de91fb-laminas-docker,
    "98b64c5: [chore] Increment version to v0.16.0-2de91fb-laminas",
    "2de91fb: [chore] Increment version to v0.15.0-53fca67-laminas",
    "53fca67: refactor: Enhance auto-sizing functionality in DarkListCtrl methods",
    "bd7d0b3: refactor: Update import statements to use absolute paths for consistency across modules",
    "83de46e: refactor: Replace CustomListCtrl with DarkListCtrl in SharedLogsWidget and StalledWidget for consistent theming",
    "a5cf9af: refactor: Replace CustomListCtrl with DarkListCtrl across multiple widgets for consistent theming",
    "4d4b497: refactor: Change shard_data structure to a list and prevent duplicate entries",
    "c446c85: feat: Implement ShardListWidget for managing shard data and UI integration",
    "ea22261: refactor: Remove debug logging for specific problematic users in member parsing",
    "7691e6c: Refactor code structure for improved readability and maintainability"
]
