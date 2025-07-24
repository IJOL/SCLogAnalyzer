"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 13
RELEASE = 1
MATURITY = "phoenix"  # "alpha", "beta", or "final"
PATCH = "1d63c1c"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"
__version__ = VERSION  

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.13.x series,
    "1d63c1c: fix: Adjust binarization threshold range for improved QR code detection\n\n- Modified the threshold range in the binarization process from 220-140 to 220-180 to enhance the detection of QR codes in images.",
    "b63f47c: refactor: Enhance QR code detection by implementing configurable binarization threshold\n\n- Introduced a new internal function to binarize images based on a configurable threshold.\n- Added logic for adaptive thresholding, starting from a high value and decreasing until a valid QR code is detected.\n- Output the threshold used for binarization to improve debugging and analysis.",
    "610b429: fix: Update import statement in log_analyzer.py to use absolute import",
    "3c1e918: chore: Update .gitignore to include additional files and directories",
    "afce6d6: refactor: Move log_analyzer.py to helpers directory",
    "c39c74a: feat: Update VIP notification format and enhance regex pattern matching\n\n- Modified the VIP notification message format in config.json.template to include the username.\n- Improved regex pattern matching in log_analyzer.py to ensure accurate detection of VIP players by using word boundaries.",

    # Version v0.13.0-21508d4-phoenix-docker,
    "55200c0: [chore] Increment version to v0.13.0-21508d4-phoenix",
    "21508d4: feat: Improve notification handling and toggle button event emission\n\n- Updated notification handling in RealtimeBridge to use configuration settings for enabling notifications.\n- Enhanced ToggleButtonWidget to emit wx.EVT_TOGGLEBUTTON events, improving interaction feedback and UI responsiveness.",

    # Version v0.12.9-c6291f7-valakkar-docker,
    "6ae7065: [chore] Increment version to v0.12.9-c6291f7-valakkar",
    "c6291f7: feat: Update UI components with enhanced button labels and styles\n\n- Replaced standard button labels with emoji-enhanced labels for better visual appeal across various panels, including ConnectedUsersPanel, FreezerPanel, and others.\n- Integrated DarkThemeButton for consistent styling in buttons throughout the application, improving overall user experience.",
    "fcae2e4: feat: Refactor RecordingSwitchWidget and ToggleButtonWidget for improved UI and functionality\n\n- Updated RecordingSwitchWidget to use GenButton for a consistent visual style with DarkThemeButton, enhancing user experience.\n- Changed event handling from toggle to click for better interaction.\n- Refactored ToggleButtonWidget to support internal state management and visual updates, ensuring consistent color application based on state.",

    # Version v0.12.8-e7472b2-valakkar-docker,
    "f6c976f: [chore] Increment version to v0.12.8-e7472b2-valakkar",
    "e7472b2: fix: Correct purple color key in config template\n\n- Updated the color key for the corpse event from \"purple,white\" to \"purple\" in the config.json.template for clarity and consistency.",

    # Version v0.12.7-2411910-valakkar-docker,
    "7cbc996: [chore] Increment version to v0.12.7-2411910-valakkar",
    "2411910: feat: Enhance UI components and improve recording switch functionality\n\n- Updated the RecordingSwitchWidget to display \"Rec ON\" and \"Rec OFF\" labels for better clarity.\n- Introduced a new ToggleButtonWidget for configurable bi-state buttons, enhancing UI flexibility.\n- Integrated the new ToggleButtonWidget into the main application for improved user interaction.",
    "7a3b36e: feat: Introduce RecordingSwitchWidget for managing recording state\n\n- Added RecordingSwitchWidget to control recording functionality with cooldown management using Windows registry.\n- Integrated the widget into LogAnalyzerFrame for direct access to recording controls.\n- Implemented cleanup logic for the recording switch timer on frame closure.",
    "430c0ec: feat: Add corpse event handling and update config template",
    "6070ecc: feat: Enhance TTL calculation and historical detection handling in StalledWidget\n\n- Updated the TTL calculation to include aggressive penalties for historical detections, improving responsiveness to recurring issues.\n- Adjusted the maximum TTL to 6 minutes and refined multipliers for historical detections during cache movement, ensuring more accurate tracking of persistent problems.",
    "075fc23: fix: Optimize Discord message sending based on profile cache\n\n- Updated LogFileHandler to check the profile cache before sending Discord messages for normal profiles.\n- Ensured that messages are only sent if the profile is new, reducing unnecessary notifications and improving efficiency.",
    "b4260ad: fix: Simplify profile data emission in ProfileCache\n\n- Removed unnecessary cleaning of profile data before broadcasting.\n- Updated the event emission logic to directly use the original profile data, enhancing clarity and reducing redundancy.",
    "3369bcf: feat: Add force parameter to send_realtime_event for improved event broadcasting\n\n- Updated the send_realtime_event method to include a force parameter, allowing events to be sent even if the pattern is not in the realtime list.\n- Modified calls to send_realtime_event in LogFileHandler to utilize the new force functionality, ensuring critical events are broadcasted as needed.",

    # Version v0.12.6-c2096a1-valakkar-docker,
    "21cdfe5: [chore] Increment version to v0.12.6-c2096a1-valakkar",
    "c2096a1: chore: Update .gitignore to include build-venv and .cursor\n\n- Added 'build-venv/' and '.cursor/' to the .gitignore file to prevent unnecessary files from being tracked in the repository.",
    "b345a23: fix: Validate page and subtab indices in DataDisplayManager and LogAnalyzerFrame\n\n- Added checks to ensure the selected subtab and current page indices are within valid ranges before accessing them, preventing potential index errors and improving stability.",
    "a855416: feat: Implement nested notebook tabs in DataDisplayManager\n\n- Added functionality to create nested notebook tabs with multiple subtabs in the DataDisplayManager.\n- Enhanced tab creation logic to handle nested structures and refresh events for subtabs.\n- Updated main frame to support refreshing active subtabs within the Data tab, improving user interaction and data management.",
    "ce3ee44: feat: Add notification support for real-time events\n\n- Implemented functionality to emit a notification when specific event types are received and notifications are enabled.\n- Enhanced the RealtimeBridge class to integrate with the notification manager, improving user engagement through timely alerts.",
    "ac42715: refactor: Enhance log profile handling and metadata management\n\n- Updated the LogFileHandler to improve the handling of actor profile events by refining metadata usage and simplifying broadcast logic.\n- Changed the way profile data is cached and emitted, ensuring clearer action definitions and reducing redundancy in metadata fields.\n- Modified ProfileCacheWidget to reflect changes in action terminology, enhancing clarity in the UI.\n- Introduced a new method to determine when profiles should be broadcasted, streamlining the decision-making process for profile notifications.",
    "ccd4380: fix: Update ProfileDetailsDialog interaction handling\n\n- Changed the text click event binding to close the dialog instead of triggering a different action.\n- Added a new method to close the dialog when it loses focus, enhancing user experience and ensuring proper dialog management.",
    "ac496fd: refactor: Improve QR code detection by adjusting image binarization\n\n- Replaced the previous dark thresholding method with a binarization approach for better QR code detection.\n- Set a new threshold value to enhance the clarity of the processed images, ensuring only black and white pixels are retained for decoding.",
    "1b8dac6: refactor: Enhance SharedLogsWidget for shared log management\n\n- Introduced a controller-listener architecture to manage shared log entries effectively.\n- Implemented methods for initializing instances as controllers or listeners, ensuring only the controller subscribes to events.\n- Added functionality to populate the UI from shared data and notify all instances of changes.\n- Streamlined log entry creation and UI updates, improving overall performance and data consistency.",
    "d751cab: refactor: Enhance player management in StalledWidget\n\n- Introduced a mapping from row indices to player names for improved access and management.\n- Cleared the mapping upon UI refresh to ensure data consistency.\n- Added a method to retrieve player names by index, streamlining context menu interactions.\n- Updated player removal logic to include filtering and success notifications, enhancing user feedback.",
    "c9bda48: refactor: Replace tooltip popup with modal dialog for profile details\n\n- Updated the ProfileCacheWidget to display profile details using a modal dialog instead of a popup window, enhancing user experience.\n- Introduced a new ProfileDetailsDialog class for a more structured and visually appealing presentation of profile information.\n- Added a reusable function to build the profile text block, ensuring consistency between the dialog and popup displays.",
    "f27707d: refactor: Integrate ensure_all_field utility for message formatting in LogFileHandler\n\n- Added ensure_all_field function to ensure the 'all' key is included in message data before formatting.\n- Updated multiple instances in LogFileHandler to utilize ensure_all_field, enhancing message consistency and preventing potential formatting issues.\n- Removed the static method for cleaning profile data in ProfileCache, simplifying the profile handling process.",
    "36a2a27: refactor: Enhance profile broadcasting and UI interaction in ProfileCacheWidget and StalledWidget\n\n- Simplified the profile broadcasting process by introducing a new method in ProfileCache to handle broadcasts more efficiently.\n- Updated ProfileCacheWidget to utilize the new broadcasting method, improving clarity and reducing redundancy.\n- Enhanced StalledWidget with historical data management, allowing for better tracking of player activity and TTL calculations.\n- Added UI improvements for displaying player activity levels and historical statistics, enriching the user experience.",
    "7d9803e: refactor: Update icon path retrieval in LogAnalyzerFrame\n\n- Changed the icon path in LogAnalyzerFrame to utilize the new get_template_base_dir function for improved asset management.\n- This adjustment ensures the application can dynamically locate the icon based on the template directory structure.",
    "f8d8c37: refactor: Simplify darkness threshold calculation in LogFileHandler\n\n- Removed the previous method of calculating the darkness threshold using a central pixel region.\n- Set a fixed darkness threshold value to streamline the processing of image data in the log analysis workflow.",
    "bee0549: refactor: Update notification icon path retrieval\n\n- Modified the icon path in the NotificationManager to use the new get_template_base_dir function for improved asset management.\n- Ensured that the application can dynamically locate the icon based on the template directory structure.",

    # Version v0.12.5-d88be00-valakkar-docker,
    "3738340: [chore] Increment version to v0.12.5-d88be00-valakkar",
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
    "99f80d8: feat: Enhance LogFileHandler to differentiate between manual and automatic profile requests, updating event handling accordingly"
]
