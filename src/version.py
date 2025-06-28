"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 12
RELEASE = 5
MATURITY = "valakkar"  # "alpha", "beta", or "final"
PATCH = "d88be00"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.12.x series,
    "d88be00: refactor: Enhance profile broadcasting and error handling\n\n- Updated the LogFileHandler to improve profile broadcasting by adding detailed metadata and error handling in the force_broadcast_profile method.\n- Modified the ProfileCacheWidget to create a complete broadcast structure for profile data.\n- Ensured that profile caching emits events to update the UI, enhancing overall data management and user experience.",
    "cc11c42: refactor: Simplify TTL calculation in StalledWidget\n\n- Removed debug logging for TTL calculation in the StalledWidget class to streamline the code.\n- Maintained the maximum TTL limit of 12 minutes while ensuring clarity in the final TTL computation.",
    "ad79e49: feat: Add FreezerWidget for managing frozen entries\n\n- Introduced FreezerWidget to display and manage frozen entries with functionalities for creating snapshots, opening folders, and deleting entries.\n- Updated ConnectedUsersPanel to include FreezerWidget alongside ProfileCacheWidget, enhancing the user interface with a vertical splitter for better organization.\n- Removed the previous _add_freezer_tab method from DataDisplayManager to streamline tab management.",
    "00c8d1f: refactor: Improve profile data handling in ProfileCache\n\n- Added a static method to clean profile data by removing the 'all' field and filtering out nested dictionaries and lists.\n- Updated the add_profile method to utilize the new cleaning method before saving profile data to the cache, enhancing data integrity.",
    "6288065: chore: Remove custom patch application for UltimateListCtrl\n\n- Eliminated the step that applied a custom colors patch to UltimateListCtrl in the build workflow, streamlining the build process.",

    # Version v0.12.4-580eae9-valakkar-docker,
    "6b132ec: [chore] Increment version to v0.12.4-580eae9-valakkar",
    "580eae9: refactor: Integrate DarkThemeButton for consistent UI styling\n\n- Replaced standard wx.Button instances with DarkThemeButton in multiple panels for a cohesive dark theme experience.\n- Enhanced log analyzer to improve event handling and profile caching logic, including better metadata management and debug logging.\n- Streamlined profile data handling in the RealtimeBridge to ensure accurate event processing and caching.",
    "a051232: refactor: Enhance configuration handling and type safety\n\n- Updated configuration retrieval in multiple modules to ensure values are cast to appropriate types (int, float) for better consistency and error handling.\n- Improved the ConfigDialog to automatically detect and convert types when saving configuration values.\n- Enhanced profile cache size retrieval to ensure it returns an integer value, preventing potential type-related issues.",
    "c490491: feat: Implement profile caching system for player profiles\n\n- Introduced a new ProfileCache class to manage player profiles with LRU caching.\n- Added ProfileCacheWidget for UI management of cached profiles, including refresh and clear functionalities.\n- Enhanced log analyzer to emit profile data for caching and broadcasting.\n- Updated connected users panel to integrate profile cache functionality, improving user experience and data management.",
    "5b92f2c: refactor: Replace UltimateListCtrlAdapter with CustomListCtrl\n\n- Updated imports across multiple files to utilize CustomListCtrl instead of UltimateListCtrlAdapter for improved customization.\n- Introduced CustomListCtrl with a dark theme and enhanced visual customization options, including theme application methods.",

    # Version v0.12.3-89ea2f0-valakkar-docker,
    "dadf544: [chore] Increment version to v0.12.3-89ea2f0-valakkar",
    "89ea2f0: feat: Add StalledWidget for real-time tracking of stalled users\n\n- Introduced StalledWidget to display information about stalled users with real-time updates.\n- Integrated StalledWidget into the main frame, enhancing the UI with a horizontal splitter for better organization of logs and stalled user data.\n- Implemented automatic TTL management and periodic UI refresh for improved user experience.",

    # Version v0.12.2-445801b-valakkar-docker,
    "7d5e879: [chore] Increment version to v0.12.2-445801b-valakkar",
    "445801b: refactor: Update UltimateListCtrlAdapter to use native insert fix\n\n- Removed workaround for inserting items at position 0, now utilizing the native fix in UltimateListCtrl for improved performance.\n- Added a flag to control the workaround behavior for future testing.",

    # Version v0.12.1-f9b37e4-valakkar-docker,
    "0a3fb7e: [chore] Increment version to v0.12.1-f9b37e4-valakkar",
    "f9b37e4: fix: Remove unused remote log handling from ConnectedUsersPanel\n\n- Eliminated the add_remote_log method and its associated UI update logic, streamlining the ConnectedUsersPanel class.",

    # Version v0.12.0-b53e6b7-valakkar-docker,
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
