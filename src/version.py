"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 10
RELEASE = 99
MATURITY = "attritus"  # "alpha", "beta", or "final"
PATCH = "267a777"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.9.x series

    # Version v0.9.14-8b2ad66-pyam-exhang-docker
    "267a777: Increment version to v0.9.14-8b2ad66-pyam-exhang",
    "8b2ad66: Refactor build process to use src/gui.py for executable creation and improve readability of pyinstaller command",
    "cec5d1a: Increment version to v0.9.13-35b1d49-pyam-exhang",
    "35b1d49: Refactor icon path retrieval in NotificationManager to use get_application_path for improved asset management",
    "2991d19: Enhance build process by adding SCLogAnalyzer icon and updating executable build options for windowed mode",
    "37496bc: Refactor freeze creation to remove hwnd parameter and enhance window focus handling",
    "2a28ec1: Add freezer functionality for log management and UI integration",
    "5c483fc: Refactor debug mode handling to centralize control in message_bus, simplifying state management across modules",
    "61e5529: Update NotificationManager background color for improved visibility",
    "854c921: Update monitoring button labels for clarity during monitoring state changes",
    "44704e3: Refactor LogAnalyzerFrame to separate main and debug button sizers for improved UI organization",

    # Version v0.9.12-bf90a3d-pyam-exhang-docker
    "429fa1e: Increment version to v0.9.12-bf90a3d-pyam-exhang",
    "bf90a3d: Update .gitignore to exclude SCLogAnalyzer build directory and enhance build.py with zipfile support for distribution",
    "50f7235: Add venv310/ to .gitignore to exclude Python virtual environment files",
    "f9aa33c: Refactor NotificationManager to use wx for notifications and implement NotificationPopup class",

    # Version v0.9.11-87fde04-pyam-exhang-docker
    "8bf2bf4: Increment version to v0.9.11-87fde04-pyam-exhang",
    "87fde04: Add winotify to requirements for Windows notifications",

    # Version v0.9.10-c6c8874-pyam-exhang-docker
    "8c64c32: Increment version to v0.9.10-c6c8874-pyam-exhang",
    "c6c8874: Enable notifications by default in LogAnalyzerFrame and NotificationManager",

    # Version v0.9.9-9d84add-pyam-exhang-docker
    "f3d19c3: Increment version to v0.9.9-9d84add-pyam-exhang",
    "9d84add: Update update_commit_messages to maintain original commit order",
    "ee6400c: Refactor NotificationManager to use MessageRateLimiter for notification rate limiting and remove redundant rate limiting logic",
    "e3f6e27: Implement NotificationManager for Windows Toast notifications and integrate with RealtimeBridge for event notifications",
    "7882e0e: Add realtime event handling in LogFileHandler: implement send_realtime_event method and integrate it into message sending logic",
    "d1b26cf: Comment out unused update_data_source_tabs method for clarity",
    "ca28e7c: Enhance ConfigDialog: add 'vip' to regex keys and 'important_players' to special keys",
    "7d85e16: Remove update_data_source_tabs method: comment out unused function for clarity",
    "7ec0059: Fix VIP pattern compilation: strip whitespace from VIP list entries before regex compilation",
    "e2f2d48: Enhance VIP detection: add VIP players tab in config dialog and implement regex pattern compilation for log analysis",
    "010988c: Refactor LogFileHandler: update message_bus import to avoid relative import and improve clarity",
    "3b4e1f4: Enhance ConnectedUsersPanel: add 'Hora local' column and update log entry handling",
    "667f8f9: Enhance ConnectedUsersPanel: add 'Mode' column and update presence handling in RealtimeBridge",
    "3c48709: Clear current shard when exiting from SC_Default mode in LogFileHandler",

    # Version v0.9.8-d69176d-pyam-exhang-docker
    "ed646bf: Increment version to v0.9.8-d69176d-pyam-exhang",
    "d69176d: Update instructions: centralize plan storage in planes.instructions.md and enhance markdown response requirements for plan changes",
    "9f9a728: Emit force_realtime_reconnect event after state reset in LogFileHandler for improved reconnection handling",
    "1654e6a: Delegate broadcast_ping_missing handling to the main thread using wx.CallAfter for UI safety",

    # Version v0.9.7-4abec3d-pyam-exhang-docker
    "27fac49: Increment version to v0.9.7-4abec3d-pyam-exhang",
    "4abec3d: Enhance private lobby handling: Add 'Private' label to UI and update dynamic labels; implement blocking for private lobby recording in LogFileHandler.",
    "357cdfa: Enhance shard/version update handling: Add 'private' argument to support lobby visibility in ConnectedUsersPanel and RealtimeBridge; implement private lobby recording block in LogFileHandler.",
    "1919fde: Enhance Connected Users Panel: Add user filter checkboxes with images and update filtering logic; modify RealtimeBridge to support user-based message filtering.",

    # Version v0.9.6-df04d86-pyam-exhang-docker
    "a3cc1a9: Increment version to v0.9.6-df04d86-pyam-exhang",
    "df04d86: Enhance UI: Adjust column widths for 'Shard' and 'VersiÃ³n' in Connected Users panel; format last active timestamp in RealtimeBridge",
    "f86edcc: Add 'stalled' message filter checkbox to UI and backend integration",
    "25fc4b7: Update tag creation logic to only execute with --push flag",
    "f9759f6: Add functions to retrieve latest tag and commit information for build process",

    # Version v0.9.5-ab074f6-pyam-exhang-docker
    "4f17c78: Increment version to v0.9.5-ab074f6-pyam-exhang",
    "ab074f6: Add connection icons to PyInstaller build for enhanced visual feedback",

    # Version v0.9.4-90e97ef-pyam-exhang-docker
    "91c79f5: Increment version to v0.9.4-90e97ef-pyam-exhang",

    # Version v0.9.3-fca6a9e-pyam-exhang-docker
    "90e97ef: Increment version to v0.9.3-fca6a9e-pyam-exhang",
    "fca6a9e: Enhance DPI awareness in GUI and apply font scaling in TabCreator for better UI consistency",
    "e510a0b: Add reconnection lock to RealtimeBridge to prevent concurrent reconnect attempts",
    "45a3642: Refactor icon loading in DynamicLabels to use pre-scaled images and remove unnecessary scaling function",
    "de807f9: Add utility script for resizing PNG images for status icons",
    "4cba6d2: Add connection status icons and update DynamicLabels for improved UI feedback",
    "b3695da: Enhance connection status handling in DynamicLabels and add auto-reconnection logic in RealtimeBridge",
    "bd43e10: Add project structure and guidelines documentation for SCLogAnalyzer",
    "9f8582d: Add check for uncommitted .py changes before build process",

    # Version v0.9.2-dca18a4-pyam-exhang-docker
    "06f1f25: Increment version to v0.9.2-dca18a4-pyam-exhang",
    "dca18a4: Enhance RealtimeBridge and ConnectedUsersPanel to improve ping handling and reconnection logic",

    # Version v0.9.1-54d7108-pyam-exhang-docker
    "5e8265c: Increment version to v0.9.1-54d7108-pyam-exhang",
    "54d7108: Fix RealtimeBridge event data logging to use 'event_data' key and set log level to DEBUG",

    # Version v0.9.0-4480e51-pyam-exhang-docker
    "1126fde: Increment version to v0.9.0-4480e51-pyam-exhang",
    "4480e51: Enhance RealtimeBridge to track user activity and improve presence synchronization with ping broadcasts",
    "5708151: Refactor test CLI to support multiprocessing for simulated users and enhance RealtimeBridge integration",
    "d88a5ca: Bump version to v0.9.99-d2f2325-pyam-exhang",
    "053690b: Refactor RealtimeBridge to use a single 'general' channel for presence and broadcast communication",
    "5f205ab: Fix presence synchronization in ConnectedUsersPanel to use 'general' channel",
    "a388adc: Remove manual authentication token setting in SupabaseManager during async connection",
    "d2caab2: Add test CLI for SCLogAnalyzer with simulated users and RealtimeBridge integration",
    "1b8f86e: Change log level to DEBUG for async Supabase client initialization and authentication success messages",
    "f7fccd5: Add stdout redirection control: implement environment variable check and enable/disable functions",
    "b9aa870: Fix mutex check output: restore stdout before error message for clarity",
    "364b342: Add filters for current mode and shard in ConnectedUsersPanel; update log entry handling to include mode",
    "339eff6: Enhance leaderboard display: align numeric columns, add totals for kills and deaths, and include last update timestamp",
]
