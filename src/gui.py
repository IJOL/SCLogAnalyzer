#!/usr/bin/env python
import ctypes
# --- Hacer que el proceso sea DPI-aware (Windows)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 1 = system DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import wx
import sys
import os
import traceback
from helpers.ui.main_frame import LogAnalyzerFrame, main

def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Global exception handler to catch any unhandled exceptions"""
    from helpers.core.message_bus import message_bus, MessageLevel
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    message_bus.publish(content="=== GLOBAL EXCEPTION CAUGHT ===", level=MessageLevel.CRITICAL)
    message_bus.publish(content=f"Exception Type: {exc_type.__name__}", level=MessageLevel.CRITICAL)
    message_bus.publish(content=f"Exception Message: {str(exc_value)}", level=MessageLevel.CRITICAL)
    message_bus.publish(content=f"Full Traceback:\n{error_msg}", level=MessageLevel.CRITICAL)
    message_bus.publish(content="=== END GLOBAL EXCEPTION ===", level=MessageLevel.CRITICAL)
    
    # Try to log through message bus if available
    try:
        from helpers.core.message_bus import message_bus, MessageLevel
        message_bus.publish(
            content=f"GLOBAL EXCEPTION: {exc_type.__name__}: {str(exc_value)}",
            level=MessageLevel.ERROR
        )
        message_bus.publish(
            content=f"TRACEBACK: {error_msg}",
            level=MessageLevel.ERROR
        )
    except:
        pass
    
    # Call the original handler to maintain normal behavior
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# This is the new entry point for the SC Log Analyzer application
# The actual implementation has been moved to the helpers module
# for better organization and maintainability.

if __name__ == "__main__":
    # Install global exception handler
    sys.excepthook = global_exception_handler
    from helpers.core.message_bus import message_bus, MessageLevel
    message_bus.publish(content="Global exception handler installed.", level=MessageLevel.INFO)
    
    main()