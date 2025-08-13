"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 16
RELEASE = 0
MATURITY = "laminas"  # "alpha", "beta", or "final"
PATCH = "2de91fb"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.15.x series,
    "2de91fb: [chore] Increment version to v0.15.0-53fca67-laminas",
    "53fca67: refactor: Enhance auto-sizing functionality in DarkListCtrl methods",
    "bd7d0b3: refactor: Update import statements to use absolute paths for consistency across modules",
    "83de46e: refactor: Replace CustomListCtrl with DarkListCtrl in SharedLogsWidget and StalledWidget for consistent theming",
    "a5cf9af: refactor: Replace CustomListCtrl with DarkListCtrl across multiple widgets for consistent theming",
    "4d4b497: refactor: Change shard_data structure to a list and prevent duplicate entries",
    "c446c85: feat: Implement ShardListWidget for managing shard data and UI integration",
    "ea22261: refactor: Remove debug logging for specific problematic users in member parsing",
    "7691e6c: Refactor code structure for improved readability and maintainability",
    "d9d4a8d: [chore] Increment version to v0.14.3-b79a854-grimhex",
    "b79a854: refactor: Update import paths to use absolute imports from helpers module",
    "d6646cc: feat: Enhance test mode detection in DynamicLabels and RecordingSwitchWidget",
    "94fd05f: feat: Add multi-environment configuration options for log paths and auto-detection",
    "6e017a4: feat: Implement multi-environment detection and monitoring in ConfigManager and UI components",
    "f3406b1: [chore] Increment version to v0.14.2-7b24d09-grimhex",
    "7b24d09: fix: Replace wx.CallLater with wx.CallAfter in initialize_config to prevent timer assertion error during startup",
    "533a0b5: refactor: Implement singleton pattern for OverlayManager and update overlay handling methods",
    "4b6b759: refactor: moved code to smaller modules and adjust everything to match",
    "612a275: [chore] Increment version to v0.14.1-a05b6bb-grimhex",
    "a05b6bb: feat: Add new Python files to .gitignore for improved project cleanliness",
    "c00cd3f: feat: Enhance StalledWidget with improved timer management and cleanup handling",
    "c99b1b5: feat: Refactor cleanup process in SharedLogsWidget to improve destruction handling",
    "e45c6e8: feat: Remove overlay logging for creation and closing in OverlayMixin",
    "03937a4: feat: Improve overlay management by logging overlay creation and closing, and add shared logs overlay toggle functionality",
    "3f65f73: feat: Refactor overlay logging and enhance error handling in cleanup process",
    "051c976: feat: Implement global exception handler for improved error logging and handling",
    "9bca261: feat: Enhance function tracing and critical path debugging with detailed logging",
    "995c642: feat: Enhance warning message for organizations with large member counts",
    "b1fa18f: feat: Remove duplicated cleanup method from DynamicOverlay class",
    "e334c42: feat: Remove deprecated hotkey and overlay settings from configuration template",
    "009563c: feat: Enhance hotkey management with dynamic registration and improved UI components",
    "aeba1b5: feat: Refactor hotkey management to improve registration and thread safety",
    "f9f54ee: feat: Update overlay hotkey registration to include context and improve thread safety",
    "d757da1: feat: Add hotkey configuration UI with config-first editing",
    "1036fe2: feat: Integrate decentralized hotkey system with self-registering components",
    "df2ec7e: feat: Add core hotkey system with decentralized config-first architecture",
    "6c2cc17: feat: Enhance click-through mode initialization and improve overlay setup logic",
    "90b30e9: refactor: Remove unused imports from gui_module.py",
    "69e8a67: [chore] Increment version to v0.14.0-1cd3a0b-grimhex",
    "1cd3a0b: feat: Add overlay settings for StalledWidget and SharedLogsWidget with position, size, opacity, and click-through options",
    "b14be24: feat: Add opacity slider and delayed save functionality to DynamicOverlay",
    "ae5183b: feat: Integrate OverlayMixin into SharedLogsWidget and StalledWidget for enhanced overlay functionality",
    "1c54e1f: feat: Implement OverlayMixin for universal overlay functionality in widgets",
    "0cd424c: feat: Add OverlayManager for dynamic overlay management with factory pattern",
    "60b6948: feat: Implement dynamic overlay system with hybrid polling and widget support",
    "bfb7c6c: fix: Emit configuration update events consistently in ConfigManager and improve reconnection handling in RealtimeBridge"
]
