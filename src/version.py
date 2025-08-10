"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 14
RELEASE = 2
MATURITY = "grimhex"  # "alpha", "beta", or "final"
PATCH = "7b24d09"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.14.x series,
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
    "bfb7c6c: fix: Emit configuration update events consistently in ConfigManager and improve reconnection handling in RealtimeBridge",
    "9a934d5: [chore] Increment version to v0.13.7-6200fb5-phoenix",
    "6200fb5: fix: Update message bus publish calls for VIP player management consistency",
    "7580643: feat: Revamp TTL calculation and activity intensity metrics in StalledWidget",
    "3c5d89b: feat: Implement VIP player management in OrgMembersWidget and ProfileCacheWidget",
    "bbe7d5a: fix: Update message bus event names for consistency\n\n- Changed event name from \"config.saved\" to \"config_saved\" in the message bus to maintain uniformity across the application.\n- Updated related error handling to reflect the new event name.",
    "4d61b05: fix: Prevent empty patterns in log analyzer\n\n- Added a check to skip empty patterns when compiling regex for important players in the LogFileHandler class, ensuring cleaner pattern matching and avoiding potential errors.",
    "a61550c: feat: Enhance OrgMembersWidget functionality\n\n- Added a MiniDarkThemeButton for clearing the search input and member list.\n- Updated UI elements for better spacing and clarity, including title and status label adjustments.\n- Improved status updates to reflect visible and redacted member counts during searches.",
    "71af939: refactor: Simplify organization data fetching logic\n\n- Removed retry mechanism for total member count validation in `_fetch_all_org_data`, simplifying the process.\n- Updated logging messages to reflect changes in data retrieval flow, enhancing clarity and maintainability.\n- Cleaned up commented-out code to improve overall code readability.",
    "1b54db0: feat: Add MiniDarkThemeButton component\n\n- Introduced a new MiniDarkThemeButton class for a compact dark-themed button that displays only an emoji.\n- Configured default styles, colors, and font size to enhance UI consistency and usability.",

    # Version v0.13.6-72a3b2e-phoenix-docker,
    "cc11bcc: [chore] Increment version to v0.13.6-72a3b2e-phoenix",
    "72a3b2e: feat: Add member count warning in organization search\n\n- Introduced a check for organizations with more than 500 members during the search process, prompting a warning message to the user about potential loading delays.\n- Enhanced context menu handling to ensure accurate member retrieval based on the displayed username in the list.",
    "f466355: feat: Add handler for realtime reconnection event\n\n- Implemented a new event handler for the \"realtime_reconnected\" event to update the UI status when the connection is restored.\n- Enhanced the existing \"broadcast_ping_missing\" handler by removing commented-out code to improve code clarity and maintainability.",
    "7ac9ba1: feat: Enhance organization data retrieval with retry logic and validation\n\n- Implemented automatic retry mechanism for HTTP requests in the `_make_request_with_retry` function to handle throttling and network errors.\n- Added logging for progress and errors using MessageBus to improve monitoring during data scraping.\n- Introduced validation against total member count to ensure data integrity during organization data fetching.\n- Updated `_fetch_all_org_data` to support retries and detailed error handling, enhancing robustness of the scraping process.",
    "b574be1: refactor: Update message bus subscription for reconnected event\n\n- Changed the subscription for the \"realtime_reconnected\" event to use a lambda function with wx.CallAfter for improved thread safety and UI responsiveness.",
    "a641836: chore: Update .gitignore",
    "6aa3eb8: refactor: Simplify profile data access in ProfileCacheWidget\n\n- Updated the way profile data is accessed by introducing a `data` variable to encapsulate `profile_data.get('profile_data', {})`.\n- Removed unused cleanup method to streamline the code and improve maintainability.",
    "4a2871a: fix: Increase page limit in _fetch_all_org_data function\n\n- Updated the maximum page limit from 50 to 150 in the _fetch_all_org_data function to allow for more comprehensive data retrieval during organization scraping.",
    "97d2f57: refactor: Remove unused cleanup code and message bus subscriptions in ConnectedUsersPanel\n\n- Deleted redundant cleanup logic for cache and freezer widgets.\n- Removed message bus subscription unsubscriptions to streamline the component lifecycle.",

    # Version v0.13.5-b90b336-phoenix-docker,
    "1d1254d: [chore] Increment version to v0.13.5-b90b336-phoenix",
    "b90b336: feat: Implement column sorting functionality in CustomListCtrl\n\n- Added sorting capabilities to the CustomListCtrl, allowing users to sort by clicking on column headers.\n- Implemented methods for detecting data types, sorting data, and updating sort indicators.\n- Introduced public API methods to enable/disable sorting and manage sort state programmatically.",
    "19cdf3d: fix: Update OrgMembersWidget initialization in ConnectedUsersPanel\n\n- Removed the explicit column specification in the OrgMembersWidget instantiation to allow for default behavior.\n- Simplified the widget setup for better maintainability.",
    "893af0a: feat: Update search organization event handler in OrgMembersWidget\n\n- Modified the `_on_search_organization_event` method to accept an optional `source` parameter for enhanced event handling.\n- Improved flexibility in processing organization search events.",
    "4ecc6fe: feat: Enhance ProfileCacheWidget with organization search functionality\n\n- Added a context menu option to search for a player's organization if available.\n- Implemented the `_search_organization` method to handle organization search events and logging.\n- Updated context menu to include organization details with appropriate icons for improved user experience.",
    "f5a4e9c: feat: Enhance error handling in RSI Organization Scraper\n\n- Improved error handling for API responses, including throttling and invalid data sections.\n- Added checks for success status and refined exception messages for better clarity.\n- Ensured safe extraction of HTML content from API responses to prevent runtime errors.",
    "bde735e: feat: Enhance context menu in SharedLogsWidget with icons\n\n- Updated context menu items to include icons for improved user experience.\n- Changed menu item labels to feature emoticons for filtering, clearing, and profile retrieval options.",
    "640715e: feat: Integrate OrgMembersWidget into ConnectedUsersPanel layout\n\n- Added OrgMembersWidget to display organization members alongside ProfileCache and Freezer widgets.\n- Adjusted layout to accommodate the new widget with updated splitter configurations.\n- Implemented cleanup for existing components and removed message bus subscriptions to prevent memory leaks.",
    "510d26f: feat: Introduce OrgMembersWidget for organization member search and display\n\n- Added a new widget for searching and visualizing non-redacted members of Star Citizen organizations.\n- Implemented UI components including search input, buttons, and a member list with dynamic columns.\n- Integrated threading for search operations to maintain UI responsiveness.\n- Added context menu options for member profile retrieval and name copying.",
    "2a6ee2e: feat: Add RSI Organization Scraper module\n\n- Introduced a new module for scraping organization member data from the RSI API.\n- Implemented functions to fetch all organization data, retrieve member information, and save HTML pages.\n- Added error handling for network requests and response validation.",
    "f419b65: feat: Update menu items in ProfileCacheWidget with icons\n\n- Added icons to menu items for improved user experience.\n- Updated \"Ver detalles\" to \"🔍 Ver detalles\", \"Enviar a Discord\" to \"🔊 Enviar a Discord\", and \"Eliminar del cache\" to \"🗑️ Eliminar del cache\".",

    # Version v0.13.4-f23a3e7-phoenix-docker,
    "074c197: [chore] Increment version to v0.13.4-f23a3e7-phoenix",
    "f23a3e7: feat: Add functionality to send player profiles to Discord\n\n- Introduced a new menu item in ProfileCacheWidget for sending profiles to Discord.\n- Implemented the `_send_discord` method in ProfileCacheWidget to handle the sending process.\n- Added `send_discord_message` method in ProfileCache to manage Discord message publishing and error handling.",
    "0dc5d92: feat: Add new event handlers for Discord and real-time messaging in log_analyzer.py\n\n- Introduced `_on_send_discord` and `_on_send_realtime` methods to handle respective events.\n- Updated event subscriptions to include new handlers for improved messaging functionality.",

    # Version v0.13.3-11b0ea6-phoenix-docker,
    "5194c28: [chore] Increment version to v0.13.3-11b0ea6-phoenix",
    "11b0ea6: refactor: Improve actor profile handling in log_analyzer.py\n\n- Added cache check for player profiles before processing broadcast data.\n- Enhanced logging and notification for received profiles.\n- Streamlined the logic for sending Discord messages based on profile status.",
    "6273ba5: refactor: Simplify profile broadcasting logic in ProfileCache class\n\n- Removed direct profile data emission in favor of a dedicated broadcast method for cleaner code.\n- Enhanced error handling during profile broadcasting.",

    # Version v0.13.2-1623ef0-phoenix-docker,
    "6a4f7f7: [chore] Increment version to v0.13.2-1623ef0-phoenix",
    "1623ef0: fix: Convert cropped image to grayscale for improved QR code detection",

    # Version v0.13.1-1d63c1c-phoenix-docker,
    "106935c: [chore] Increment version to v0.13.1-1d63c1c-phoenix",
    "1d63c1c: fix: Adjust binarization threshold range for improved QR code detection\n\n- Modified the threshold range in the binarization process from 220-140 to 220-180 to enhance the detection of QR codes in images.",
    "b63f47c: refactor: Enhance QR code detection by implementing configurable binarization threshold\n\n- Introduced a new internal function to binarize images based on a configurable threshold.\n- Added logic for adaptive thresholding, starting from a high value and decreasing until a valid QR code is detected.\n- Output the threshold used for binarization to improve debugging and analysis.",
    "610b429: fix: Update import statement in log_analyzer.py to use absolute import",
    "3c1e918: chore: Update .gitignore to include additional files and directories",
    "afce6d6: refactor: Move log_analyzer.py to helpers directory",
    "c39c74a: feat: Update VIP notification format and enhance regex pattern matching\n\n- Modified the VIP notification message format in config.json.template to include the username.\n- Improved regex pattern matching in log_analyzer.py to ensure accurate detection of VIP players by using word boundaries.",

    # Version v0.13.0-21508d4-phoenix-docker,
    "55200c0: [chore] Increment version to v0.13.0-21508d4-phoenix",
    "21508d4: feat: Improve notification handling and toggle button event emission\n\n- Updated notification handling in RealtimeBridge to use configuration settings for enabling notifications.\n- Enhanced ToggleButtonWidget to emit wx.EVT_TOGGLEBUTTON events, improving interaction feedback and UI responsiveness."
]
