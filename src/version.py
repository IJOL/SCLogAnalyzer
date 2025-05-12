"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 9
RELEASE = 6
MATURITY = "pyam-exhang"  # "alpha", "beta", or "final"
PATCH = "df04d86"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.9.x series
    "339eff6: Enhance leaderboard display: align numeric columns, add totals for kills and deaths, and include last update timestamp",
    "364b342: Add filters for current mode and shard in ConnectedUsersPanel; update log entry handling to include mode",
    "b9aa870: Fix mutex check output: restore stdout before error message for clarity",
    "f7fccd5: Add stdout redirection control: implement environment variable check and enable/disable functions",
    "1b8f86e: Change log level to DEBUG for async Supabase client initialization and authentication success messages",
    "d2caab2: Add test CLI for SCLogAnalyzer with simulated users and RealtimeBridge integration",
    "a388adc: Remove manual authentication token setting in SupabaseManager during async connection",
    "5f205ab: Fix presence synchronization in ConnectedUsersPanel to use 'general' channel",
    "053690b: Refactor RealtimeBridge to use a single 'general' channel for presence and broadcast communication",
    "d88a5ca: Bump version to v0.9.99-d2f2325-pyam-exhang",
    "5708151: Refactor test CLI to support multiprocessing for simulated users and enhance RealtimeBridge integration",
    "4480e51: Enhance RealtimeBridge to track user activity and improve presence synchronization with ping broadcasts",

    # Version v0.9.0-4480e51-pyam-exhang-docker
    "1126fde: Increment version to v0.9.0-4480e51-pyam-exhang",
    "54d7108: Fix RealtimeBridge event data logging to use 'event_data' key and set log level to DEBUG",

    # Version v0.9.1-54d7108-pyam-exhang-docker
    "5e8265c: Increment version to v0.9.1-54d7108-pyam-exhang",
    "dca18a4: Enhance RealtimeBridge and ConnectedUsersPanel to improve ping handling and reconnection logic",

    # Version v0.9.2-dca18a4-pyam-exhang-docker
    "06f1f25: Increment version to v0.9.2-dca18a4-pyam-exhang",
    "9f8582d: Add check for uncommitted .py changes before build process",
    "bd43e10: Add project structure and guidelines documentation for SCLogAnalyzer",
    "b3695da: Enhance connection status handling in DynamicLabels and add auto-reconnection logic in RealtimeBridge",
    "4cba6d2: Add connection status icons and update DynamicLabels for improved UI feedback",
    "de807f9: Add utility script for resizing PNG images for status icons",
    "45a3642: Refactor icon loading in DynamicLabels to use pre-scaled images and remove unnecessary scaling function",
    "e510a0b: Add reconnection lock to RealtimeBridge to prevent concurrent reconnect attempts",
    "fca6a9e: Enhance DPI awareness in GUI and apply font scaling in TabCreator for better UI consistency",

    # Version v0.9.3-fca6a9e-pyam-exhang-docker
    "90e97ef: Increment version to v0.9.3-fca6a9e-pyam-exhang",

    # Version v0.9.4-90e97ef-pyam-exhang-docker
    "91c79f5: Increment version to v0.9.4-90e97ef-pyam-exhang",
    "ab074f6: Add connection icons to PyInstaller build for enhanced visual feedback",

    # Version v0.9.5-ab074f6-pyam-exhang-docker
    "4f17c78: Increment version to v0.9.5-ab074f6-pyam-exhang",
    "f9759f6: Add functions to retrieve latest tag and commit information for build process",
    "25fc4b7: Update tag creation logic to only execute with --push flag",
    "f86edcc: Add 'stalled' message filter checkbox to UI and backend integration",
    "df04d86: Enhance UI: Adjust column widths for 'Shard' and 'VersiÃ³n' in Connected Users panel; format last active timestamp in RealtimeBridge",
]
