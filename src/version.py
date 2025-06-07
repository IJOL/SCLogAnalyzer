"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 11
RELEASE = 3
MATURITY = "laminas"  # "alpha", "beta", or "final"
PATCH = "9b2b76a"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.11.x series,
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
    "2408732: [chore] Update commit message handling and improve formatting in build script",

    # Version v0.10.4-413df9b-attritus-docker,
    "ec336a0: [chore]Increment version to v0.10.4-413df9b-attritus",
    "413df9b: [feat] Add Profile Request button and implement profile request handling",
    "f5a3bb2: [fix] Improve actor death event handling and action determination in profile scraping",
    "9d06062: [feat] Enhance profile scraping functionality and integrate with log analyzer for actor events",
    "3216861: [chore] Update requirements to remove version constraints for consistency",
    "918f85f: [fix] Update statistics messages to include \"Current Month\" suffix and adjust data fetching logic",
    "26d074a: [chore] Refactor build process to use Plumbum for command execution, enhance version management, and add Nuitka build support",
    "305d862: [chore] Add __version__ assignment f",

    # Version v0.10.3-27ef38a-attritus-docker,
    "e4ba561: [chore] Refactor build script to exclude build.py from version increment checks and improve commit validation logic",
    "797d373: Increment version to v0.10.3-27ef38a-attritus",
    "27ef38a: [fix] Enhance SupabaseDataProvider to conditionally order view results by kdr_live and update log message",
    "bc41e70: [fix] Refactor data fetching logic to simplify table existence check and remove redundant message bus notifications",
    "a3dfa15: [feature] Update tab configurations and add views for current and previous month summaries",
    "dc13d5c: Enhance build script to exclude changes in build.py from version increment and tagging processes",

    # Version v0.10.2-f86d692-attritus-docker,
    "d11c738: Increment version to v0.10.2-f86d692-attritus",

    # Version v0.10.1-ff89999-attritus-docker,
    "f86d692: Increment version to v0.10.1-ff89999-attritus",
    "ff89999: Refactor config utility functions to streamline template path retrieval and update icon loading in UI components",
    "c36e6d4: Fix asset path for SCLogAnalyzer icon in build_executables function",
    "1b8e125: Log ping missing thread stop event in RealtimeBridge",
    "6e3bdec: Remove redundant connection initiation for RealtimeBridge in LogAnalyzerFrame",
    "017c86e: Rename force_realtime_reconnect event to realtime_disconnect in LogFileHandler and update RealtimeBridge to handle new event",
    "aaf7a26: Remove reconnect button handler and streamline username handling in RealtimeBridge",
    "58a979a: Fix username change event emission to include previous username",

    # Version v0.10.0-b9b1a83-attritus-docker,
    "0502dbd: Increment version to v0.10.0-b9b1a83-attritus",
    "b9b1a83: Decrement minor version number in get_recent_commits function",
    "3e07073: Update version information to reflect new release details",
    "4002987: Remove FreezerPanel implementation and associated functionality",
    "b860f7a: Implement Freezer tab functionality and remove obsolete freezer helper module",
    "f9ec12f: Add icon creation and extraction functionality for SCLogAnalyzer",
    "855811a: Remove specific instruction files from .gitignore to streamline ignored files list",
    "0d4ab16: Refactor icon path handling to use get_application_path for consistency across modules",
    "7e99c9f: Enhance tag creation to only proceed if there are new commits since the last tag"
]
