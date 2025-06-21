"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 12
RELEASE = 1
MATURITY = "valakkar"  # "alpha", "beta", or "final"
PATCH = "f9b37e4"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.12.x series,
    "f9b37e4: fix: Remove unused remote log handling from ConnectedUsersPanel\n\n- Eliminated the add_remote_log method and its associated UI update logic, streamlining the ConnectedUsersPanel class.",
    "2710d72: [chore] Increment version to v0.12.0-b53e6b7-valakkar",
    "b53e6b7: fix: Update SharedLogsWidget to align with ConnectedUsersPanel structure\n\n- Removed specific column insertions from ConnectedUsersPanel\n- Adjusted column initialization in SharedLogsWidget to include 'Hora local' and 'Tipo'\n- Updated log entry handling to reflect new column indices",
    "fd50561: chore: Update .gitignore to include build-venv directory\n\n- Added build-venv to .gitignore to prevent virtual environment files from being tracked",
    "fc69133: chore: Enhance build process with virtual environment support and custom UltimateListCtrl patch\n\n- Updated activate_venv to reference venv executables for Python, pip, and PyInstaller\n- Added apply_ultimatelistctrl_patch function to download and apply a custom patch for selection colors support\n- Integrated patch application into the build process with dry-run capability",
    "ebeb4fd: feat: add SharedLogsWidget with global filters\n\n- Created reusable SharedLogsWidget with context menu\n- Integrated in main_frame with 80/20 splitter layout\n- Moved mode/shard filters to RealtimeBridge as global filters\n- Refactored ConnectedUsersPanel to use SharedLogsWidget\n- Removed code duplication for shared logs functionality",
    "370ad0a: feat: Introduce UltimateListCtrlAdapter for enhanced list control functionality with customizable themes and selection colors",
    "f6cbd4f: feat: Add custom patch for wxPython UltimateListCtrl to support selection colors",
    "02b444b: chore: Introduce configurable virtual environment directory in build process",
    "9fe0596: fix: Ensure rate limit timeout and max duplicates are cast to integers in LogFileHandler initialization",
    "99f80d8: feat: Enhance LogFileHandler to differentiate between manual and automatic profile requests, updating event handling accordingly",

    # Version v0.11.3-9b2b76a-laminas-docker,
    "02b370b: [chore] Increment version to v0.11.3-9b2b76a-laminas",
    "9b2b76a: feat: Add 'Get Profile' option in ConnectedUsersPanel and integrate profile request handling via message bus",
    "ce1542e: fix: Update scraping event from 'actor_death' to 'player_death' in config template and improve formatting in actor_profile message",
    "5129c38: fix: Enhance mode checks in LogFileHandler to include debug mode condition",

    # Version v0.11.2-edae730-laminas-docker,
    "26efe73: [chore] Increment version to v0.11.2-edae730-laminas",
    "edae730: feat: Integrate RealtimeBridge for content filtering in ConnectedUsersPanel, adding right-click menu options for managing filters",
    "4a23f3e: fix: Add 'actor_profile' to notifications_events in config template for improved notification handling",
    "c2be3cb: refactor: Remove unused functions and improve message bus filter documentation",

    # Version v0.11.1-2f34d56-laminas-docker,
    "f053a9e: [chore] Increment version to v0.11.1-2f34d56-laminas",
    "2f34d56: fix: Remove unused regex patterns and messages for player and ship events in config template",
    "30cb3df: fix: Correct formatting in actor_profile message and ensure consistent spacing",
    "fe3a83d: fix: Update ConfigDialog to be modal and improve dialog handling in main frame",
    "97509ad: fix: Add mode check to prevent event processing in non-default mode",
    "dc4bbde: fix: Update organization detection logic and enhance logging in profile parser",
    "010c13b: refactor: Simplify profile scraping by integrating standalone parser and enhancing error handling",
    "eed91fa: refactor: Update async_profile_scraping to accept pattern_name and improve event handling",
    "4074b5a: fix: Enhance organization status detection with detailed logging and error handling",

    # Version v0.11.0-d275e6e-laminas-docker,
    "6ff05e9: [chore] Increment version to v0.11.0-d275e6e-laminas",
    "d275e6e: fix: Correct SQL syntax for hash_value generated column in SupabaseManager",
    "e8eb473: chore: Unified version increment function to handle release, minor, and major increments",
    "7ab7255: fix: Add 'actor_profile' to regex keys in ConfigDialog for message filtering",
    "f3f4b8b: chore: Add functions to increment major and minor versions in version.py",
    "1bf7a1e: fix: Update actor_profile and player_death message formats for consistency",
    "2e1f064: feat: Enhance organization status detection in profile scraping",
    "eb3fed3: chore: Add 'perfiles/' to .gitignore to exclude profile directories from version control",
    "5b2000b: fix: Convert all data to strings in raw_data for consistent handling",
    "fe0a877: fix: Remove datetime parsing for enlisted date in profile data extraction",
    "b96c9aa: fix: Correct commit message formatting and improve non-chore commit filtering logic",
    "78a038e: chore: Remove obsolete build script and related commands",
    "2408732: [chore] Update commit message handling and improve formatting in build script"
]
